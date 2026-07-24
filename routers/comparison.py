"""
Live vs Backtest comparison endpoints.

Endpoints:
  POST /api/comparison/upload           Upload a live or backtest CSV (auto-detects format).
  GET  /api/comparison/status            Return what the user currently has uploaded.
  GET  /api/comparison/live-vs-backtest  Per-bot comparison of live vs backtest.
  GET  /api/comparison/recent-vs-history Per-bot recent-window vs historical trend.
  DELETE /api/comparison/upload/{type}   Wipe a live or backtest upload.
"""
from __future__ import annotations

from typing import Annotated
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query
from sqlalchemy.orm import Session

from auth_middleware import get_current_user
from database import get_db
from models import User
from comparison_parser import parse_csv, UnknownFormatError
from comparison_service import (
    aggregate_by_bot,
    build_strategy_lookup_from_live,
    clip_to_live_start,
    compare_live_vs_backtest,
    compare_recent_vs_historical,
    get_user_uploads,
    load_trades,
    replace_upload,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _serialize_upload(u) -> dict | None:
    if u is None:
        return None
    return {
        "id": u.id,
        "upload_type": u.upload_type,
        "source_format": u.source_format,
        "filename": u.filename,
        "period_start": u.period_start.isoformat() if u.period_start else None,
        "period_end": u.period_end.isoformat() if u.period_end else None,
        "trade_count": u.trade_count,
        "uploaded_at": u.uploaded_at.isoformat() if u.uploaded_at else None,
    }


@router.post("/upload")
async def upload_comparison_csv(
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    upload_type: str = Form(...),  # 'live' or 'backtest'
    db: Session = Depends(get_db),
):
    if upload_type not in ("live", "backtest"):
        raise HTTPException(status_code=400, detail="upload_type must be 'live' or 'backtest'")

    content = await file.read()
    try:
        result = parse_csv(content, file.filename)
    except UnknownFormatError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to parse comparison CSV")
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}")

    # Sanity check: live should be TradeSteward, backtest should be Backtick.
    expected = {"live": "tradesteward", "backtest": "backtick"}
    if result.source_format != expected[upload_type]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"CSV looks like {result.source_format} format but was uploaded as {upload_type}. "
                f"Expected {expected[upload_type]}."
            ),
        )

    if not result.trades:
        raise HTTPException(status_code=400, detail="No valid trades found in CSV")

    upload = replace_upload(
        db=db,
        user_id=current_user.id,
        upload_type=upload_type,
        source_format=result.source_format,
        filename=file.filename or "uploaded.csv",
        trades=result.trades,
        period_start=result.period_start,
        period_end=result.period_end,
    )

    return {"success": True, "upload": _serialize_upload(upload)}


@router.get("/status")
async def comparison_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    uploads = get_user_uploads(db, current_user.id)
    return {
        "success": True,
        "live": _serialize_upload(uploads.get("live")),
        "backtest": _serialize_upload(uploads.get("backtest")),
    }


@router.get("/live-vs-backtest")
async def live_vs_backtest(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    uploads = get_user_uploads(db, current_user.id)
    live_upload = uploads.get("live")
    bt_upload = uploads.get("backtest")
    if not live_upload and not bt_upload:
        raise HTTPException(status_code=404, detail="No comparison uploads yet. Upload a live and/or backtest CSV first.")

    live_trades = load_trades(db, live_upload.id) if live_upload else []
    bt_trades = load_trades(db, bt_upload.id) if bt_upload else []

    # Align the backtest to the live start date: drop backtest trades that occur
    # before live trading began, so both sides cover the same starting point.
    bt_trades, live_start, bt_excluded = clip_to_live_start(live_trades, bt_trades)

    strategy_lookup = build_strategy_lookup_from_live(live_trades)
    live_metrics = aggregate_by_bot(live_trades, strategy_lookup)
    bt_metrics = aggregate_by_bot(bt_trades, strategy_lookup)
    rows = compare_live_vs_backtest(live_metrics, bt_metrics)

    return {
        "success": True,
        "live": _serialize_upload(live_upload),
        "backtest": _serialize_upload(bt_upload),
        "alignment": {
            "applied": live_start is not None,
            "live_start": live_start.isoformat() if live_start else None,
            "backtest_trades_excluded": bt_excluded,
        },
        "rows": rows,
        "summary": {
            "bots_in_both": sum(1 for r in rows if r["presence"] == "both"),
            "live_only": sum(1 for r in rows if r["presence"] == "live_only"),
            "backtest_only": sum(1 for r in rows if r["presence"] == "backtest_only"),
            "green": sum(1 for r in rows if r["match_quality"] == "green"),
            "yellow": sum(1 for r in rows if r["match_quality"] == "yellow"),
            "red": sum(1 for r in rows if r["match_quality"] == "red"),
        },
    }


@router.get("/recent-vs-history")
async def recent_vs_history(
    current_user: Annotated[User, Depends(get_current_user)],
    recent_window_days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    uploads = get_user_uploads(db, current_user.id)
    live_upload = uploads.get("live")
    if not live_upload:
        raise HTTPException(status_code=404, detail="Upload a live CSV first to compare recent vs historical.")

    live_trades = load_trades(db, live_upload.id)
    rows = compare_recent_vs_historical(live_trades, recent_window_days=recent_window_days)
    return {
        "success": True,
        "live": _serialize_upload(live_upload),
        "recent_window_days": recent_window_days,
        "rows": rows,
        "summary": {
            "improving": sum(1 for r in rows if r["pl_per_trade_trend"] == "improving"),
            "stable": sum(1 for r in rows if r["pl_per_trade_trend"] == "stable"),
            "degrading": sum(1 for r in rows if r["pl_per_trade_trend"] == "degrading"),
            "no_data": sum(1 for r in rows if r["pl_per_trade_trend"] == "no_data"),
        },
    }


@router.get("/dashboard-data")
async def dashboard_data(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """Compact trade-level payload for the performance dashboard page.

    Requires both a live and a backtest upload; the dashboard compares the two.
    All metric/drift math runs client-side so capital and mapping stay adjustable.
    """
    from comparison_dashboard_service import build_dashboard_payload

    uploads = get_user_uploads(db, current_user.id)
    live_upload = uploads.get("live")
    bt_upload = uploads.get("backtest")

    missing = [name for name, u in (("live", live_upload), ("backtest", bt_upload)) if not u]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Upload a {' and '.join(missing)} CSV first to build the dashboard.",
        )

    live_trades = load_trades(db, live_upload.id)
    bt_trades = load_trades(db, bt_upload.id)
    if not live_trades or not bt_trades:
        raise HTTPException(status_code=404, detail="Uploaded files contain no trades.")

    payload = build_dashboard_payload(live_trades, bt_trades)
    payload["uploads"] = {
        "live": _serialize_upload(live_upload),
        "backtest": _serialize_upload(bt_upload),
    }
    return payload


@router.delete("/upload/{upload_type}")
async def delete_upload(
    upload_type: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    if upload_type not in ("live", "backtest"):
        raise HTTPException(status_code=400, detail="upload_type must be 'live' or 'backtest'")
    from models import ComparisonUpload
    db.query(ComparisonUpload).filter(
        ComparisonUpload.user_id == current_user.id,
        ComparisonUpload.upload_type == upload_type,
    ).delete(synchronize_session=False)
    db.commit()
    return {"success": True}
