import React from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CalendarClock,
  CheckCircle2,
  Database,
  Download,
  FileCheck2,
  LineChart,
  ListChecks,
  Radio,
  RefreshCw,
  Search,
  ShieldAlert,
  TrendingDown,
  TrendingUp,
  WalletCards
} from "lucide-react";
import "./styles.css";

type Metrics = {
  start: string;
  end: string;
  trading_days: number;
  total_return: number;
  annualized_return: number;
  annualized_volatility: number;
  sharpe_no_risk_free: number;
  max_drawdown: number;
  max_drawdown_peak: string;
  max_drawdown_trough: string;
  calmar: number;
  win_rate_daily: number;
  avg_daily_turnover: number;
  rebalance_count: number;
  avg_holding_count: number;
  benchmark_total_return: number;
  benchmark_annualized_return: number;
  benchmark_annualized_volatility: number;
  benchmark_max_drawdown: number;
};

type CsvRow = Record<string, string>;
type ChartMode = "equity" | "drawdown" | "turnover";
type DetailTab = "rebalance" | "returns";
type MarketChartMode = "daily" | "intraday";
type PreviewMode = "observe" | "cash-only" | "full-account";
type SortDirection = "asc" | "desc";
type PositionSortKey =
  | "name"
  | "market_val"
  | "qty"
  | "average_cost"
  | "current_price"
  | "today_pl_val"
  | "unrealized_pl"
  | "position_percent";
type OrderSortKey = "name" | "side" | "quantity" | "price" | "estimated_value";

type RunMeta = {
  generated_at: string;
  requested_data_source: string;
  actual_data_mode: string;
  is_synthetic: boolean;
  source_status: Record<string, string>;
  warning_count: number;
  error_count: number;
  quality_counts: Record<string, number>;
};

type DataQualityRow = {
  code: string;
  name: string;
  source_status: string;
  status: "ok" | "warning" | "error";
  start_date: string;
  end_date: string;
  row_count: number;
  expected_trading_days: number;
  valid_close_count: number;
  missing_ratio: number;
  extreme_return_count: number;
  duplicate_dates: number;
  warnings: string;
};

type PricePoint = {
  date: string;
  close: number;
  daily_return: number | null;
};

type PriceSeries = Record<
  string,
  {
    code: string;
    name: string;
    points: PricePoint[];
  }
>;

type IntradayPoint = {
  time: string;
  price: number;
};

type IntradaySeries = Record<
  string,
  {
    code: string;
    name: string;
    source: string;
    period: string;
    points: IntradayPoint[];
  }
>;

type MarketSnapshot = {
  generated_at: string;
  source: string;
  warnings: string[];
  items: Array<{
    code: string;
    name: string;
    source: string;
    latest_price: number | null;
    latest_close: number | null;
    prev_close: number | null;
    daily_return: number | null;
    updated_at: string;
  }>;
};

type TradeSignal = {
  generated_at: string;
  signal_date: string;
  suggested_rebalance_date: string;
  data_mode: string;
  trading_env: string;
  market: string;
  selected: string[];
  targets: Array<{
    code: string;
    futu_code: string;
    name: string;
    target_weight: number;
    latest_price: number | null;
    selected: boolean;
  }>;
};

type FutuAccount = {
  acc_id: number;
  acc_type: string;
  acc_role: string;
  trd_env: string;
  security_firm: string;
  trdmarket_auth: string[];
  sim_acc_type?: string;
  competition_acc_name?: string;
};

type FutuSimAccount = {
  generated_at: string;
  ok: boolean;
  host: string;
  port: number;
  sdk_version: string;
  opend_reachable: boolean;
  target_env: string;
  target_market: string;
  selected_account?: FutuAccount | null;
  accounts: FutuAccount[];
  warnings: string[];
  errors: string[];
  message: string;
};

type FutuPosition = {
  code: string;
  name: string;
  qty: number;
  can_sell_qty: number;
  average_cost: number;
  nominal_price: number;
  current_price: number;
  prev_close: number;
  market_val: number;
  unrealized_pl: number;
  pl_ratio_avg_cost: number;
  today_pl_val: number;
  today_pl_ratio: number;
  position_percent: number;
};

type FutuSimPositions = {
  generated_at: string;
  funds: Record<string, number | string>;
  positions: FutuPosition[];
};

type FutuSimOrder = {
  code: string;
  local_code: string;
  name: string;
  side: "BUY" | "SELL" | "HOLD";
  quantity: number;
  price: number;
  order_type: string;
  target_weight: number;
  current_qty: number;
  can_sell_qty: number;
  current_value: number;
  target_value: number;
  estimated_value: number;
};

type FutuSimOrderPreview = {
  generated_at: string;
  account: FutuAccount;
  trade_signal: {
    generated_at: string;
    signal_date: string;
    suggested_rebalance_date: string;
    data_mode: string;
  };
  funds: Record<string, number | string>;
  mode?: {
    selected: PreviewMode;
    label: string;
    notes: string[];
  };
  positions: FutuPosition[];
  summary: {
    total_assets: number;
    available_funds: number;
    reserved_cash: number;
    sell_value: number;
    buy_value: number;
    gross_order_value: number;
    order_count: number;
  };
  risk: {
    status: "pass" | "blocked";
    errors: string[];
    warnings: string[];
    rules: Record<string, number | string>;
  };
  orders: FutuSimOrder[];
};

type FutuOrderSnapshot = {
  generated_at?: string;
  market?: string;
  orders?: Array<{
    order_id: string;
    code: string;
    side: string;
    status: string;
    qty: number;
    price: number;
    dealt_qty: number;
    dealt_avg_price: number;
  }>;
};

type FutuLastExecution = {
  generated_at: string;
  ok: boolean;
  submitted_count: number;
  failed_count: number;
};

type LinePoint = {
  label: string;
  value: number;
};

const AUTO_REFRESH_INTERVAL_MS = 5000;

const ETF_NAMES: Record<string, string> = {
  "510300": "沪深300ETF",
  "510500": "中证500ETF",
  "159915": "创业板ETF",
  "510880": "红利ETF",
  "518880": "黄金ETF",
  "513100": "纳指ETF",
  "513180": "恒生科技ETF",
  "511010": "国债ETF"
};

