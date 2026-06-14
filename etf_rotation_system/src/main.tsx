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
  LineChart,
  Radio,
  RefreshCw,
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

type LinePoint = {
  label: string;
  value: number;
};

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
  const [metrics, meta, dataQuality, priceSeries, intradaySeries, marketSnapshot, equityText, weightsText, rebalanceText] =
    await Promise.all([
    fetch("/output/metrics.json").then((res) => res.json() as Promise<Metrics>),
    fetch("/output/run_meta.json").then((res) => res.json() as Promise<RunMeta>),
    fetch("/output/data_quality.json").then((res) => res.json() as Promise<DataQualityRow[]>),
    fetch("/output/price_series.json").then((res) => res.json() as Promise<PriceSeries>),
    fetch("/output/intraday_series.json").then((res) => res.json() as Promise<IntradaySeries>),
    fetch("/output/market_snapshot.json").then((res) => res.json() as Promise<MarketSnapshot>),
    fetch("/output/equity_curve.csv").then((res) => res.text()),
    fetch("/output/daily_weights.csv").then((res) => res.text()),
    fetch("/output/rebalance_log.csv").then((res) => res.text())
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
    rebalances: parseCsv(rebalanceText)
  };
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

function App() {
  const [data, setData] = React.useState<Awaited<ReturnType<typeof loadDashboardData>> | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [chartMode, setChartMode] = React.useState<ChartMode>("equity");
  const [tab, setTab] = React.useState<DetailTab>("rebalance");
  const [selectedEtf, setSelectedEtf] = React.useState("510300");
  const [marketMode, setMarketMode] = React.useState<MarketChartMode>("daily");

  const reload = React.useCallback(() => {
    setError(null);
    loadDashboardData()
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, []);

  React.useEffect(() => {
    reload();
  }, [reload]);

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

  const { metrics, meta, dataQuality, priceSeries, intradaySeries, marketSnapshot, equity, weights, rebalances } = data;
  const etfCodes = Object.keys(priceSeries);
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
              <span>这份结果只用于验证流程，不应作为真实 ETF 策略表现判断。</span>
            </div>
          </section>
        )}

        {!meta.is_synthetic && (meta.warning_count > 0 || meta.error_count > 0) && (
          <section className="notice quality-notice">
            <AlertTriangle size={18} />
            <div>
              <strong>数据质量提示</strong>
              <span>
                warning {meta.warning_count} 项，error {meta.error_count} 项；请在数据质量表中检查对应 ETF。
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
                        <strong>{code}</strong>
                        <div>
                          <span>{ETF_NAMES[code] ?? code}</span>
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
            <h2>ETF 行情中心</h2>
            <div className="toolbar-inline">
              <Radio size={16} />
              <span className="muted">
                分时来源：{marketSourceLabel(activeIntraday?.source || marketSnapshot.source)}
              </span>
            </div>
          </div>
          <div className="market-layout">
            <div className="etf-list" aria-label="ETF list">
              {etfCodes.map((code) => {
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
                    <strong>{code}</strong>
                    <span>{item.name}</span>
                    <em className={tone(last?.daily_return ?? 0)}>{pct(last?.daily_return ?? 0)}</em>
                    {isHeld && <b>持仓</b>}
                  </button>
                );
              })}
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
                    {activeEtfCode} {activeSeries?.name}
                  </h3>
                  <span className="muted">
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
            </div>
          </div>
        </section>

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
                  <th>ETF</th>
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
                      <strong>{row.code}</strong>
                      <span className="cell-sub">{row.name}</span>
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
