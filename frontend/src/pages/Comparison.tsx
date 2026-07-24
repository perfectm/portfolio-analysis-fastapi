import React, { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
  useTheme,
} from "@mui/material";
import {
  CloudUpload,
  Delete,
  TrendingDown,
  TrendingFlat,
  TrendingUp,
} from "@mui/icons-material";
import { API_BASE_URL, authAPI } from "../services/api";

type UploadType = "live" | "backtest";

interface UploadInfo {
  id: number;
  upload_type: UploadType;
  source_format: string;
  filename: string;
  period_start: string | null;
  period_end: string | null;
  trade_count: number;
  uploaded_at: string;
}

interface BotMetrics {
  bot_name: string;
  strategy: string | null;
  trade_count: number;
  total_pl: number;
  avg_pl_per_trade: number;
  win_rate: number;
  largest_win: number;
  largest_loss: number;
  profit_factor: number | null;
}

interface LvBRow {
  bot_name: string;
  strategy: string | null;
  presence: "both" | "live_only" | "backtest_only";
  live: BotMetrics | null;
  backtest: BotMetrics | null;
  pl_per_trade_deviation: number | null;
  win_rate_deviation: number | null;
  overall_deviation: number | null;
  match_quality: "green" | "yellow" | "red" | "gray";
}

interface RvHRow {
  bot_name: string;
  strategy: string | null;
  recent: BotMetrics | null;
  historical: BotMetrics | null;
  pl_per_trade_trend: "improving" | "stable" | "degrading" | "no_data";
  win_rate_trend: "improving" | "stable" | "degrading" | "no_data";
}

interface Alignment {
  applied: boolean;
  live_start: string | null;
  backtest_trades_excluded: number;
}

type ViewMode = "live_vs_backtest" | "recent_vs_history";

const fmtCurrency = (v: number | null | undefined) => {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
};
const fmtPct = (v: number | null | undefined, digits = 1) => {
  if (v === null || v === undefined) return "—";
  return `${(v * 100).toFixed(digits)}%`;
};

const matchColor = (q: LvBRow["match_quality"], theme: any) => {
  switch (q) {
    case "green":
      return theme.palette.success.main;
    case "yellow":
      return theme.palette.warning.main;
    case "red":
      return theme.palette.error.main;
    default:
      return theme.palette.text.disabled;
  }
};

const TrendIcon = ({ trend }: { trend: RvHRow["pl_per_trade_trend"] }) => {
  if (trend === "improving") return <TrendingUp color="success" fontSize="small" />;
  if (trend === "degrading") return <TrendingDown color="error" fontSize="small" />;
  if (trend === "stable") return <TrendingFlat color="warning" fontSize="small" />;
  return <TrendingFlat color="disabled" fontSize="small" />;
};