function parseCsv(text: string): CsvRow[] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;

  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    const next = text[i + 1];

    if (quoted) {
      if (ch === '"' && next === '"') {
        field += '"';
        i += 1;
      } else if (ch === '"') {
        quoted = false;
      } else {
        field += ch;
      }
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === ",") {
      row.push(field);
      field = "";
    } else if (ch === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else if (ch !== "\r") {
      field += ch;
    }
  }

  if (field.length > 0 || row.length > 0) {
    row.push(field);
    rows.push(row);
  }

  const headers = rows.shift() ?? [];
  return rows
    .filter((cells) => cells.some(Boolean))
    .map((cells) => {
      const item: CsvRow = {};
      headers.forEach((header, index) => {
        item[header || "date"] = cells[index] ?? "";
      });
      return item;
    });
}

async function loadDashboardData() {
  const [
    metrics,
    meta,
    dataQuality,
    priceSeries,
    intradaySeries,
    marketSnapshot,
    equityText,
    weightsText,
    rebalanceText,
    tradeSignal,
    futuSimAccount,
    futuSimPositions,
    futuSimOrderPreview,
    futuSimRecentOrders,
    futuSimLastExecution
  ] =
    await Promise.all([
    fetchFresh("/output/metrics.json").then((res) => res.json() as Promise<Metrics>),
    fetchFresh("/output/run_meta.json").then((res) => res.json() as Promise<RunMeta>),
    fetchFresh("/output/data_quality.json").then((res) => res.json() as Promise<DataQualityRow[]>),
    fetchFresh("/output/price_series.json").then((res) => res.json() as Promise<PriceSeries>),
    fetchFresh("/output/intraday_series.json").then((res) => res.json() as Promise<IntradaySeries>),
    fetchFresh("/output/market_snapshot.json").then((res) => res.json() as Promise<MarketSnapshot>),
    fetchFresh("/output/equity_curve.csv").then((res) => res.text()),
    fetchFresh("/output/daily_weights.csv").then((res) => res.text()),
    fetchFresh("/output/rebalance_log.csv").then((res) => res.text()),
    optionalJson<TradeSignal>("/output/trade_signal.json", null),
    optionalJson<FutuSimAccount>("/output/futu_sim_account.json", null),
    optionalJson<FutuSimPositions>("/output/futu_sim_positions.json", null),
    optionalJson<FutuSimOrderPreview>("/output/futu_sim_order_preview.json", null),
    optionalJson<FutuOrderSnapshot>("/output/futu_sim_recent_orders.json", null),
    optionalJson<FutuLastExecution>("/output/futu_sim_last_execution.json", null)
  ]);

  return {
    metrics,
    meta,
    dataQuality,
    priceSeries,
    intradaySeries,
    marketSnapshot,
    equity: parseCsv(equityText),
    weights: parseCsv(weightsText),
    rebalances: parseCsv(rebalanceText),
    tradeSignal,
    futuSimAccount,
    futuSimPositions,
    futuSimOrderPreview,
    futuSimRecentOrders,
    futuSimLastExecution
  };
}

function cacheBustUrl(url: string) {
  return `${url}${url.includes("?") ? "&" : "?"}_=${Date.now()}`;
}

function fetchFresh(url: string, init?: RequestInit) {
  return fetch(cacheBustUrl(url), { cache: "no-store", ...init });
}

async function optionalJson<T>(url: string, fallback: T | null): Promise<T | null> {
  const res = await fetchFresh(url);
  if (!res.ok) return fallback;
  return res.json() as Promise<T>;
}

function pct(value: number | string | undefined) {
  const num = Number(value);
  return Number.isFinite(num) ? `${(num * 100).toFixed(2)}%` : "--";
}

function num(value: number | string | undefined, digits = 2) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toFixed(digits) : "--";
}

function tone(value: number | string | undefined) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "";
  return parsed >= 0 ? "positive" : "negative";
}

function cnTone(value: number | string | undefined) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "";
  return parsed >= 0 ? "cn-positive" : "cn-negative";
}

function pctPoint(value: number | string | undefined) {
  const numValue = Number(value);
  return Number.isFinite(numValue) ? `${numValue.toFixed(3)}%` : "--";
}

function selectedLabel(value: string) {
  if (!value || value === "CASH") return "CASH";
  return value
    .split(",")
    .map((code) => `${code} ${ETF_NAMES[code] ?? ""}`.trim())
    .join(" / ");
}

function dataModeLabel(mode: string) {
  if (mode === "akshare") return "真实 AkShare";
  if (mode === "cached") return "本地缓存";
  if (mode === "synthetic") return "Synthetic 实验数据";
  return mode || "--";
}

function statusLabel(status: string) {
  if (status === "ok") return "正常";
  if (status === "warning") return "警告";
  if (status === "error") return "错误";
  return status || "--";
}

function marketSourceLabel(source: string) {
  if (source === "akshare_minute") return "AkShare 分钟线";
  if (source === "akshare_minute_mixed") return "AkShare/日线派生混合";
  if (source === "derived_from_daily") return "日线派生";
  return source || "--";
}

function orderSideLabel(side: string) {
  if (side === "BUY") return "买入";
  if (side === "SELL") return "卖出";
  return side || "--";
}

function SortHeader<T extends string>({
  label,
  field,
  activeField,
  direction,
  onSort
}: {
  label: string;
  field: T;
  activeField: T;
  direction: SortDirection;
  onSort: (field: T) => void;
}) {
  const active = field === activeField;
  return (
    <button type="button" className={`sort-header ${active ? "active" : ""}`} onClick={() => onSort(field)}>
      {label}
      <span>{active ? (direction === "asc" ? "▲" : "▼") : "↕"}</span>
    </button>
  );
}

function sortedPositions(rows: FutuPosition[], key: PositionSortKey, direction: SortDirection) {
  const copy = [...rows];
  copy.sort((a, b) => compareValues(positionSortValue(a, key), positionSortValue(b, key), direction));
  return copy;
}

function positionSortValue(row: FutuPosition, key: PositionSortKey): string | number {
  if (key === "name") return row.name || row.code;
  return Number(row[key] ?? 0);
}

function sortedOrders(rows: FutuSimOrder[], key: OrderSortKey, direction: SortDirection) {
  const copy = [...rows];
  copy.sort((a, b) => compareValues(orderSortValue(a, key), orderSortValue(b, key), direction));
  return copy;
}

function orderSortValue(row: FutuSimOrder, key: OrderSortKey): string | number {
  if (key === "name") return row.name || row.code;
  if (key === "side") return row.side;
  return Number(row[key] ?? 0);
}

function compareValues(a: string | number, b: string | number, direction: SortDirection) {
  let result = 0;
  if (typeof a === "string" || typeof b === "string") {
    result = String(a).localeCompare(String(b), "zh-Hans-CN");
  } else {
    result = a - b;
  }
  return direction === "asc" ? result : -result;
}

