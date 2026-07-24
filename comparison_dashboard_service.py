"""
Performance-dashboard data service for the Live vs Backtest feature.

Reads the user's uploaded comparison trades (from the DB) and produces the
compact, trade-level JSON payload consumed by the standalone dashboard page
(frontend/public/comparison-dashboard.html). All metric/drift math happens
client-side in that page so the capital slider and mapping overrides recompute
live; this module only shapes the data and resolves the bot->strategy mapping.

Bot->strategy resolution tiers (backtest bots have no strategy of their own):
  1. exact        - backtest Position Name == a live BotName -> inherit strategy
  2. containment  - a live strategy name appears inside the bot name
  3. manual       - curated presets (see MANUAL_MAP)
  4. fuzzy        - token-overlap match (singular/plural tolerant)
  5. self         - fall back to the bot's own name, timestamps stripped
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from comparison_service import build_strategy_lookup_from_live

CAPITAL_DEFAULT = 500_000.0
RF_ANNUAL = 0.043
TRADING_DAYS = 252
RECENT_WEEK_DAYS = 7
RECENT_MONTH_DAYS = 30

# Curated presets for bots that don't resolve via the automatic tiers.
# Only fire when those exact backtest bot names are present; harmless otherwise.
MANUAL_MAP = {
    "Afternoon NonSMA VIX all SMA>7": "Afternoon NonSMA Condor",
    "Afternoon SMA Condor 1:48 Boost": "Afternoon SMA Condors",
    "EOM EOD Strangle": "EOM EOD Straddle",
    "Put Spread Hedge ATM 20w 1:25 VIX>17": "Put Spread Hedge ATM 20w 1:55",
    "RIC 1DTE Below SMA": "RIC Below SMA",
    "RoD EMA Skewed Condor - 1:17 Delta": "RoD EMA Skewed Condors",
    "Call Hedge 36D SPX>0 11:05": "Hedges",
    "Call Hedge 36D SPX>0 11:05 4.5min": "Hedges",
    "EOD Call Butterfly Hedge": "Hedges",
    "EOD Put Butterfly Hedge": "Hedges",
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def strip_timestamps(name: str) -> str:
    """Remove time-of-day stamps like '10:30', '1:57' from a bot name."""
    s = re.sub(r"\b\d{1,2}:\d{2}\b", "", str(name))
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip(" -[]") or str(name).strip()


def _fuzzy_match(bot: str, live_strats: list[str]) -> str | None:
    """Token-overlap match to a strategy family, singular/plural tolerant."""
    def stem(x: str) -> str:
        return x[:-1] if x.endswith("s") and len(x) > 3 else x

    bt_tokens = {t for t in re.findall(r"[a-z0-9]+", bot.lower()) if not t.isdigit()}
    bt_stems = {stem(t) for t in bt_tokens}
    best, best_score = None, 0.0
    for s in live_strats:
        s_tokens = {t for t in re.findall(r"[a-z0-9]+", s.lower()) if not t.isdigit()}
        s_stems = {stem(t) for t in s_tokens}
        if len(s_stems) < 2:
            continue
        covered = len(s_stems & bt_stems) / len(s_stems)
        if covered >= 0.85:
            score = covered * len(s_stems)
            if score > best_score:
                best, best_score = s, score
    return best


def build_bot_strategy_mapping(
    bt_bots: list[str],
    strategy_lookup: dict[str, str],
    live_strategy_names: set[str],
) -> list[dict]:
    """Return [{bot, strategy, tier}] for every backtest bot."""
    live_strats = sorted(live_strategy_names, key=len, reverse=True)
    norm_strats = [(s, _norm(s)) for s in live_strats]
    rows: list[dict] = []
    for bot in sorted(set(bt_bots)):
        if bot in strategy_lookup:
            rows.append({"bot": bot, "strategy": strategy_lookup[bot], "tier": "exact"})
            continue
        nb = _norm(bot)
        contained = next((s for s, ns in norm_strats if len(ns) >= 5 and ns in nb), None)
        if contained:
            rows.append({"bot": bot, "strategy": contained, "tier": "containment"})
            continue
        if bot in MANUAL_MAP:
            rows.append({"bot": bot, "strategy": MANUAL_MAP[bot], "tier": "manual"})
            continue
        fz = _fuzzy_match(bot, live_strats)
        if fz:
            rows.append({"bot": bot, "strategy": fz, "tier": "fuzzy"})
            continue
        rows.append({"bot": bot, "strategy": strip_timestamps(bot), "tier": "self"})
    return rows


def _compact(trades, base: datetime, with_strategy_index: dict | None = None):
    """Build parallel arrays: bot index, (strategy index), day offset, pl."""
    out_bot, out_day, out_pl = [], [], []
    out_strat = [] if with_strategy_index is not None else None
    base_d = base.date()
    # stable bot index
    bot_names = sorted({t.bot_name for t in trades})
    bot_idx = {b: i for i, b in enumerate(bot_names)}
    for t in sorted(trades, key=lambda x: x.entry_date):
        out_bot.append(bot_idx[t.bot_name])
        out_day.append((t.entry_date.date() - base_d).days)
        out_pl.append(round(float(t.pl), 2))
        if out_strat is not None:
            out_strat.append(with_strategy_index.get(t.strategy, -1) if t.strategy else -1)
    arrays = {"bot": out_bot, "day": out_day, "pl": out_pl}
    if out_strat is not None:
        arrays["strat"] = out_strat
    return bot_names, arrays


def build_dashboard_payload(live_trades: list, bt_trades: list) -> dict:
    """Shape live + backtest trades into the dashboard's compact JSON payload."""
    strategy_lookup = build_strategy_lookup_from_live(live_trades)
    live_strategy_names = {t.strategy for t in live_trades if t.strategy}

    bt_bots = [t.bot_name for t in bt_trades]
    mapping = build_bot_strategy_mapping(bt_bots, strategy_lookup, live_strategy_names)
    tier_counts: dict[str, int] = {}
    for m in mapping:
        tier_counts[m["tier"]] = tier_counts.get(m["tier"], 0) + 1

    base_bt = min(t.entry_date for t in bt_trades)
    base_lv = min(t.entry_date for t in live_trades)
    max_bt = max(t.entry_date for t in bt_trades)
    max_lv = max(t.entry_date for t in live_trades)

    lv_strat_names = sorted(live_strategy_names)
    lv_strat_idx = {s: i for i, s in enumerate(lv_strat_names)}

    bt_bot_names, bt_arrays = _compact(bt_trades, base_bt)
    lv_bot_names, lv_arrays = _compact(live_trades, base_lv, with_strategy_index=lv_strat_idx)

    return {
        "meta": {
            "capital_default": CAPITAL_DEFAULT,
            "rf_annual": RF_ANNUAL,
            "trading_days": TRADING_DAYS,
            "backtest_base_date": base_bt.date().isoformat(),
            "backtest_max_date": max_bt.date().isoformat(),
            "live_base_date": base_lv.date().isoformat(),
            "live_max_date": max_lv.date().isoformat(),
            "recent_week_days": RECENT_WEEK_DAYS,
            "recent_month_days": RECENT_MONTH_DAYS,
            "tier_counts": tier_counts,
        },
        "mapping": mapping,
        "backtest": {"bot_names": bt_bot_names, "trades": bt_arrays},
        "live": {"bot_names": lv_bot_names, "strat_names": lv_strat_names, "trades": lv_arrays},
    }