async function authedFetch(path: string, init: RequestInit = {}) {
  const token = authAPI.getToken();
  const headers: HeadersInit = {
    ...(init.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || body.error || detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json();
}

const Comparison: React.FC = () => {
  const theme = useTheme();
  const [status, setStatus] = useState<{ live: UploadInfo | null; backtest: UploadInfo | null }>({
    live: null,
    backtest: null,
  });
  const [viewMode, setViewMode] = useState<ViewMode>("live_vs_backtest");
  const [lvbRows, setLvbRows] = useState<LvBRow[]>([]);
  const [alignment, setAlignment] = useState<Alignment | null>(null);
  const [rvhRows, setRvhRows] = useState<RvHRow[]>([]);
  const [recentWindow, setRecentWindow] = useState<number>(30);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState<UploadType | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("");
  const [filterQuality, setFilterQuality] = useState<string>("all");

  const refreshStatus = async () => {
    try {
      const data = await authedFetch("/api/comparison/status");
      setStatus({ live: data.live, backtest: data.backtest });
    } catch (e: any) {
      setError(e.message);
    }
  };

  const loadLvB = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await authedFetch("/api/comparison/live-vs-backtest");
      setLvbRows(data.rows || []);
      setAlignment(data.alignment || null);
    } catch (e: any) {
      setError(e.message);
      setLvbRows([]);
      setAlignment(null);
    } finally {
      setLoading(false);
    }
  };

  const loadRvH = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await authedFetch(
        `/api/comparison/recent-vs-history?recent_window_days=${recentWindow}`
      );
      setRvhRows(data.rows || []);
    } catch (e: any) {
      setError(e.message);
      setRvhRows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshStatus();
  }, []);

  useEffect(() => {
    if (!status.live && !status.backtest) return;
    if (viewMode === "live_vs_backtest") loadLvB();
    else loadRvH();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewMode, recentWindow, status.live?.id, status.backtest?.id]);

  const handleUpload = async (type: UploadType, file: File) => {
    setUploading(type);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("upload_type", type);
      await authedFetch("/api/comparison/upload", { method: "POST", body: fd });
      await refreshStatus();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUploading(null);
    }
  };

  const handleDelete = async (type: UploadType) => {
    if (!window.confirm(`Delete the ${type} upload?`)) return;
    try {
      await authedFetch(`/api/comparison/upload/${type}`, { method: "DELETE" });
      await refreshStatus();
      setLvbRows([]);
      setRvhRows([]);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const filteredLvB = useMemo(() => {
    const f = filter.toLowerCase();
    return lvbRows.filter((r) => {
      if (filterQuality !== "all" && r.match_quality !== filterQuality) return false;
      if (!f) return true;
      return (
        r.bot_name.toLowerCase().includes(f) ||
        (r.strategy || "").toLowerCase().includes(f)
      );
    });
  }, [lvbRows, filter, filterQuality]);

  const filteredRvH = useMemo(() => {
    const f = filter.toLowerCase();
    return rvhRows.filter((r) => {
      if (!f) return true;
      return (
        r.bot_name.toLowerCase().includes(f) ||
        (r.strategy || "").toLowerCase().includes(f)
      );
    });
  }, [rvhRows, filter]);

  const lvbSummary = useMemo(() => {
    const s = { green: 0, yellow: 0, red: 0, gray: 0, both: 0, live_only: 0, backtest_only: 0 };
    lvbRows.forEach((r) => {
      s[r.match_quality] = (s[r.match_quality] || 0) + 1;
      s[r.presence] = (s[r.presence] || 0) + 1;
    });
    return s;
  }, [lvbRows]);

  const rvhSummary = useMemo(() => {
    const s = { improving: 0, stable: 0, degrading: 0, no_data: 0 };
    rvhRows.forEach((r) => {
      s[r.pl_per_trade_trend] = (s[r.pl_per_trade_trend] || 0) + 1;
    });
    return s;
  }, [rvhRows]);

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Typography
        variant="h3"
        sx={{
          fontWeight: 700,
          mb: 1,
          background: `linear-gradient(135deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
          backgroundClip: "text",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
        }}
      >
        Live vs Backtest Comparison
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
        Upload TradeSteward live performance logs and Backtick backtest exports to compare
        per-bot performance. Each new upload replaces the previous one of the same type.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Upload zone */}
      <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ mb: 3 }}>
        {(["live", "backtest"] as UploadType[]).map((type) => {
          const info = status[type];
          const label = type === "live" ? "Live (TradeSteward)" : "Backtest (Backtick)";
          return (
            <Paper key={type} sx={{ p: 2, flex: 1 }} elevation={2}>
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Typography variant="h6">{label}</Typography>
                <Chip
                  label={info ? `${info.trade_count} trades` : "no upload"}
                  size="small"
                  color={info ? "primary" : "default"}
                />
              </Stack>
              {info ? (
                <Box sx={{ mt: 1 }}>
                  <Typography variant="body2">{info.filename}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {info.period_start?.slice(0, 10)} → {info.period_end?.slice(0, 10)}
                  </Typography>
                </Box>
              ) : (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  Drop a {type === "live" ? "TradeSteward performance log" : "Backtick CSV export"} here.
                </Typography>
              )}
              <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
                <Button
                  component="label"
                  variant="contained"
                  startIcon={uploading === type ? <CircularProgress size={18} /> : <CloudUpload />}
                  disabled={uploading !== null}
                  size="small"
                >
                  {info ? "Replace" : "Upload"}
                  <input
                    type="file"
                    accept=".csv"
                    hidden
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) handleUpload(type, f);
                      e.target.value = "";
                    }}
                  />
                </Button>
                {info && (
                  <Button
                    variant="outlined"
                    color="error"
                    size="small"
                    startIcon={<Delete />}
                    onClick={() => handleDelete(type)}
                  >
                    Remove
                  </Button>
                )}
              </Stack>
            </Paper>
          );
        })}
      </Stack>

      {/* View mode toggle */}
      <Paper sx={{ p: 2, mb: 2 }} elevation={1}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems="center">
          <FormControl size="small" sx={{ minWidth: 240 }}>
            <InputLabel>Comparison</InputLabel>
            <Select
              label="Comparison"
              value={viewMode}
              onChange={(e) => setViewMode(e.target.value as ViewMode)}
            >
              <MenuItem value="live_vs_backtest">Live vs Backtest (per bot)</MenuItem>
              <MenuItem value="recent_vs_history">Recent vs Historical (live data)</MenuItem>
            </Select>
          </FormControl>

          {viewMode === "recent_vs_history" && (
            <TextField
              size="small"
              label="Recent window (days)"
              type="number"
              value={recentWindow}
              onChange={(e) => setRecentWindow(Math.max(1, parseInt(e.target.value) || 30))}
              sx={{ width: 180 }}
            />
          )}

          <TextField
            size="small"
            label="Filter bot or strategy"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            sx={{ minWidth: 240 }}
          />

          {viewMode === "live_vs_backtest" && (
            <FormControl size="small" sx={{ minWidth: 180 }}>
              <InputLabel>Quality</InputLabel>
              <Select
                label="Quality"
                value={filterQuality}
                onChange={(e) => setFilterQuality(e.target.value)}
              >
                <MenuItem value="all">All</MenuItem>
                <MenuItem value="green">Green (&lt;15%)</MenuItem>
                <MenuItem value="yellow">Yellow (15-30%)</MenuItem>
                <MenuItem value="red">Red (&gt;30%)</MenuItem>
                <MenuItem value="gray">Gray (no data)</MenuItem>
              </Select>
            </FormControl>
          )}

          <Box sx={{ flex: 1 }} />

          {viewMode === "live_vs_backtest" ? (
            <Stack direction="row" spacing={1}>
              <Chip label={`Both: ${lvbSummary.both}`} size="small" />
              <Chip label={`Live only: ${lvbSummary.live_only}`} size="small" />
              <Chip label={`Backtest only: ${lvbSummary.backtest_only}`} size="small" />
              <Divider orientation="vertical" flexItem />
              <Chip label={`🟢 ${lvbSummary.green}`} size="small" />
              <Chip label={`🟡 ${lvbSummary.yellow}`} size="small" />
              <Chip label={`🔴 ${lvbSummary.red}`} size="small" />
            </Stack>
          ) : (
            <Stack direction="row" spacing={1}>
              <Chip label={`Improving: ${rvhSummary.improving}`} size="small" color="success" />
              <Chip label={`Stable: ${rvhSummary.stable}`} size="small" />
              <Chip label={`Degrading: ${rvhSummary.degrading}`} size="small" color="error" />
              <Chip label={`No baseline: ${rvhSummary.no_data}`} size="small" />
            </Stack>
          )}
        </Stack>
      </Paper>

      {loading && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {!loading && viewMode === "live_vs_backtest" && alignment?.applied && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Backtest aligned to the live start date
          {alignment.live_start ? ` (${alignment.live_start.slice(0, 10)})` : ""}
          {alignment.backtest_trades_excluded > 0
            ? ` — ${alignment.backtest_trades_excluded} earlier backtest trade${
                alignment.backtest_trades_excluded === 1 ? "" : "s"
              } excluded so both sides cover the same window.`
            : " — no earlier backtest trades to exclude."}
        </Alert>
      )}

      {!loading && viewMode === "live_vs_backtest" && (
        <TableContainer component={Paper}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 700 }}>Bot</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Strategy</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">Live #</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">Live Avg P/L</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">Live Win%</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">Live Total P/L</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">BT #</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">BT Avg P/L</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">BT Win%</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">BT Total P/L</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">
                  <Tooltip title="Worst of avg P/L per trade deviation and win rate deviation, both as % of backtest value">
                    <span>Deviation</span>
                  </Tooltip>
                </TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="center">Match</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredLvB.map((r) => {
                const color = matchColor(r.match_quality, theme);
                return (
                  <TableRow key={r.bot_name} hover>
                    <TableCell>{r.bot_name}</TableCell>
                    <TableCell>
                      <Typography variant="caption" color="text.secondary">
                        {r.strategy || "—"}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">{r.live?.trade_count ?? "—"}</TableCell>
                    <TableCell align="right">{fmtCurrency(r.live?.avg_pl_per_trade)}</TableCell>
                    <TableCell align="right">{fmtPct(r.live?.win_rate)}</TableCell>
                    <TableCell align="right">{fmtCurrency(r.live?.total_pl)}</TableCell>
                    <TableCell align="right">{r.backtest?.trade_count ?? "—"}</TableCell>
                    <TableCell align="right">{fmtCurrency(r.backtest?.avg_pl_per_trade)}</TableCell>
                    <TableCell align="right">{fmtPct(r.backtest?.win_rate)}</TableCell>
                    <TableCell align="right">{fmtCurrency(r.backtest?.total_pl)}</TableCell>
                    <TableCell align="right">
                      {r.overall_deviation !== null ? `${(r.overall_deviation * 100).toFixed(1)}%` : "—"}
                    </TableCell>
                    <TableCell align="center">
                      <Box
                        sx={{
                          display: "inline-block",
                          width: 14,
                          height: 14,
                          borderRadius: "50%",
                          backgroundColor: color,
                        }}
                      />
                    </TableCell>
                  </TableRow>
                );
              })}
              {filteredLvB.length === 0 && (
                <TableRow>
                  <TableCell colSpan={12} align="center" sx={{ py: 4 }}>
                    <Typography color="text.secondary">
                      No rows to show. Upload a live and backtest CSV to compare.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {!loading && viewMode === "recent_vs_history" && (
        <TableContainer component={Paper}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 700 }}>Bot</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Strategy</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">Recent #</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">Recent Avg P/L</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">Recent Win%</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">Hist #</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">Hist Avg P/L</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">Hist Win%</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="center">
                  <Tooltip title="Z-score on avg P/L per trade: > +1σ improving, < -1σ degrading">
                    <span>P/L Trend</span>
                  </Tooltip>
                </TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="center">
                  <Tooltip title="±5 percentage points on win rate">
                    <span>Win% Trend</span>
                  </Tooltip>
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredRvH.map((r) => (
                <TableRow key={r.bot_name} hover>
                  <TableCell>{r.bot_name}</TableCell>
                  <TableCell>
                    <Typography variant="caption" color="text.secondary">
                      {r.strategy || "—"}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">{r.recent?.trade_count ?? "—"}</TableCell>
                  <TableCell align="right">{fmtCurrency(r.recent?.avg_pl_per_trade)}</TableCell>
                  <TableCell align="right">{fmtPct(r.recent?.win_rate)}</TableCell>
                  <TableCell align="right">{r.historical?.trade_count ?? "—"}</TableCell>
                  <TableCell align="right">{fmtCurrency(r.historical?.avg_pl_per_trade)}</TableCell>
                  <TableCell align="right">{fmtPct(r.historical?.win_rate)}</TableCell>
                  <TableCell align="center">
                    <TrendIcon trend={r.pl_per_trade_trend} />
                  </TableCell>
                  <TableCell align="center">
                    <TrendIcon trend={r.win_rate_trend} />
                  </TableCell>
                </TableRow>
              ))}
              {filteredRvH.length === 0 && (
                <TableRow>
                  <TableCell colSpan={10} align="center" sx={{ py: 4 }}>
                    <Typography color="text.secondary">
                      No rows to show. Upload a live CSV to enable the recent-vs-history view.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Container>
  );
};

export default Comparison;