function drawdown(values: number[]) {
  let peak = values[0] || 1;
  return values.map((value) => {
    peak = Math.max(peak, value);
    return value / peak - 1;
  });
}

function toSeries(equity: CsvRow[], mode: ChartMode) {
  if (mode === "equity") {
    return [
      {
        name: "策略",
        color: "#2563eb",
        values: equity.map((row) => Number(row.strategy))
      },
      {
        name: "等权基准",
        color: "#0f766e",
        values: equity.map((row) => Number(row.benchmark_equal_weight))
      }
    ];
  }

  if (mode === "drawdown") {
    return [
      {
        name: "策略回撤",
        color: "#b42318",
        values: drawdown(equity.map((row) => Number(row.strategy)))
      },
      {
        name: "基准回撤",
        color: "#b7791f",
        values: drawdown(equity.map((row) => Number(row.benchmark_equal_weight)))
      }
    ];
  }

  return [
    {
      name: "每日换手",
      color: "#2563eb",
      values: equity.map((row) => Number(row.turnover))
    }
  ];
}

function SvgChart({ equity, mode }: { equity: CsvRow[]; mode: ChartMode }) {
  const width = 980;
  const height = 390;
  const pad = { left: 58, right: 18, top: 22, bottom: 42 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const series = toSeries(equity, mode);
  const allValues = series.flatMap((item) => item.values).filter(Number.isFinite);
  const rawMin = Math.min(...allValues);
  const rawMax = Math.max(...allValues);
  const spread = rawMax === rawMin ? 1 : rawMax - rawMin;
  const min = rawMin - spread * 0.08;
  const max = rawMax + spread * 0.08;

  const xFor = (index: number) => pad.left + (plotWidth * index) / Math.max(1, equity.length - 1);
  const yFor = (value: number) => pad.top + plotHeight - ((value - min) / (max - min)) * plotHeight;

  const lines = series.map((item) => ({
    ...item,
    path: item.values
      .map((value, index) => `${index === 0 ? "M" : "L"} ${xFor(index).toFixed(2)} ${yFor(value).toFixed(2)}`)
      .join(" ")
  }));

  const yTicks = Array.from({ length: 6 }, (_, index) => {
    const value = max - ((max - min) * index) / 5;
    return {
      y: pad.top + (plotHeight * index) / 5,
      label: mode === "equity" ? value.toFixed(2) : pct(value)
    };
  });

  const xTicks = Array.from({ length: 6 }, (_, index) => {
    const dataIndex = Math.min(equity.length - 1, Math.round(((equity.length - 1) * index) / 5));
    return {
      x: pad.left + (plotWidth * index) / 5,
      label: (equity[dataIndex]?.date ?? "").slice(0, 7)
    };
  });

  return (
    <svg className="chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="backtest chart">
      <rect x="0" y="0" width={width} height={height} fill="#fff" />
      {yTicks.map((tick) => (
        <g key={tick.y}>
          <line x1={pad.left} y1={tick.y} x2={pad.left + plotWidth} y2={tick.y} stroke="#e5eaf0" />
          <text x={pad.left - 10} y={tick.y + 4} textAnchor="end" className="axis-label">
            {tick.label}
          </text>
        </g>
      ))}
      {xTicks.map((tick) => (
        <text key={tick.x} x={tick.x} y={pad.top + plotHeight + 25} textAnchor="middle" className="axis-label">
          {tick.label}
        </text>
      ))}
      {lines.map((line) => (
        <path key={line.name} d={line.path} fill="none" stroke={line.color} strokeWidth="2.5" />
      ))}
      <g transform={`translate(${pad.left + 8}, ${pad.top + 4})`}>
        {series.map((item, index) => (
          <g key={item.name} transform={`translate(${index * 110}, 0)`}>
            <rect x="0" y="0" width="20" height="4" fill={item.color} rx="2" />
            <text x="28" y="5" className="legend-label">
              {item.name}
            </text>
          </g>
        ))}
      </g>
    </svg>
  );
}

function PriceChart({ points }: { points: LinePoint[] }) {
  const width = 980;
  const height = 330;
  const pad = { left: 58, right: 18, top: 22, bottom: 42 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const values = points.map((point) => point.value).filter(Number.isFinite);
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const spread = rawMax === rawMin ? 1 : rawMax - rawMin;
  const min = rawMin - spread * 0.08;
  const max = rawMax + spread * 0.08;

  const xFor = (index: number) => pad.left + (plotWidth * index) / Math.max(1, points.length - 1);
  const yFor = (value: number) => pad.top + plotHeight - ((value - min) / (max - min)) * plotHeight;
  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${xFor(index).toFixed(2)} ${yFor(point.value).toFixed(2)}`)
    .join(" ");
  const yTicks = Array.from({ length: 5 }, (_, index) => {
    const value = max - ((max - min) * index) / 4;
    return {
      y: pad.top + (plotHeight * index) / 4,
      label: value.toFixed(2)
    };
  });
  const xTicks = Array.from({ length: 5 }, (_, index) => {
    const dataIndex = Math.min(points.length - 1, Math.round(((points.length - 1) * index) / 4));
    return {
      x: pad.left + (plotWidth * index) / 4,
      label: points[dataIndex]?.label ?? ""
    };
  });

  return (
    <svg className="price-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="etf price chart">
      <rect x="0" y="0" width={width} height={height} fill="#fff" />
      {yTicks.map((tick) => (
        <g key={tick.y}>
          <line x1={pad.left} y1={tick.y} x2={pad.left + plotWidth} y2={tick.y} stroke="#e5eaf0" />
          <text x={pad.left - 10} y={tick.y + 4} textAnchor="end" className="axis-label">
            {tick.label}
          </text>
        </g>
      ))}
      {xTicks.map((tick) => (
        <text key={tick.x} x={tick.x} y={pad.top + plotHeight + 25} textAnchor="middle" className="axis-label">
          {tick.label}
        </text>
      ))}
      <path d={path} fill="none" stroke="#2563eb" strokeWidth="2.4" />
    </svg>
  );
}

function SimTradingPanel({
  tradeSignal,
  futuSimAccount,
  futuSimPositions,
  futuSimOrderPreview,
  futuSimRecentOrders,
  futuSimLastExecution,
  previewModeLoading,
  portfolioRefreshing,
  lastPortfolioRefresh,
  portfolioRefreshError,
  onPreviewModeChange
}: {
  tradeSignal: TradeSignal | null;
  futuSimAccount: FutuSimAccount | null;
  futuSimPositions: FutuSimPositions | null;
  futuSimOrderPreview: FutuSimOrderPreview | null;
  futuSimRecentOrders: FutuOrderSnapshot | null;
  futuSimLastExecution: FutuLastExecution | null;
  previewModeLoading: PreviewMode | null;
  portfolioRefreshing: boolean;
  lastPortfolioRefresh: string | null;
  portfolioRefreshError: string | null;
  onPreviewModeChange: (mode: PreviewMode) => void;
}) {
  const account = futuSimAccount?.selected_account;
  const signalTargets = tradeSignal?.targets.filter((item) => item.selected) ?? [];
  const previewOrders = futuSimOrderPreview?.orders ?? [];
  const positions = futuSimPositions?.positions ?? futuSimOrderPreview?.positions ?? [];
  const funds = futuSimPositions?.funds ?? futuSimOrderPreview?.funds ?? {};
  const riskStatus = futuSimOrderPreview?.risk.status ?? "blocked";
  const activePreviewMode = futuSimOrderPreview?.mode?.selected ?? "observe";
  const previewModes: Array<{ key: PreviewMode; label: string; note: string }> = [
    { key: "observe", label: "观察", note: "只看持仓和目标，不生成买卖单" },
    { key: "cash-only", label: "只用现金", note: "只用可用现金买入，不卖出现有持仓" },
    { key: "full-account", label: "全账户", note: "按目标仓位生成买卖调仓计划" }
  ];
  const [positionSort, setPositionSort] = React.useState<{ key: PositionSortKey; direction: SortDirection }>({
    key: "market_val",
    direction: "desc"
  });
  const [orderSort, setOrderSort] = React.useState<{ key: OrderSortKey; direction: SortDirection }>({
    key: "estimated_value",
    direction: "desc"
  });
  const sortedPositionRows = sortedPositions(positions, positionSort.key, positionSort.direction);
  const sortedOrderRows = sortedOrders(previewOrders, orderSort.key, orderSort.direction);
  const togglePositionSort = (key: PositionSortKey) => {
    setPositionSort((current) => ({
      key,
      direction: current.key === key && current.direction === "desc" ? "asc" : "desc"
    }));
  };
  const toggleOrderSort = (key: OrderSortKey) => {
    setOrderSort((current) => ({
      key,
      direction: current.key === key && current.direction === "desc" ? "asc" : "desc"
    }));
  };

  return (
    <section className="panel sim-panel">
      <div className="panel-head">
        <h2>Futu 模拟盘</h2>
        <div className="toolbar-inline">
          <FileCheck2 size={16} />
          <span className="muted">{futuSimAccount?.generated_at ? `预检 ${futuSimAccount.generated_at}` : "尚未预检"}</span>
          <span className="live-dot" aria-hidden="true" />
          <span className="muted">
            {portfolioRefreshing ? "持仓刷新中" : lastPortfolioRefresh ? `持仓刷新 ${lastPortfolioRefresh}` : "5秒自动刷新"}
          </span>
        </div>
      </div>
      {portfolioRefreshError && (
        <div className="market-warning sim-refresh-warning">
          <AlertTriangle size={15} />
          <span>{portfolioRefreshError}</span>
        </div>
      )}
      <div className="sim-grid">
        <article className="sim-card">
          <div className="sim-card-head">
            <span>账户状态</span>
            <span className={`quality-pill ${futuSimAccount?.ok ? "ok" : "warning"}`}>
              {futuSimAccount?.ok ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
              {futuSimAccount?.ok ? "可用" : "待检查"}
            </span>
          </div>
          {account ? (
            <dl className="sim-facts">
              <div><dt>账户</dt><dd>{account.acc_id}</dd></div>
              <div><dt>环境</dt><dd>{account.trd_env}</dd></div>
              <div><dt>券商</dt><dd>{account.security_firm || "--"}</dd></div>
              <div><dt>权限</dt><dd>{account.trdmarket_auth?.join(", ") || "--"}</dd></div>
            </dl>
          ) : (
            <p className="empty-text">{futuSimAccount?.message ?? "运行预检后显示模拟账户。"}</p>
          )}
          {(futuSimAccount?.errors?.length ?? 0) > 0 && <p className="risk-text">{futuSimAccount?.errors[0]}</p>}
        </article>

        <article className="sim-card">
          <div className="sim-card-head">
            <span>账户资金</span>
            <span className="muted">{futuSimPositions?.generated_at ?? futuSimOrderPreview?.generated_at ?? "--"}</span>
          </div>
          <dl className="sim-facts">
            <div><dt>总资产</dt><dd>{num(funds.total_assets)}</dd></div>
            <div><dt>可用资金</dt><dd>{num(funds.available_funds)}</dd></div>
            <div><dt>现金</dt><dd>{num(funds.cash)}</dd></div>
            <div><dt>持仓市值</dt><dd>{num(funds.market_val)}</dd></div>
          </dl>
        </article>

        <article className="sim-card">
          <div className="sim-card-head">
            <span>策略信号</span>
            <span className="muted">{tradeSignal?.signal_date ?? "--"}</span>
          </div>
          {signalTargets.length > 0 ? (
            <div className="signal-list">
              {signalTargets.map((target) => (
                <div key={target.futu_code}>
                  <strong>{target.name}</strong>
                  <span>{target.futu_code}</span>
                  <em>{pct(target.target_weight)}</em>
                </div>
              ))}
            </div>
          ) : (
            <p className="empty-text">当前信号为空仓或尚未生成。</p>
          )}
        </article>

        <article className="sim-card">
          <div className="sim-card-head">
            <span>风控结果</span>
            <span className={`quality-pill ${riskStatus === "pass" ? "ok" : "error"}`}>
              {riskStatus === "pass" ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
              {riskStatus === "pass" ? "通过" : "拦截"}
            </span>
          </div>
          <dl className="sim-facts">
            <div><dt>模式</dt><dd>{futuSimOrderPreview?.mode?.label ?? "未生成"}</dd></div>
            <div><dt>订单数</dt><dd>{futuSimOrderPreview?.summary.order_count ?? 0}</dd></div>
            <div><dt>买入额</dt><dd>{num(futuSimOrderPreview?.summary.buy_value)}</dd></div>
            <div><dt>卖出额</dt><dd>{num(futuSimOrderPreview?.summary.sell_value)}</dd></div>
            <div><dt>现金预留</dt><dd>{num(futuSimOrderPreview?.summary.reserved_cash)}</dd></div>
          </dl>
          {(futuSimOrderPreview?.risk.errors.length ?? 0) > 0 && <p className="risk-text">{futuSimOrderPreview?.risk.errors[0]}</p>}
          {(futuSimOrderPreview?.mode?.notes.length ?? 0) > 0 && <p className="mode-note">{futuSimOrderPreview?.mode?.notes[0]}</p>}
        </article>
      </div>

      <div className="preview-mode-switch">
        <div>
          <strong>预览模式</strong>
          <span>{previewModes.find((item) => item.key === activePreviewMode)?.note ?? "选择一种方式重新生成订单预览"}</span>
        </div>
        <div className="segmented mode-segmented">
          {previewModes.map((mode) => (
            <button
              key={mode.key}
              type="button"
              className={activePreviewMode === mode.key ? "active" : ""}
              disabled={previewModeLoading !== null || portfolioRefreshing}
              onClick={() => onPreviewModeChange(mode.key)}
              title={mode.note}
            >
              {previewModeLoading === mode.key ? "生成中" : mode.label}
            </button>
          ))}
        </div>
      </div>

      <div className="sim-command-row">
        <div>
          <ListChecks size={16} />
          <code>python futu_sim_preflight.py</code>
        </div>
        <div>
          <ListChecks size={16} />
          <code>python generate_futu_sim_orders.py --mode observe</code>
        </div>
        <div>
          <ListChecks size={16} />
          <code>python generate_futu_sim_orders.py --mode cash-only --cash-buffer 0.05</code>
        </div>
        <div>
          <ListChecks size={16} />
          <code>python generate_futu_sim_orders.py --mode full-account --cash-buffer 0.05</code>
        </div>
        <div>
          <ListChecks size={16} />
          <code>python execute_futu_sim_orders.py --confirmed</code>
        </div>
      </div>

      <div className="sim-two-col">
        <div className="table-scroll compact">
          <table className="position-table">
            <thead>
              <tr>
                <th>
                  <SortHeader label="持仓股" field="name" activeField={positionSort.key} direction={positionSort.direction} onSort={togglePositionSort} />
                </th>
                <th>
                  <SortHeader label="市值" field="market_val" activeField={positionSort.key} direction={positionSort.direction} onSort={togglePositionSort} />
                </th>
                <th>
                  <SortHeader label="数量" field="qty" activeField={positionSort.key} direction={positionSort.direction} onSort={togglePositionSort} />
                </th>
                <th>
                  <SortHeader label="成本/现价" field="current_price" activeField={positionSort.key} direction={positionSort.direction} onSort={togglePositionSort} />
                </th>
                <th>
                  <SortHeader label="当日盈亏" field="today_pl_val" activeField={positionSort.key} direction={positionSort.direction} onSort={togglePositionSort} />
                </th>
                <th>
                  <SortHeader label="累计盈亏" field="unrealized_pl" activeField={positionSort.key} direction={positionSort.direction} onSort={togglePositionSort} />
                </th>
                <th>
                  <SortHeader label="个股仓位" field="position_percent" activeField={positionSort.key} direction={positionSort.direction} onSort={togglePositionSort} />
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedPositionRows.length > 0 ? sortedPositionRows.slice(0, 12).map((position) => (
                <tr key={position.code}>
                  <td>
                    <strong>{position.name || position.code}</strong>
                    <span className="cell-sub">{position.code}</span>
                  </td>
                  <td>{num(position.market_val)}</td>
                  <td>{num(position.qty, 0)}</td>
                  <td>
                    <strong>{num(position.average_cost, 3)}</strong>
                    <span className="cell-sub">{num(position.current_price || position.nominal_price, 3)}</span>
                  </td>
                  <td className={cnTone(position.today_pl_val)}>
                    <strong>{num(position.today_pl_val)}</strong>
                    <span className="cell-sub">{pctPoint(position.today_pl_ratio)}</span>
                  </td>
                  <td className={cnTone(position.unrealized_pl)}>
                    <strong>{num(position.unrealized_pl)}</strong>
                    <span className="cell-sub">{pctPoint(position.pl_ratio_avg_cost)}</span>
                  </td>
                  <td>{pctPoint(position.position_percent)}</td>
                </tr>
              )) : (
                <tr><td colSpan={7}>暂无持仓数据</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="table-scroll compact">
          <table className="position-table">
            <thead>
              <tr>
                <th>
                  <SortHeader label="订单" field="name" activeField={orderSort.key} direction={orderSort.direction} onSort={toggleOrderSort} />
                </th>
                <th>
                  <SortHeader label="数量" field="quantity" activeField={orderSort.key} direction={orderSort.direction} onSort={toggleOrderSort} />
                </th>
                <th>
                  <SortHeader label="价格" field="price" activeField={orderSort.key} direction={orderSort.direction} onSort={toggleOrderSort} />
                </th>
                <th>
                  <SortHeader label="金额" field="estimated_value" activeField={orderSort.key} direction={orderSort.direction} onSort={toggleOrderSort} />
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedOrderRows.length > 0 ? sortedOrderRows.map((order) => (
                <tr key={`${order.side}-${order.code}`}>
                  <td>
                    <strong>{orderSideLabel(order.side)} {order.name}</strong>
                    <span className="cell-sub">{order.code}</span>
                  </td>
                  <td>{order.quantity}</td>
                  <td>{num(order.price, 3)}</td>
                  <td>{num(order.estimated_value)}</td>
                </tr>
              )) : (
                <tr><td colSpan={4}>暂无订单预览</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {(futuSimRecentOrders?.orders?.length ?? 0) > 0 && (
        <div className="table-scroll compact sim-orders-table">
          <table>
            <thead>
              <tr>
                <th>今日订单</th>
                <th>状态</th>
                <th>委托</th>
                <th>成交</th>
              </tr>
            </thead>
            <tbody>
              {futuSimRecentOrders?.orders?.slice(0, 12).map((order) => (
                <tr key={order.order_id}>
                  <td>
                    <strong>{orderSideLabel(order.side)} {order.code}</strong>
                    <span className="cell-sub">{order.order_id}</span>
                  </td>
                  <td>{order.status}</td>
                  <td>{num(order.qty, 0)} @ {num(order.price, 3)}</td>
                  <td>{num(order.dealt_qty, 0)} @ {num(order.dealt_avg_price, 3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {futuSimLastExecution && (
        <p className="sim-exec-line">
          最近执行：{futuSimLastExecution.generated_at}，提交 {futuSimLastExecution.submitted_count}，失败 {futuSimLastExecution.failed_count}
        </p>
      )}
    </section>
  );
}

function App() {
  const [data, setData] = React.useState<Awaited<ReturnType<typeof loadDashboardData>> | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [chartMode, setChartMode] = React.useState<ChartMode>("equity");
  const [tab, setTab] = React.useState<DetailTab>("rebalance");
  const [selectedEtf, setSelectedEtf] = React.useState("510300");
  const [marketMode, setMarketMode] = React.useState<MarketChartMode>("daily");
  const [marketQuery, setMarketQuery] = React.useState("");
  const [previewModeLoading, setPreviewModeLoading] = React.useState<PreviewMode | null>(null);
  const [marketRefreshing, setMarketRefreshing] = React.useState(false);
  const [lastMarketRefresh, setLastMarketRefresh] = React.useState<string | null>(null);
  const [marketRefreshError, setMarketRefreshError] = React.useState<string | null>(null);
  const marketRefreshRunning = React.useRef(false);
  const [portfolioRefreshing, setPortfolioRefreshing] = React.useState(false);
  const [lastPortfolioRefresh, setLastPortfolioRefresh] = React.useState<string | null>(null);
  const [portfolioRefreshError, setPortfolioRefreshError] = React.useState<string | null>(null);
  const portfolioRefreshRunning = React.useRef(false);
  const dataReady = data !== null;
  const activePreviewMode = data?.futuSimOrderPreview?.mode?.selected ?? "observe";

  const reload = React.useCallback(() => {
    setError(null);
    loadDashboardData()
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, []);

  React.useEffect(() => {
    reload();
  }, [reload]);

  const refreshMarket = React.useCallback(async () => {
    if (marketRefreshRunning.current) return;
    marketRefreshRunning.current = true;
    setMarketRefreshing(true);
    setMarketRefreshError(null);
    try {
      const response = await fetch("/api/refresh-market", { method: "POST" });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || result.ok === false) {
        throw new Error(result.stderr || result.error || "行情刷新失败");
      }
      const nextData = await loadDashboardData();
      setData(nextData);
      setLastMarketRefresh(new Date().toLocaleTimeString("zh-CN", { hour12: false }));
    } catch (err) {
      setMarketRefreshError(err instanceof Error ? err.message : String(err));
    } finally {
      marketRefreshRunning.current = false;
      setMarketRefreshing(false);
    }
  }, []);

  React.useEffect(() => {
    if (marketMode !== "intraday") return;
    refreshMarket();
    const timer = window.setInterval(refreshMarket, AUTO_REFRESH_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [marketMode, refreshMarket]);

  const refreshPortfolio = React.useCallback(async (mode: PreviewMode) => {
    if (portfolioRefreshRunning.current) return;
    portfolioRefreshRunning.current = true;
    setPortfolioRefreshing(true);
    setPortfolioRefreshError(null);
    try {
      const response = await fetch(`/api/futu-sim-preview?mode=${encodeURIComponent(mode)}`, { method: "POST" });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(result.stderr || result.error || "持仓刷新接口不可用，请重启 npm run dev 后再试。");
      }
      const nextData = await loadDashboardData();
      setData(nextData);
      setLastPortfolioRefresh(new Date().toLocaleTimeString("zh-CN", { hour12: false }));
      if (result.stderr) {
        setPortfolioRefreshError(result.stderr);
      }
    } catch (err) {
      setPortfolioRefreshError(err instanceof Error ? err.message : String(err));
    } finally {
      portfolioRefreshRunning.current = false;
      setPortfolioRefreshing(false);
    }
  }, []);

  React.useEffect(() => {
    if (!dataReady) return;
    refreshPortfolio(activePreviewMode);
    const timer = window.setInterval(() => refreshPortfolio(activePreviewMode), AUTO_REFRESH_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [activePreviewMode, dataReady, refreshPortfolio]);

  const generatePreview = React.useCallback(async (mode: PreviewMode) => {
    setError(null);
    setPreviewModeLoading(mode);
    try {
      const response = await fetch(`/api/futu-sim-preview?mode=${encodeURIComponent(mode)}`, { method: "POST" });
      if (!response.ok) {
        throw new Error("模式切换接口不可用，请重启 npm run dev 后再试。");
      }
      const nextData = await loadDashboardData();
      setData(nextData);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPreviewModeLoading(null);
    }
  }, []);

  if (error) {
    return (
      <main className="error-state">
        <ShieldAlert />
        <h1>面板读取失败</h1>
        <p>{error}</p>
        <button className="primary-button" onClick={reload}>
          <RefreshCw size={16} />
          重试
        </button>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="loading-state">
        <Activity className="spin" />
        <span>正在读取回测结果</span>
      </main>
    );
  }

  const {
    metrics,
    meta,
    dataQuality,
    priceSeries,
    intradaySeries,
    marketSnapshot,
    equity,
    weights,
    rebalances,
    tradeSignal,
    futuSimAccount,
    futuSimPositions,
    futuSimOrderPreview,
    futuSimRecentOrders,
    futuSimLastExecution
  } = data;
  const etfCodes = Object.keys(priceSeries);
  const filteredMarketCodes = etfCodes.filter((code) => {
    const query = marketQuery.trim().toLowerCase();
    const item = priceSeries[code];
    if (!query) return true;
    return code.toLowerCase().includes(query) || item.name.toLowerCase().includes(query);
  });
  const activeEtfCode = priceSeries[selectedEtf] ? selectedEtf : etfCodes[0];
  const activeSeries = priceSeries[activeEtfCode];
  const activePoints = activeSeries?.points ?? [];
  const activeIntraday = intradaySeries[activeEtfCode];
  const activeIntradayPoints = activeIntraday?.points ?? [];
  const activeSnapshot = marketSnapshot.items.find((item) => item.code === activeEtfCode);
  const chartPoints: LinePoint[] =
    marketMode === "daily"
      ? activePoints.map((point) => ({ label: point.date.slice(0, 7), value: point.close }))
      : activeIntradayPoints.map((point) => ({ label: point.time.slice(11), value: point.price }));
  const latestPoint = activePoints[activePoints.length - 1];
  const prevPoint = activePoints[activePoints.length - 2];
  const ret20 =
    activePoints.length > 20 && latestPoint
      ? latestPoint.close / activePoints[activePoints.length - 21].close - 1
      : undefined;
  const ret60 =
    activePoints.length > 60 && latestPoint
      ? latestPoint.close / activePoints[activePoints.length - 61].close - 1
      : undefined;
  const ret120 =
    activePoints.length > 120 && latestPoint
      ? latestPoint.close / activePoints[activePoints.length - 121].close - 1
      : undefined;
  const latestHolding = [...weights].reverse().find((row) =>
    Object.keys(row).some((key) => key !== "date" && Number(row[key]) > 0)
  );
  const latestWeights = latestHolding
    ? Object.keys(latestHolding)
        .filter((key) => key !== "date" && Number(latestHolding[key]) > 0)
        .sort((a, b) => Number(latestHolding[b]) - Number(latestHolding[a]))
    : [];

  const metricCards = [
    {
      label: "总收益",
      value: pct(metrics.total_return),
      sub: `基准 ${pct(metrics.benchmark_total_return)}`,
      raw: metrics.total_return,
      icon: TrendingUp
    },
    {
      label: "年化收益",
      value: pct(metrics.annualized_return),
      sub: `基准 ${pct(metrics.benchmark_annualized_return)}`,
      raw: metrics.annualized_return,
      icon: LineChart
    },
    {
      label: "最大回撤",
      value: pct(metrics.max_drawdown),
      sub: `${metrics.max_drawdown_peak} 至 ${metrics.max_drawdown_trough}`,
      raw: metrics.max_drawdown,
      icon: TrendingDown
    },
    {
      label: "夏普比率",
      value: num(metrics.sharpe_no_risk_free),
      sub: "未扣无风险收益",
      raw: metrics.sharpe_no_risk_free,
      icon: BarChart3
    },
    {
      label: "年化波动",
      value: pct(metrics.annualized_volatility),
      sub: `基准 ${pct(metrics.benchmark_annualized_volatility)}`,
      raw: null,
      icon: Activity
    },
    {
      label: "平均换手",
      value: pct(metrics.avg_daily_turnover),
      sub: `平均持仓 ${num(metrics.avg_holding_count)} 只`,
      raw: null,
      icon: RefreshCw
    }
  ];

  return (
    <>
      <header className="app-header">
        <div className="brand">
          <WalletCards />
          <div>
            <h1>ETF Rotation Dashboard</h1>
            <span>动量轮动回测监控面板</span>
          </div>
        </div>
        <div className="header-actions">
          <span className={`data-badge ${meta.actual_data_mode}`}>
            <Database size={14} />
            {dataModeLabel(meta.actual_data_mode)}
          </span>
          <span className="status-pill">
            <CalendarClock size={14} />
            {metrics.start} 至 {metrics.end}
          </span>
          <span className="status-pill">交易日 {metrics.trading_days}</span>
          <span className="status-pill">调仓 {metrics.rebalance_count} 次</span>
          <button className="icon-button" title="重新读取 output 数据" onClick={reload}>
            <RefreshCw size={17} />
          </button>
          <a className="icon-button" title="下载 Excel 结果" href="/output/results.xlsx">
            <Download size={17} />
          </a>
        </div>
      </header>

      <main className="app-main">
        {meta.is_synthetic && (
          <section className="notice warning-notice">
            <AlertTriangle size={18} />
            <div>
              <strong>当前展示的是 synthetic 实验数据</strong>
              <span>这份结果只用于验证流程，不应作为真实策略表现判断。</span>
            </div>
          </section>
        )}

        {!meta.is_synthetic && (meta.warning_count > 0 || meta.error_count > 0) && (
          <section className="notice quality-notice">
            <AlertTriangle size={18} />
            <div>
              <strong>数据质量提示</strong>
              <span>
                warning {meta.warning_count} 项，error {meta.error_count} 项；请在数据质量表中检查对应标的。
              </span>
            </div>
          </section>
        )}

        <section className="metric-grid">
          {metricCards.map((card) => {
            const Icon = card.icon;
            return (
              <article className="metric-card" key={card.label}>
                <div className="metric-top">
                  <span>{card.label}</span>
                  <Icon size={18} />
                </div>
                <strong className={card.raw === null ? "" : tone(card.raw)}>{card.value}</strong>
                <small>{card.sub}</small>
              </article>
            );
          })}
        </section>

        <section className="workspace">
          <article className="panel chart-panel">
            <div className="panel-head">
              <h2>净值曲线</h2>
              <div className="segmented">
                {[
                  ["equity", "净值"],
                  ["drawdown", "回撤"],
                  ["turnover", "换手"]
                ].map(([mode, label]) => (
                  <button
                    key={mode}
                    type="button"
                    className={chartMode === mode ? "active" : ""}
                    onClick={() => setChartMode(mode as ChartMode)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <SvgChart equity={equity} mode={chartMode} />
          </article>

          <aside className="side-stack">
            <article className="panel">
              <div className="panel-head">
                <h2>最新持仓</h2>
                <span className="muted">{latestHolding?.date ?? "--"}</span>
              </div>
              <div className="holdings">
                {latestWeights.length === 0 ? (
                  <p className="empty-text">当前为空仓</p>
                ) : (
                  latestWeights.map((code) => {
                    const weight = Number(latestHolding?.[code] ?? 0);
                    return (
                      <div className="holding-row" key={code}>
                        <strong>{ETF_NAMES[code] ?? code}</strong>
                        <div>
                          <span>{code}</span>
                          <div className="bar-track">
                            <div className="bar" style={{ width: `${Math.max(3, weight * 100)}%` }} />
                          </div>
                        </div>
                        <em>{pct(weight)}</em>
                      </div>
                    );
                  })
                )}
              </div>
            </article>

            <article className="panel">
              <div className="panel-head">
                <h2>最近调仓</h2>
              </div>
              <div className="table-scroll compact">
                <table>
                  <thead>
                    <tr>
                      <th>日期</th>
                      <th>标的</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rebalances.slice(-12).reverse().map((row) => (
                      <tr key={row.date}>
                        <td>{row.date}</td>
                        <td>{selectedLabel(row.selected)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
          </aside>
        </section>

        <section className="panel market-panel">
          <div className="panel-head">
            <h2>行情中心</h2>
            <div className="toolbar-inline">
              <Radio size={16} />
              <span className="muted">
                分时来源：{marketSourceLabel(activeIntraday?.source || marketSnapshot.source)}
              </span>
              {marketMode === "intraday" && (
                <>
                  <span className="live-dot" aria-hidden="true" />
                  <span className="muted">
                    {marketRefreshing ? "刷新中" : lastMarketRefresh ? `上次刷新 ${lastMarketRefresh}` : "5秒自动刷新"}
                  </span>
                </>
              )}
              <button
                type="button"
                className="icon-button small"
                title="立即刷新分时行情"
                onClick={refreshMarket}
                disabled={marketRefreshing}
              >
                <RefreshCw size={15} className={marketRefreshing ? "spin" : ""} />
              </button>
            </div>
          </div>
          <div className="market-layout">
            <div className="etf-list" aria-label="ETF list">
              <label className="market-search">
                <Search size={15} />
                <input
                  value={marketQuery}
                  onChange={(event) => setMarketQuery(event.target.value)}
                  placeholder="搜索名称或代码"
                />
              </label>
              {filteredMarketCodes.map((code) => {
                const item = priceSeries[code];
                const last = item.points[item.points.length - 1];
                const isHeld = Number(latestHolding?.[code] ?? 0) > 0;
                return (
                  <button
                    type="button"
                    className={`etf-button ${activeEtfCode === code ? "active" : ""}`}
                    key={code}
                    onClick={() => setSelectedEtf(code)}
                  >
                    <strong>{item.name}</strong>
                    <span>{code}</span>
                    <em className={tone(last?.daily_return ?? 0)}>{pct(last?.daily_return ?? 0)}</em>
                    {isHeld && <b>持仓</b>}
                  </button>
                );
              })}
              {filteredMarketCodes.length === 0 && <p className="empty-text">没有匹配的标的</p>}
            </div>
            <div className="market-main">
              <div className="quote-strip">
                <div>
                  <span>最新价</span>
                  <strong>{num(activeSnapshot?.latest_price ?? latestPoint?.close, 3)}</strong>
                </div>
                <div>
                  <span>日涨跌</span>
                  <strong className={tone(activeSnapshot?.daily_return ?? latestPoint?.daily_return ?? 0)}>
                    {pct(activeSnapshot?.daily_return ?? latestPoint?.daily_return ?? 0)}
                  </strong>
                </div>
                <div>
                  <span>20日动量</span>
                  <strong className={tone(ret20)}>{pct(ret20)}</strong>
                </div>
                <div>
                  <span>60日动量</span>
                  <strong className={tone(ret60)}>{pct(ret60)}</strong>
                </div>
                <div>
                  <span>120日动量</span>
                  <strong className={tone(ret120)}>{pct(ret120)}</strong>
                </div>
                <div>
                  <span>更新时间</span>
                  <strong>{activeSnapshot?.updated_at?.slice(5) ?? latestPoint?.date ?? "--"}</strong>
                </div>
              </div>
              <div className="market-title-row">
                <div>
                  <h3>
                    {activeSeries?.name}
                  </h3>
                  <span className="muted">
                    {activeEtfCode}，
                    {activePoints[0]?.date ?? "--"} 至 {latestPoint?.date ?? "--"}
                    {prevPoint ? `，上一交易日 ${num(prevPoint.close, 3)}` : ""}
                  </span>
                </div>
                <div className="segmented">
                  <button type="button" className={marketMode === "daily" ? "active" : ""} onClick={() => setMarketMode("daily")}>
                    日线
                  </button>
                  <button
                    type="button"
                    className={marketMode === "intraday" ? "active" : ""}
                    onClick={() => setMarketMode("intraday")}
                  >
                    分时
                  </button>
                </div>
              </div>
              {chartPoints.length > 1 ? <PriceChart points={chartPoints} /> : <p className="empty-text">暂无价格序列</p>}
              {marketSnapshot.warnings.length > 0 && (
                <div className="market-warning">
                  <AlertTriangle size={15} />
                  <span>{marketSnapshot.warnings[0]}</span>
                </div>
              )}
              {marketRefreshError && (
                <div className="market-warning">
                  <AlertTriangle size={15} />
                  <span>{marketRefreshError}</span>
                </div>
              )}
            </div>
          </div>
        </section>

        <SimTradingPanel
          tradeSignal={tradeSignal}
          futuSimAccount={futuSimAccount}
          futuSimPositions={futuSimPositions}
          futuSimOrderPreview={futuSimOrderPreview}
          futuSimRecentOrders={futuSimRecentOrders}
          futuSimLastExecution={futuSimLastExecution}
          previewModeLoading={previewModeLoading}
          portfolioRefreshing={portfolioRefreshing}
          lastPortfolioRefresh={lastPortfolioRefresh}
          portfolioRefreshError={portfolioRefreshError}
          onPreviewModeChange={generatePreview}
        />

        <section className="panel data-quality-panel">
          <div className="panel-head">
            <h2>数据质量</h2>
            <span className="muted">生成时间 {meta.generated_at}</span>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>状态</th>
                  <th>标的</th>
                  <th>来源</th>
                  <th>数据范围</th>
                  <th>有效/预期</th>
                  <th>缺失率</th>
                  <th>异常涨跌</th>
                  <th>提示</th>
                </tr>
              </thead>
              <tbody>
                {dataQuality.map((row) => (
                  <tr key={row.code}>
                    <td>
                      <span className={`quality-pill ${row.status}`}>
                        {row.status === "ok" ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
                        {statusLabel(row.status)}
                      </span>
                    </td>
                    <td>
                      <strong>{row.name}</strong>
                      <span className="cell-sub">{row.code}</span>
                    </td>
                    <td>{row.source_status}</td>
                    <td>
                      {row.start_date || "--"} 至 {row.end_date || "--"}
                    </td>
                    <td>
                      {row.valid_close_count} / {row.expected_trading_days}
                    </td>
                    <td>{pct(row.missing_ratio)}</td>
                    <td>{row.extreme_return_count}</td>
                    <td>{row.warnings || "--"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="panel detail-panel">
          <div className="tabs">
            <button type="button" className={tab === "rebalance" ? "active" : ""} onClick={() => setTab("rebalance")}>
              调仓记录
            </button>
            <button type="button" className={tab === "returns" ? "active" : ""} onClick={() => setTab("returns")}>
              收益明细
            </button>
          </div>
          {tab === "rebalance" ? (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>日期</th>
                    <th>持仓</th>
                    <th>分数</th>
                  </tr>
                </thead>
                <tbody>
                  {rebalances.slice(-140).reverse().map((row) => (
                    <tr key={`${row.date}-${row.selected}`}>
                      <td>{row.date}</td>
                      <td>{selectedLabel(row.selected)}</td>
                      <td>
                        <code>{row.scores || "{}"}</code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>日期</th>
                    <th>策略净值</th>
                    <th>基准净值</th>
                    <th>策略日收益</th>
                    <th>换手</th>
                  </tr>
                </thead>
                <tbody>
                  {equity.slice(-180).reverse().map((row) => (
                    <tr key={row.date}>
                      <td>{row.date}</td>
                      <td>{num(row.strategy, 4)}</td>
                      <td>{num(row.benchmark_equal_weight, 4)}</td>
                      <td className={tone(row.strategy_daily_return)}>{pct(row.strategy_daily_return)}</td>
                      <td>{pct(row.turnover)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
