"""
Comparison service: aggregates trades per bot and produces:
  1. Live vs Backtest metric deltas + a match-quality classification.
  2. Recent vs Historical comparison within the live dataset.

All accounts are treated as one big account per the product spec.
Strategy grouping comes only from the live data; backtest trades inherit
their strategy via a bot->strategy lookup built from the live upload.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from statistics import mean, pstdev
from typing import Iterable
import logging

from sqlalchemy.orm import Session

from models import ComparisonUpload, ComparisonTrade

logger = logging.getLogger(__name__)


@dataclass
class BotMetrics:
    bot_name: str
    strategy: str | None
    trade_count: int
    total_pl: float
    avg_pl_per_trade: float
    win_rate: float  # 0.0 - 1.0
    largest_win: float
    largest_loss: float
    profit_factor: float | None  # gross wins / gross losses; None if no losses

    def to_dict(self) -> dict:
        return asdict(self)


# ---- aggregation ----------------------------------------------------------

def _metrics_from_trades(bot: str, strategy: str | None, trades: list[ComparisonTrade]) -> BotMetrics:
    pls = [t.pl for t in trades]
    wins = [pl for pl in pls if pl > 0]
    losses = [pl for pl in pls if pl < 0]
    total = sum(pls)
    count = len(pls)
    win_rate = len(wins) / count if count else 0.0
    largest_win = max(pls) if pls else 0.0
    largest_loss = min(pls) if pls else 0.0
    gross_losses = abs(sum(losses))
    profit_factor = (sum(wins) / gross_losses) if gross_losses > 0 else None
    return BotMetrics(
        bot_name=bot,
        strategy=strategy,
        trade_count=count,
        total_pl=total,
        avg_pl_per_trade=(total / count) if count else 0.0,
        win_rate=win_rate,
        largest_win=largest_win,
        largest_loss=largest_loss,
        profit_factor=profit_factor,
    )


def aggregate_by_bot(trades: Iterable[ComparisonTrade], strategy_lookup: dict[str, str] | None = None) -> dict[str, BotMetrics]:
    """Group trades by bot_name, ignoring account_num. strategy_lookup overrides trade.strategy when present."""
    buckets: dict[str, list[ComparisonTrade]] = {}
    for t in trades:
        buckets.setdefault(t.bot_name, []).append(t)
    out: dict[str, BotMetrics] = {}
    for bot, items in buckets.items():
        strat = (strategy_lookup or {}).get(bot)
        if strat is None:
            # fall back to whatever the trade itself carried (live trades only)
            for t in items:
                if t.strategy:
                    strat = t.strategy
                    break
        out[bot] = _metrics_from_trades(bot, strat, items)
    return out


def build_strategy_lookup_from_live(live_trades: Iterable[ComparisonTrade]) -> dict[str, str]:
    """bot_name -> strategy. Last non-empty wins (stable across the file)."""
    lookup: dict[str, str] = {}
    for t in live_trades:
        if t.strategy and t.bot_name:
            lookup[t.bot_name] = t.strategy
    return lookup


# ---- comparison: live vs backtest -----------------------------------------

def clip_to_live_start(
    live_trades: list[ComparisonTrade],
    backtest_trades: list[ComparisonTrade],
) -> tuple[list[ComparisonTrade], datetime | None, int]:
    """Drop backtest trades that occur before the live data's first trade date.

    The backtest is often pulled over a wider window than the live data (e.g. a
    full year-to-date export while live trading didn't begin until February).
    Comparing the whole backtest against a shorter live window is apples-to-oranges,
    so we align the backtest's start to the live start date. Only the lower bound is
    clipped; backtest trades after the live start (including any past the live end)
    are kept.

    Returns (clipped_backtest, live_start, num_excluded). No-op (returns the backtest
    unchanged with live_start=None) when either side is empty.
    """
    if not live_trades or not backtest_trades:
        return list(backtest_trades), None, 0
    live_start = min(t.entry_date for t in live_trades)
    kept = [t for t in backtest_trades if t.entry_date >= live_start]
    return kept, live_start, len(backtest_trades) - len(kept)


def _safe_pct_deviation(live_val: float, bt_val: float) -> float | None:
    """Return |live - bt| / |bt| as a fraction. None when bt is ~0 (undefined)."""
    if bt_val == 0:
        return None
    return abs(live_val - bt_val) / abs(bt_val)


def _classify_match(dev: float | None) -> str:
    """green <15%, yellow 15-30%, red >30%, gray if undefined."""
    if dev is None:
        return "gray"
    if dev < 0.15:
        return "green"
    if dev < 0.30:
        return "yellow"
    return "red"


def compare_live_vs_backtest(
    live: dict[str, BotMetrics],
    backtest: dict[str, BotMetrics],
) -> list[dict]:
    """Return per-bot comparison rows. Includes bots present in either side."""
    rows: list[dict] = []
    all_bots = sorted(set(live.keys()) | set(backtest.keys()), key=lambda s: s.lower())
    for bot in all_bots:
        lm = live.get(bot)
        bm = backtest.get(bot)
        strategy = (lm.strategy if lm else None) or (bm.strategy if bm else None)

        if lm and bm:
            pl_per_trade_dev = _safe_pct_deviation(lm.avg_pl_per_trade, bm.avg_pl_per_trade)
            win_rate_dev = _safe_pct_deviation(lm.win_rate, bm.win_rate)
            # Overall match quality is the worse of the two key metrics
            devs = [d for d in (pl_per_trade_dev, win_rate_dev) if d is not None]
            overall_dev = max(devs) if devs else None
            presence = "both"
        elif lm:
            pl_per_trade_dev = None
            win_rate_dev = None
            overall_dev = None
            presence = "live_only"
        else:
            pl_per_trade_dev = None
            win_rate_dev = None
            overall_dev = None
            presence = "backtest_only"

        rows.append({
            "bot_name": bot,
            "strategy": strategy,
            "presence": presence,
            "live": lm.to_dict() if lm else None,
            "backtest": bm.to_dict() if bm else None,
            "pl_per_trade_deviation": pl_per_trade_dev,
            "win_rate_deviation": win_rate_dev,
            "overall_deviation": overall_dev,
            "match_quality": _classify_match(overall_dev) if presence == "both" else "gray",
        })
    return rows


# ---- comparison: recent vs historical -------------------------------------

def split_recent_historical(
    trades: list[ComparisonTrade],
    recent_window_days: int,
) -> tuple[list[ComparisonTrade], list[ComparisonTrade], datetime | None]:
    """Split into (recent, historical, recent_cutoff) using the max entry_date in the trades."""
    if not trades:
        return [], [], None
    max_date = max(t.entry_date for t in trades)
    cutoff = max_date - timedelta(days=recent_window_days)
    recent = [t for t in trades if t.entry_date > cutoff]
    historical = [t for t in trades if t.entry_date <= cutoff]
    return recent, historical, cutoff


def _classify_trend(recent: float, historical_mean: float, historical_std: float) -> str:
    """z-score based: improving > +1σ, degrading < -1σ, else stable. Gray when no spread."""
    if historical_std <= 0:
        # No variance to compare against — fall back to ±10% pct change
        if historical_mean == 0:
            return "gray"
        pct = (recent - historical_mean) / abs(historical_mean)
        if pct > 0.10:
            return "improving"
        if pct < -0.10:
            return "degrading"
        return "stable"
    z = (recent - historical_mean) / historical_std
    if z > 1.0:
        return "improving"
    if z < -1.0:
        return "degrading"
    return "stable"


def compare_recent_vs_historical(
    live_trades: list[ComparisonTrade],
    recent_window_days: int = 30,
) -> list[dict]:
    """
    For each bot in live data, compare recent-window metrics against the full
    historical baseline (everything before the recent window).
    """
    strategy_lookup = build_strategy_lookup_from_live(live_trades)
    recent_trades, hist_trades, cutoff = split_recent_historical(live_trades, recent_window_days)
    recent_by_bot = aggregate_by_bot(recent_trades, strategy_lookup)
    hist_by_bot = aggregate_by_bot(hist_trades, strategy_lookup)

    # Build per-bot daily-PL series from historical data to estimate volatility of avg_pl_per_trade
    hist_buckets: dict[str, list[float]] = {}
    for t in hist_trades:
        hist_buckets.setdefault(t.bot_name, []).append(t.pl)

    rows: list[dict] = []
    all_bots = sorted(set(recent_by_bot.keys()) | set(hist_by_bot.keys()), key=lambda s: s.lower())
    for bot in all_bots:
        rm = recent_by_bot.get(bot)
        hm = hist_by_bot.get(bot)
        strategy = strategy_lookup.get(bot)

        # Trend on avg_pl_per_trade
        if rm and hm:
            hist_pls = hist_buckets.get(bot, [])
            hist_std = pstdev(hist_pls) if len(hist_pls) > 1 else 0.0
            trend_pl = _classify_trend(
                recent=rm.avg_pl_per_trade,
                historical_mean=hm.avg_pl_per_trade,
                historical_std=hist_std,
            )
            # Win-rate trend uses a simpler ±5 percentage-point band
            wr_delta = rm.win_rate - hm.win_rate
            if wr_delta > 0.05:
                trend_wr = "improving"
            elif wr_delta < -0.05:
                trend_wr = "degrading"
            else:
                trend_wr = "stable"
        else:
            trend_pl = "no_data"
            trend_wr = "no_data"

        rows.append({
            "bot_name": bot,
            "strategy": strategy,
            "recent": rm.to_dict() if rm else None,
            "historical": hm.to_dict() if hm else None,
            "pl_per_trade_trend": trend_pl,
            "win_rate_trend": trend_wr,
        })
    return rows


# ---- DB helpers -----------------------------------------------------------

def replace_upload(
    db: Session,
    user_id: int,
    upload_type: str,
    source_format: str,
    filename: str,
    trades: list,  # list of ParsedTrade
    period_start: datetime | None,
    period_end: datetime | None,
) -> ComparisonUpload:
    """Delete prior uploads of the same (user_id, upload_type), then insert the new one."""
    db.query(ComparisonUpload).filter(
        ComparisonUpload.user_id == user_id,
        ComparisonUpload.upload_type == upload_type,
    ).delete(synchronize_session=False)

    upload = ComparisonUpload(
        user_id=user_id,
        upload_type=upload_type,
        source_format=source_format,
        filename=filename,
        period_start=period_start,
        period_end=period_end,
        trade_count=len(trades),
    )
    db.add(upload)
    db.flush()

    rows = [
        ComparisonTrade(
            upload_id=upload.id,
            bot_name=t.bot_name,
            strategy=t.strategy,
            entry_date=t.entry_date,
            exit_date=t.exit_date,
            pl=t.pl,
            win_loss=t.win_loss,
            buying_power=t.buying_power,
            contracts=t.contracts,
            account_num=t.account_num,
        )
        for t in trades
    ]
    db.bulk_save_objects(rows)
    db.commit()
    db.refresh(upload)
    return upload


def get_user_uploads(db: Session, user_id: int) -> dict[str, ComparisonUpload | None]:
    """Return {'live': ComparisonUpload|None, 'backtest': ComparisonUpload|None} for a user."""
    out: dict[str, ComparisonUpload | None] = {"live": None, "backtest": None}
    for u in db.query(ComparisonUpload).filter(ComparisonUpload.user_id == user_id).all():
        out[u.upload_type] = u
    return out


def load_trades(db: Session, upload_id: int) -> list[ComparisonTrade]:
    return db.query(ComparisonTrade).filter(ComparisonTrade.upload_id == upload_id).all()
