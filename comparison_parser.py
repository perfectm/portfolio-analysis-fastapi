"""
CSV parsers for the Live vs Backtest comparison feature.

Supports two formats:
- TradeSteward live performance logs (BotName, Strategy, OpenDate, TotalNetProfitLoss, ...)
- Backtick backtest exports (Position Name, Entry Date, Trade P/L, Win / Loss, ...)

Returns trade-level dicts ready to be inserted into comparison_trades.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from typing import Iterable
import csv
import logging

logger = logging.getLogger(__name__)


@dataclass
class ParsedTrade:
    bot_name: str
    strategy: str | None
    entry_date: datetime
    exit_date: datetime | None
    pl: float
    win_loss: int | None  # 1 win, 0 loss, None if unknown
    buying_power: float | None
    contracts: int | None
    account_num: str | None


@dataclass
class ParseResult:
    source_format: str  # 'tradesteward' or 'backtick'
    trades: list[ParsedTrade]
    period_start: datetime | None
    period_end: datetime | None


class UnknownFormatError(ValueError):
    """Raised when the CSV header doesn't match any supported format."""


def _to_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value.replace(",", "").replace("$", ""))
    except (ValueError, AttributeError):
        return None


def _to_int(value: str | None) -> int | None:
    f = _to_float(value)
    return int(f) if f is not None else None


def _parse_date_loose(value: str | None) -> datetime | None:
    """Parse common date formats found in both files."""
    if not value:
        return None
    value = value.strip()
    formats = [
        "%Y-%m-%d",        # 2026-05-29
        "%m/%d/%Y",        # 4/27/2026
        "%m/%d/%y",        # 4/27/26
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def detect_format(header: list[str]) -> str:
    """Return 'tradesteward', 'backtick', or raise UnknownFormatError."""
    header_set = {h.strip() for h in header}
    if {"BotName", "Strategy", "OpenDate", "TotalNetProfitLoss"}.issubset(header_set):
        return "tradesteward"
    if {"Position Name", "Entry Date", "Trade P/L", "Backtick Name"}.issubset(header_set):
        return "backtick"
    raise UnknownFormatError(
        f"CSV header does not match TradeSteward or Backtick formats. Got columns: {sorted(header_set)[:10]}..."
    )


def parse_tradesteward(reader: csv.DictReader) -> list[ParsedTrade]:
    trades: list[ParsedTrade] = []
    for row in reader:
        bot = (row.get("BotName") or "").strip()
        if not bot:
            continue
        entry_date = _parse_date_loose(row.get("OpenDate"))
        if entry_date is None:
            continue
        exit_date = _parse_date_loose(row.get("FinalTradeClosedDate"))
        pl = _to_float(row.get("TotalNetProfitLoss"))
        if pl is None:
            continue
        strategy = (row.get("Strategy") or "").strip() or None
        win = 1 if pl > 0 else (0 if pl < 0 else None)
        trades.append(ParsedTrade(
            bot_name=bot,
            strategy=strategy,
            entry_date=entry_date,
            exit_date=exit_date,
            pl=pl,
            win_loss=win,
            buying_power=_to_float(row.get("BuyingPower")),
            contracts=None,  # TradeSteward doesn't expose a portfolio-level contract count
            account_num=(row.get("AccountNum") or "").strip() or None,
        ))
    return trades


def parse_backtick(reader: csv.DictReader) -> list[ParsedTrade]:
    trades: list[ParsedTrade] = []
    for row in reader:
        # Position Name is the per-bot key, NOT Backtick Name (which is the whole backtest's label).
        bot = (row.get("Position Name") or "").strip()
        if not bot:
            continue
        entry_date = _parse_date_loose(row.get("Entry Date"))
        if entry_date is None:
            continue
        pl = _to_float(row.get("Trade P/L"))
        if pl is None:
            continue
        win_loss_str = (row.get("Win / Loss") or "").strip()
        if win_loss_str in ("1", "Win", "win", "W"):
            win = 1
        elif win_loss_str in ("0", "Loss", "loss", "L", "-1"):
            win = 0
        else:
            win = 1 if pl > 0 else (0 if pl < 0 else None)
        trades.append(ParsedTrade(
            bot_name=bot,
            strategy=None,  # backtick doesn't carry a strategy grouping; service backfills from live
            entry_date=entry_date,
            exit_date=_parse_date_loose(row.get("Exit Date")),
            pl=pl,
            win_loss=win,
            buying_power=_to_float(row.get("Buying Power")),
            contracts=_to_int(row.get("Quantity")),
            account_num=None,
        ))
    return trades


def parse_csv(content: bytes | str, filename: str | None = None) -> ParseResult:
    """Parse a CSV blob and return trades + detected format + period bounds."""
    if isinstance(content, bytes):
        # Some exports include a UTF-8 BOM
        text = content.decode("utf-8-sig", errors="replace")
    else:
        text = content

    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames is None:
        raise UnknownFormatError("CSV has no header row")

    fmt = detect_format(list(reader.fieldnames))
    trades = parse_tradesteward(reader) if fmt == "tradesteward" else parse_backtick(reader)

    if not trades:
        return ParseResult(source_format=fmt, trades=[], period_start=None, period_end=None)

    period_start = min(t.entry_date for t in trades)
    period_end = max((t.exit_date or t.entry_date) for t in trades)
    logger.info(f"Parsed {len(trades)} trades from {filename or 'CSV'} as {fmt} format")
    return ParseResult(
        source_format=fmt,
        trades=trades,
        period_start=period_start,
        period_end=period_end,
    )
