from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
OUTPUT_DIR = ROOT / "output"
FUTU_APPDATA_DIR = ROOT / ".futu_appdata"
MIN_DATA_COVERAGE = 0.75
EXTREME_RETURN_THRESHOLD = 0.12


ETF_UNIVERSE: Dict[str, str] = {
    "510300": "沪深300ETF",
    "510500": "中证500ETF",
    "159915": "创业板ETF",
    "510880": "红利ETF",
    "518880": "黄金ETF",
    "513100": "纳指ETF",
    "513180": "恒生科技ETF",
    "511010": "国债ETF",
}


@dataclass(frozen=True)
class BacktestConfig:
    start: str
    end: str
    data_source: str
    rebalance: str
    top_n: int
    fee_rate: float
    risk_penalty: float
    min_momentum_window: int
    clear_proxy: bool
    futu_host: str
    futu_port: int


@dataclass(frozen=True)
class PriceLoadResult:
    prices: pd.DataFrame
    actual_data_mode: str
    data_quality: pd.DataFrame
    source_status: Dict[str, str]


def parse_args() -> BacktestConfig:
    default_end = pd.Timestamp.today().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="ETF momentum rotation backtest")
    parser.add_argument("--start", default=None, help="Start date, defaults to one year before --end")
    parser.add_argument("--end", default=default_end, help="End date")
    parser.add_argument(
        "--data-source",
        choices=["auto", "akshare", "futu", "synthetic"],
        default="auto",
        help="auto uses cached/AkShare data when available, then falls back to synthetic data",
    )
    parser.add_argument("--rebalance", default="W-FRI", help="Pandas frequency, e.g. W-FRI or ME")
    parser.add_argument("--top-n", type=int, default=2, help="Number of ETFs to hold")
    parser.add_argument("--fee-rate", type=float, default=0.0008, help="One-way transaction cost")
    parser.add_argument("--risk-penalty", type=float, default=0.15, help="Penalty applied to 60-day vol")
    parser.add_argument(
        "--min-momentum-window",
        type=int,
        default=120,
        help="Require positive return over this window; set 0 to disable",
    )
    parser.add_argument("--clear-proxy", action="store_true", help="Clear proxy env vars before AkShare fetch")
    parser.add_argument("--futu-host", default="127.0.0.1", help="Futu OpenD host for --data-source futu")
    parser.add_argument("--futu-port", type=int, default=11111, help="Futu OpenD port for --data-source futu")
    args = parser.parse_args()
    if args.start is None:
        args.start = (pd.Timestamp(args.end) - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
    return BacktestConfig(**vars(args))


def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def clear_proxy_env() -> None:
    for key in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
        os.environ.pop(key, None)


def prepare_futu_env() -> None:
    FUTU_APPDATA_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["APPDATA"] = str(FUTU_APPDATA_DIR)
    os.environ["appdata"] = str(FUTU_APPDATA_DIR)


def normalize_price_frame(df: pd.DataFrame, code: str, name: str) -> pd.DataFrame:
    rename_map = {
        "日期": "date",
        "收盘": "close",
        "成交额": "amount",
        "成交量": "volume",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
    }
    df = df.rename(columns=rename_map).copy()
    if "date" not in df.columns or "close" not in df.columns:
        raise ValueError(f"{code} returned unexpected columns: {list(df.columns)}")
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["code"] = code
    df["name"] = name
    keep_cols = [c for c in ["date", "code", "name", "close", "amount", "volume", "open", "high", "low"] if c in df.columns]
    return df[keep_cols].dropna(subset=["date", "close"]).sort_values("date")


def quality_row(df: pd.DataFrame, code: str, name: str, start: str, end: str, source_status: str) -> dict:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    requested_days = len(pd.bdate_range(start_ts, end_ts))
    in_range = df[(df["date"] >= start_ts) & (df["date"] <= end_ts)].copy()
    duplicate_dates = int(in_range["date"].duplicated().sum()) if not in_range.empty else 0
    in_range = in_range.drop_duplicates(subset=["date"], keep="last").sort_values("date")
    row_count = int(len(in_range))
    close = pd.to_numeric(in_range["close"], errors="coerce") if "close" in in_range.columns else pd.Series(dtype=float)
    valid_close_count = int(close.notna().sum())
    first_data_ts = in_range["date"].min() if row_count else pd.NaT
    effective_start_ts = max(start_ts, first_data_ts) if row_count else start_ts
    expected_days = len(pd.bdate_range(effective_start_ts, end_ts))
    missing_ratio = 1 - valid_close_count / expected_days if expected_days else 0.0
    daily_return = close.pct_change()
    extreme_return_count = int((daily_return.abs() > EXTREME_RETURN_THRESHOLD).sum())
    warnings: List[str] = []
    status = "ok"

    if row_count == 0 or valid_close_count == 0:
        status = "error"
        warnings.append("no valid close data in requested range")
    if missing_ratio > (1 - MIN_DATA_COVERAGE):
        status = "error"
        warnings.append(f"effective data coverage below {MIN_DATA_COVERAGE:.0%}")
    if row_count > 0 and first_data_ts > start_ts + pd.Timedelta(days=7):
        warnings.append(f"first data starts after requested start: {first_data_ts.strftime('%Y-%m-%d')}")
        if status == "ok":
            status = "warning"
    if duplicate_dates > 0:
        warnings.append(f"{duplicate_dates} duplicate date rows")
        if status == "ok":
            status = "warning"
    if extreme_return_count > 0:
        warnings.append(f"{extreme_return_count} daily returns exceed {EXTREME_RETURN_THRESHOLD:.0%}")
        if status == "ok":
            status = "warning"

    first_date = in_range["date"].min().strftime("%Y-%m-%d") if row_count else ""
    last_date = in_range["date"].max().strftime("%Y-%m-%d") if row_count else ""

    return {
        "code": code,
        "name": name,
        "source_status": source_status,
        "status": status,
        "start_date": first_date,
        "end_date": last_date,
        "row_count": row_count,
        "expected_trading_days": int(requested_days),
        "effective_expected_trading_days": int(expected_days),
        "valid_close_count": valid_close_count,
        "missing_ratio": float(max(0.0, missing_ratio)),
        "extreme_return_count": extreme_return_count,
        "duplicate_dates": duplicate_dates,
        "warnings": "; ".join(warnings),
    }


def validate_quality(data_quality: pd.DataFrame, context: str) -> None:
    bad = data_quality[data_quality["status"] == "error"]
    if bad.empty:
        return
    details = [
        f"{row.code} {row.name}: {row.warnings or 'data quality error'}"
        for row in bad.itertuples(index=False)
    ]
    raise ValueError(f"{context} data quality validation failed: " + " | ".join(details))


def cache_path(code: str, provider: str = "akshare") -> Path:
    return RAW_DIR / provider / f"{code}.csv"


def read_cached_prices(start: str, end: str, strict: bool, provider: str = "akshare") -> PriceLoadResult | None:
    frames: List[pd.DataFrame] = []
    quality_rows = []
    source_status: Dict[str, str] = {}
    for code, name in ETF_UNIVERSE.items():
        path = cache_path(code, provider)
        if not path.exists():
            return None
        df = pd.read_csv(path)
        df = normalize_price_frame(df, code, name)
        quality_rows.append(quality_row(df, code, name, start, end, f"{provider}_cache_hit"))
        source_status[code] = f"{provider}_cache_hit"
        frames.append(df)
    data_quality = pd.DataFrame(quality_rows)
    if strict:
        validate_quality(data_quality, "Cached")
    prices = build_close_matrix(frames, start, end)
    if prices.shape[1] < 3:
        if strict:
            raise ValueError(f"Cached {provider} data produced fewer than 3 usable ETF price series")
        return None
    return PriceLoadResult(prices, f"{provider}_cached", data_quality, source_status)


def fetch_akshare_prices(start: str, end: str, clear_proxy: bool, strict: bool) -> PriceLoadResult:
    if clear_proxy:
        clear_proxy_env()
    import akshare as ak

    frames: List[pd.DataFrame] = []
    quality_rows = []
    source_status: Dict[str, str] = {}
    start_raw = pd.Timestamp(start).strftime("%Y%m%d")
    end_raw = pd.Timestamp(end).strftime("%Y%m%d")
    cache_path("probe", "akshare").parent.mkdir(parents=True, exist_ok=True)
    for code, name in ETF_UNIVERSE.items():
        print(f"Fetching {code} {name}...")
        df = ak.fund_etf_hist_em(symbol=code, period="daily", start_date=start_raw, end_date=end_raw, adjust="qfq")
        df = normalize_price_frame(df, code, name)
        quality_rows.append(quality_row(df, code, name, start, end, "downloaded"))
        source_status[code] = "downloaded"
        df.to_csv(cache_path(code, "akshare"), index=False, encoding="utf-8-sig")
        frames.append(df)
    data_quality = pd.DataFrame(quality_rows)
    if strict:
        validate_quality(data_quality, "AkShare")
    prices = build_close_matrix(frames, start, end)
    if prices.shape[1] < 3:
        raise ValueError("AkShare data produced fewer than 3 usable ETF price series")
    return PriceLoadResult(prices, "akshare", data_quality, source_status)


def futu_symbol(code: str) -> str:
    if code.startswith(("5", "6")):
        return f"SH.{code}"
    return f"SZ.{code}"


def normalize_futu_daily_frame(df: pd.DataFrame, code: str, name: str) -> pd.DataFrame:
    df = df.rename(columns={"time_key": "date", "turnover": "amount"}).copy()
    if "date" not in df.columns or "close" not in df.columns:
        raise ValueError(f"{code} returned unexpected Futu columns: {list(df.columns)}")
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["code"] = code
    df["name"] = name
    keep_cols = [c for c in ["date", "code", "name", "close", "amount", "volume", "open", "high", "low"] if c in df.columns]
    return df[keep_cols].dropna(subset=["date", "close"]).sort_values("date")


def fetch_futu_one_daily(
    quote_ctx,
    symbol: str,
    start: str,
    end: str,
    kl_type,
    au_type,
) -> pd.DataFrame:
    prepare_futu_env()
    from futu import RET_OK

    frames: List[pd.DataFrame] = []
    page_req_key = None
    while True:
        ret, data, page_req_key = quote_ctx.request_history_kline(
            symbol,
            start=start,
            end=end,
            ktype=kl_type.K_DAY,
            autype=au_type.QFQ,
            max_count=1000,
            page_req_key=page_req_key,
        )
        if ret != RET_OK:
            raise RuntimeError(str(data))
        frames.append(data)
        if page_req_key is None:
            break
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def fetch_futu_prices(config: BacktestConfig, strict: bool) -> PriceLoadResult:
    prepare_futu_env()
    try:
        from futu import AuType, KLType, OpenQuoteContext
    except ImportError as exc:
        raise RuntimeError("futu-api is not installed. Install it with: pip install futu-api") from exc

    frames: List[pd.DataFrame] = []
    quality_rows = []
    source_status: Dict[str, str] = {}
    cache_path("probe", "futu").parent.mkdir(parents=True, exist_ok=True)
    quote_ctx = OpenQuoteContext(host=config.futu_host, port=config.futu_port)
    try:
        for code, name in ETF_UNIVERSE.items():
            symbol = futu_symbol(code)
            print(f"Fetching {code} {name} from Futu ({symbol})...")
            raw = fetch_futu_one_daily(quote_ctx, symbol, config.start, config.end, KLType, AuType)
            df = normalize_futu_daily_frame(raw, code, name)
            quality_rows.append(quality_row(df, code, name, config.start, config.end, "futu_downloaded"))
            source_status[code] = "futu_downloaded"
            df.to_csv(cache_path(code, "futu"), index=False, encoding="utf-8-sig")
            frames.append(df)
    finally:
        quote_ctx.close()

    data_quality = pd.DataFrame(quality_rows)
    if strict:
        validate_quality(data_quality, "Futu")
    prices = build_close_matrix(frames, config.start, config.end)
    if prices.shape[1] < 3:
        raise ValueError("Futu data produced fewer than 3 usable ETF price series")
    return PriceLoadResult(prices, "futu", data_quality, source_status)


def synthetic_prices(start: str, end: str) -> pd.DataFrame:
    dates = pd.bdate_range(start, end)
    rng = np.random.default_rng(20260613)
    n = len(dates)
    if n < 260:
        raise ValueError("Need at least about one trading year for this backtest")

    common = rng.normal(0.00015, 0.0065, n)
    regimes = np.where(np.arange(n) % 760 < 460, 1.0, -0.25)
    profiles = {
        "510300": (0.00018, 0.010, 0.95),
        "510500": (0.00022, 0.013, 1.10),
        "159915": (0.00028, 0.017, 1.25),
        "510880": (0.00012, 0.009, 0.75),
        "518880": (0.00016, 0.011, -0.10),
        "513100": (0.00031, 0.015, 0.65),
        "513180": (0.00024, 0.019, 1.05),
        "511010": (0.00006, 0.0022, -0.35),
    }
    out = {}
    for idx, (code, (drift, vol, beta)) in enumerate(profiles.items()):
        cycle = 0.0009 * np.sin(np.linspace(0, 10 * np.pi, n) + idx)
        noise = rng.normal(0, vol, n)
        daily_ret = drift * regimes + beta * common + cycle + noise
        daily_ret = np.clip(daily_ret, -0.085, 0.085)
        out[code] = 100 * np.cumprod(1 + daily_ret)
    return pd.DataFrame(out, index=dates)


def synthetic_quality(prices: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    rows = []
    for code, name in ETF_UNIVERSE.items():
        df = pd.DataFrame({"date": prices.index, "close": prices[code], "code": code, "name": name})
        rows.append(quality_row(df, code, name, start, end, "synthetic"))
    return pd.DataFrame(rows)


def build_close_matrix(frames: Iterable[pd.DataFrame], start: str, end: str) -> pd.DataFrame:
    close = {}
    for df in frames:
        code = str(df["code"].iloc[0])
        s = df.set_index("date")["close"].sort_index()
        close[code] = s
    prices = pd.DataFrame(close)
    prices = prices.loc[pd.Timestamp(start) : pd.Timestamp(end)]
    prices = prices.ffill().dropna(how="all")
    return prices.dropna(axis=1, thresh=int(len(prices) * 0.75)).ffill().dropna()


def load_prices(config: BacktestConfig) -> PriceLoadResult:
    if config.data_source in {"auto", "akshare"}:
        cached = read_cached_prices(config.start, config.end, strict=config.data_source == "akshare", provider="akshare")
        if cached is not None:
            return cached
        try:
            return fetch_akshare_prices(config.start, config.end, config.clear_proxy, strict=config.data_source == "akshare")
        except Exception as exc:
            if config.data_source == "akshare":
                raise RuntimeError(f"AkShare strict mode failed; no synthetic fallback was used. Reason: {exc}") from exc
            print(f"AkShare unavailable, using synthetic data. Reason: {exc}")
    if config.data_source == "futu":
        cached = read_cached_prices(config.start, config.end, strict=True, provider="futu")
        if cached is not None:
            return cached
        try:
            return fetch_futu_prices(config, strict=True)
        except Exception as exc:
            raise RuntimeError(f"Futu strict mode failed; no synthetic fallback was used. Reason: {exc}") from exc
    prices = synthetic_prices(config.start, config.end)
    return PriceLoadResult(
        prices=prices,
        actual_data_mode="synthetic",
        data_quality=synthetic_quality(prices, config.start, config.end),
        source_status={code: "synthetic" for code in ETF_UNIVERSE},
    )


def pick_rebalance_dates(index: pd.DatetimeIndex, freq: str) -> pd.DatetimeIndex:
    markers = pd.Series(index=index, data=index)
    grouped = markers.groupby(pd.Grouper(freq=freq)).last().dropna()
    return pd.DatetimeIndex(grouped.values)


def compute_scores(prices: pd.DataFrame, risk_penalty: float) -> pd.DataFrame:
    ret20 = prices.pct_change(20)
    ret60 = prices.pct_change(60)
    ret120 = prices.pct_change(120)
    vol60 = prices.pct_change().rolling(60).std() * math.sqrt(252)
    return 0.2 * ret20 + 0.3 * ret60 + 0.5 * ret120 - risk_penalty * vol60


def run_backtest(prices: pd.DataFrame, config: BacktestConfig) -> Dict[str, pd.DataFrame | pd.Series | dict]:
    returns = prices.pct_change().fillna(0)
    scores = compute_scores(prices, config.risk_penalty)
    rebalance_dates = pick_rebalance_dates(prices.index, config.rebalance)

    target_weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    rebalance_rows = []
    current = pd.Series(0.0, index=prices.columns)

    for date in prices.index:
        if date in rebalance_dates and date in scores.index:
            score = scores.loc[date].dropna()
            if config.min_momentum_window > 0:
                momentum = prices.pct_change(config.min_momentum_window).loc[date]
                score = score[momentum.reindex(score.index) > 0]
            selected = score.sort_values(ascending=False).head(config.top_n)
            current = pd.Series(0.0, index=prices.columns)
            if not selected.empty:
                current.loc[selected.index] = 1.0 / len(selected)
            rebalance_rows.append(
                {
                    "date": date,
                    "selected": ",".join(selected.index.tolist()) if not selected.empty else "CASH",
                    "scores": json.dumps({k: round(float(v), 6) for k, v in selected.items()}, ensure_ascii=False),
                }
            )
        target_weights.loc[date] = current

    effective_weights = target_weights.shift(1).fillna(0)
    turnover = effective_weights.diff().abs().sum(axis=1).fillna(effective_weights.abs().sum(axis=1))
    gross_ret = (effective_weights * returns).sum(axis=1)
    net_ret = gross_ret - turnover * config.fee_rate
    equity = (1 + net_ret).cumprod()

    benchmark_ret = returns.mean(axis=1)
    benchmark_equity = (1 + benchmark_ret).cumprod()
    equity_curve = pd.DataFrame(
        {
            "strategy": equity,
            "benchmark_equal_weight": benchmark_equity,
            "strategy_daily_return": net_ret,
            "benchmark_daily_return": benchmark_ret,
            "turnover": turnover,
        }
    )
    rebalance_log = pd.DataFrame(rebalance_rows)
    if not rebalance_log.empty:
        rebalance_log["date"] = pd.to_datetime(rebalance_log["date"])
    metrics = calc_metrics(equity_curve, effective_weights, rebalance_log)
    return {
        "prices": prices,
        "equity_curve": equity_curve,
        "daily_weights": effective_weights,
        "rebalance_log": rebalance_log,
        "metrics": metrics,
    }


def max_drawdown(equity: pd.Series) -> Tuple[float, str, str]:
    peak = equity.cummax()
    drawdown = equity / peak - 1
    trough_date = drawdown.idxmin()
    peak_date = equity.loc[:trough_date].idxmax()
    return float(drawdown.min()), peak_date.strftime("%Y-%m-%d"), trough_date.strftime("%Y-%m-%d")


def annualized_return(equity: pd.Series) -> float:
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    if years <= 0:
        return 0.0
    return float(equity.iloc[-1] ** (1 / years) - 1)


def calc_metrics(equity_curve: pd.DataFrame, weights: pd.DataFrame, rebalance_log: pd.DataFrame) -> dict:
    strategy = equity_curve["strategy"]
    benchmark = equity_curve["benchmark_equal_weight"]
    ret = equity_curve["strategy_daily_return"]
    bench_ret = equity_curve["benchmark_daily_return"]
    mdd, peak_date, trough_date = max_drawdown(strategy)
    bench_mdd, _, _ = max_drawdown(benchmark)
    ann_ret = annualized_return(strategy)
    ann_vol = float(ret.std() * math.sqrt(252))
    sharpe = float(ann_ret / ann_vol) if ann_vol else 0.0
    calmar = float(ann_ret / abs(mdd)) if mdd else 0.0
    return {
        "start": strategy.index[0].strftime("%Y-%m-%d"),
        "end": strategy.index[-1].strftime("%Y-%m-%d"),
        "trading_days": int(len(strategy)),
        "total_return": float(strategy.iloc[-1] - 1),
        "annualized_return": ann_ret,
        "annualized_volatility": ann_vol,
        "sharpe_no_risk_free": sharpe,
        "max_drawdown": mdd,
        "max_drawdown_peak": peak_date,
        "max_drawdown_trough": trough_date,
        "calmar": calmar,
        "win_rate_daily": float((ret > 0).mean()),
        "avg_daily_turnover": float(equity_curve["turnover"].mean()),
        "rebalance_count": int(len(rebalance_log)),
        "avg_holding_count": float((weights > 0).sum(axis=1).mean()),
        "benchmark_total_return": float(benchmark.iloc[-1] - 1),
        "benchmark_annualized_return": annualized_return(benchmark),
        "benchmark_annualized_volatility": float(bench_ret.std() * math.sqrt(252)),
        "benchmark_max_drawdown": bench_mdd,
    }


def pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def config_to_dict(config: BacktestConfig) -> dict:
    return {
        "start": config.start,
        "end": config.end,
        "data_source": config.data_source,
        "rebalance": config.rebalance,
        "top_n": config.top_n,
        "fee_rate": config.fee_rate,
        "risk_penalty": config.risk_penalty,
        "min_momentum_window": config.min_momentum_window,
        "clear_proxy": config.clear_proxy,
        "futu_host": config.futu_host,
        "futu_port": config.futu_port,
    }


def clean_records(df: pd.DataFrame) -> List[dict]:
    clean = df.where(pd.notna(df), None)
    return clean.to_dict(orient="records")


def build_run_meta(config: BacktestConfig, load_result: PriceLoadResult) -> dict:
    quality_counts = load_result.data_quality["status"].value_counts().to_dict()
    warning_count = int((load_result.data_quality["status"] == "warning").sum())
    error_count = int((load_result.data_quality["status"] == "error").sum())
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "requested_data_source": config.data_source,
        "actual_data_mode": load_result.actual_data_mode,
        "is_synthetic": load_result.actual_data_mode == "synthetic",
        "config": config_to_dict(config),
        "universe": [{"code": code, "name": name} for code, name in ETF_UNIVERSE.items()],
        "source_status": load_result.source_status,
        "quality_counts": quality_counts,
        "warning_count": warning_count,
        "error_count": error_count,
        "quality_rules": {
            "min_data_coverage": MIN_DATA_COVERAGE,
            "extreme_return_threshold": EXTREME_RETURN_THRESHOLD,
        },
    }


def build_price_series(prices: pd.DataFrame) -> dict:
    series = {}
    for code, name in ETF_UNIVERSE.items():
        if code not in prices.columns:
            continue
        close = prices[code].dropna()
        returns = close.pct_change()
        series[code] = {
            "code": code,
            "name": name,
            "points": [
                {
                    "date": idx.strftime("%Y-%m-%d"),
                    "close": float(value),
                    "daily_return": None if pd.isna(returns.loc[idx]) else float(returns.loc[idx]),
                }
                for idx, value in close.items()
            ],
        }
    return series


def make_intraday_times(base_date: pd.Timestamp) -> List[datetime]:
    points: List[datetime] = []
    morning = datetime.combine(base_date.date(), time(9, 30))
    afternoon = datetime.combine(base_date.date(), time(13, 0))
    for i in range(121):
        points.append(morning + timedelta(minutes=i))
    for i in range(121):
        points.append(afternoon + timedelta(minutes=i))
    return points


def derived_intraday_points(close: pd.Series, code: str) -> List[dict]:
    clean = close.dropna()
    if len(clean) < 2:
        return []
    latest_date = pd.Timestamp(clean.index[-1])
    prev_close = float(clean.iloc[-2])
    latest_close = float(clean.iloc[-1])
    rng = np.random.default_rng(20260613 + int(code))
    times = make_intraday_times(latest_date)
    base_path = np.linspace(prev_close, latest_close, len(times))
    noise = rng.normal(0, max(prev_close, latest_close) * 0.0009, len(times)).cumsum()
    noise = noise - np.linspace(noise[0], noise[-1], len(times))
    values = base_path + noise
    values[0] = prev_close
    values[-1] = latest_close
    return [
        {
            "time": ts.strftime("%Y-%m-%d %H:%M"),
            "price": float(max(value, 0.001)),
        }
        for ts, value in zip(times, values)
    ]


def build_derived_intraday_series(prices: pd.DataFrame) -> dict:
    series = {}
    for code, name in ETF_UNIVERSE.items():
        if code not in prices.columns:
            continue
        points = derived_intraday_points(prices[code], code)
        series[code] = {
            "code": code,
            "name": name,
            "source": "derived_from_daily",
            "period": "1",
            "points": points,
        }
    return series


def normalize_intraday_frame(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        "时间": "time",
        "日期时间": "time",
        "最新价": "price",
        "收盘": "price",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
    }
    df = df.rename(columns=rename_map).copy()
    if "time" not in df.columns or "price" not in df.columns:
        raise ValueError(f"unexpected intraday columns: {list(df.columns)}")
    df["time"] = pd.to_datetime(df["time"])
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    return df.dropna(subset=["time", "price"]).sort_values("time")


def fetch_intraday_series_from_akshare(prices: pd.DataFrame, clear_proxy: bool) -> Tuple[dict, List[str]]:
    if clear_proxy:
        clear_proxy_env()
    import akshare as ak

    warnings = []
    series = {}
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=5)
    start_text = start_dt.strftime("%Y-%m-%d 09:30:00")
    end_text = end_dt.strftime("%Y-%m-%d 15:30:00")
    derived = build_derived_intraday_series(prices)
    for code, name in ETF_UNIVERSE.items():
        if code not in prices.columns:
            continue
        try:
            df = ak.fund_etf_hist_min_em(
                symbol=code,
                start_date=start_text,
                end_date=end_text,
                period="1",
                adjust="",
            )
            df = normalize_intraday_frame(df)
            if df.empty:
                raise ValueError("empty intraday response")
            # Keep the latest trading day returned by the provider.
            latest_day = df["time"].dt.date.max()
            df = df[df["time"].dt.date == latest_day].tail(260)
            series[code] = {
                "code": code,
                "name": name,
                "source": "akshare_minute",
                "period": "1",
                "points": [
                    {
                        "time": row.time.strftime("%Y-%m-%d %H:%M"),
                        "price": float(row.price),
                    }
                    for row in df.itertuples(index=False)
                ],
            }
        except Exception as exc:
            warnings.append(f"{code} minute data fallback: {exc}")
            series[code] = derived.get(code, {"code": code, "name": name, "source": "derived_from_daily", "period": "1", "points": []})
    return series, warnings


def normalize_futu_intraday_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={"time_key": "time", "close": "price"}).copy()
    if "time" not in df.columns or "price" not in df.columns:
        raise ValueError(f"unexpected Futu intraday columns: {list(df.columns)}")
    df["time"] = pd.to_datetime(df["time"])
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    return df.dropna(subset=["time", "price"]).sort_values("time")


def fetch_futu_one_intraday(quote_ctx, symbol: str, start: str, end: str, kl_type, au_type) -> pd.DataFrame:
    prepare_futu_env()
    from futu import RET_OK

    frames: List[pd.DataFrame] = []
    page_req_key = None
    while True:
        ret, data, page_req_key = quote_ctx.request_history_kline(
            symbol,
            start=start,
            end=end,
            ktype=kl_type.K_1M,
            autype=au_type.QFQ,
            max_count=1000,
            page_req_key=page_req_key,
        )
        if ret != RET_OK:
            raise RuntimeError(str(data))
        frames.append(data)
        if page_req_key is None:
            break
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def fetch_intraday_series_from_futu(prices: pd.DataFrame, config: BacktestConfig) -> Tuple[dict, List[str]]:
    prepare_futu_env()
    try:
        from futu import AuType, KLType, OpenQuoteContext
    except ImportError as exc:
        raise RuntimeError("futu-api is not installed. Install it with: pip install futu-api") from exc

    warnings = []
    series = {}
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=5)
    start_text = start_dt.strftime("%Y-%m-%d")
    end_text = end_dt.strftime("%Y-%m-%d")
    derived = build_derived_intraday_series(prices)
    quote_ctx = OpenQuoteContext(host=config.futu_host, port=config.futu_port)
    try:
        for code, name in ETF_UNIVERSE.items():
            if code not in prices.columns:
                continue
            try:
                symbol = futu_symbol(code)
                df = fetch_futu_one_intraday(quote_ctx, symbol, start_text, end_text, KLType, AuType)
                df = normalize_futu_intraday_frame(df)
                if df.empty:
                    raise ValueError("empty intraday response")
                latest_day = df["time"].dt.date.max()
                df = df[df["time"].dt.date == latest_day].tail(260)
                series[code] = {
                    "code": code,
                    "name": name,
                    "source": "futu_minute",
                    "period": "1",
                    "points": [
                        {
                            "time": row.time.strftime("%Y-%m-%d %H:%M"),
                            "price": float(row.price),
                        }
                        for row in df.itertuples(index=False)
                    ],
                }
            except Exception as exc:
                warnings.append(f"{code} Futu minute data fallback: {exc}")
                series[code] = derived.get(code, {"code": code, "name": name, "source": "derived_from_daily", "period": "1", "points": []})
    finally:
        quote_ctx.close()
    return series, warnings


def build_market_snapshot(prices: pd.DataFrame, intraday_series: dict, source: str, warnings: List[str]) -> dict:
    items = []
    for code, name in ETF_UNIVERSE.items():
        if code not in prices.columns:
            continue
        close = prices[code].dropna()
        latest_close = float(close.iloc[-1]) if len(close) else None
        prev_close = float(close.iloc[-2]) if len(close) > 1 else None
        daily_return = latest_close / prev_close - 1 if latest_close and prev_close else None
        minute_points = intraday_series.get(code, {}).get("points", [])
        latest_minute = minute_points[-1]["price"] if minute_points else latest_close
        items.append(
            {
                "code": code,
                "name": name,
                "source": source,
                "latest_price": latest_minute,
                "latest_close": latest_close,
                "prev_close": prev_close,
                "daily_return": daily_return,
                "updated_at": minute_points[-1]["time"] if minute_points else close.index[-1].strftime("%Y-%m-%d"),
            }
        )
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": source,
        "warnings": warnings,
        "items": items,
    }


def build_intraday_outputs(prices: pd.DataFrame, config: BacktestConfig, data_mode: str) -> Tuple[dict, dict]:
    warnings: List[str] = []
    if data_mode.startswith("futu"):
        try:
            intraday_series, warnings = fetch_intraday_series_from_futu(prices, config)
            source = "futu_minute" if not warnings else "futu_minute_mixed"
        except Exception as exc:
            warnings = [f"Futu minute data unavailable, using derived intraday: {exc}"]
            intraday_series = build_derived_intraday_series(prices)
            source = "derived_from_daily"
    elif data_mode.startswith("akshare") or data_mode == "cached":
        try:
            intraday_series, warnings = fetch_intraday_series_from_akshare(prices, config.clear_proxy)
            source = "akshare_minute" if not warnings else "akshare_minute_mixed"
        except Exception as exc:
            warnings = [f"AkShare minute data unavailable, using derived intraday: {exc}"]
            intraday_series = build_derived_intraday_series(prices)
            source = "derived_from_daily"
    else:
        intraday_series = build_derived_intraday_series(prices)
        source = "derived_from_daily"
        warnings = ["Synthetic run: intraday is derived from daily synthetic prices, not realtime quotes."]
    return intraday_series, build_market_snapshot(prices, intraday_series, source, warnings)


def save_outputs(results: Dict[str, pd.DataFrame | pd.Series | dict], config: BacktestConfig, load_result: PriceLoadResult) -> None:
    import matplotlib.pyplot as plt

    prices = results["prices"]
    equity_curve = results["equity_curve"]
    daily_weights = results["daily_weights"]
    rebalance_log = results["rebalance_log"]
    metrics = results["metrics"]
    data_quality = load_result.data_quality
    run_meta = build_run_meta(config, load_result)
    price_series = build_price_series(prices)
    intraday_series, market_snapshot = build_intraday_outputs(prices, config, load_result.actual_data_mode)

    assert isinstance(prices, pd.DataFrame)
    assert isinstance(equity_curve, pd.DataFrame)
    assert isinstance(daily_weights, pd.DataFrame)
    assert isinstance(rebalance_log, pd.DataFrame)
    assert isinstance(metrics, dict)

    prices.to_csv(OUTPUT_DIR / "prices_used.csv", encoding="utf-8-sig")
    equity_curve.to_csv(OUTPUT_DIR / "equity_curve.csv", encoding="utf-8-sig")
    daily_weights.to_csv(OUTPUT_DIR / "daily_weights.csv", encoding="utf-8-sig")
    rebalance_log.to_csv(OUTPUT_DIR / "rebalance_log.csv", index=False, encoding="utf-8-sig")
    data_quality.to_csv(OUTPUT_DIR / "data_quality.csv", index=False, encoding="utf-8-sig")
    (OUTPUT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT_DIR / "data_quality.json").write_text(
        json.dumps(clean_records(data_quality), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUTPUT_DIR / "run_meta.json").write_text(json.dumps(run_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT_DIR / "price_series.json").write_text(
        json.dumps(price_series, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUTPUT_DIR / "intraday_series.json").write_text(
        json.dumps(intraday_series, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUTPUT_DIR / "market_snapshot.json").write_text(
        json.dumps(market_snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with pd.ExcelWriter(OUTPUT_DIR / "results.xlsx", engine="openpyxl") as writer:
        pd.DataFrame([metrics]).to_excel(writer, sheet_name="metrics", index=False)
        pd.DataFrame([run_meta]).to_excel(writer, sheet_name="run_meta", index=False)
        data_quality.to_excel(writer, sheet_name="data_quality", index=False)
        equity_curve.to_excel(writer, sheet_name="equity_curve")
        rebalance_log.to_excel(writer, sheet_name="rebalance_log", index=False)
        daily_weights.tail(260).to_excel(writer, sheet_name="weights_last_260d")

    plt.figure(figsize=(12, 6))
    plt.plot(equity_curve.index, equity_curve["strategy"], label="ETF rotation", linewidth=2.2)
    plt.plot(equity_curve.index, equity_curve["benchmark_equal_weight"], label="Equal-weight benchmark", linewidth=1.6)
    plt.title("ETF Rotation Backtest")
    plt.xlabel("Date")
    plt.ylabel("Net Asset Value")
    plt.grid(True, alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "equity_curve.png", dpi=160)
    plt.close()

    report = build_report(metrics, config, load_result.actual_data_mode, data_quality)
    (OUTPUT_DIR / "report.md").write_text(report, encoding="utf-8")


def build_report(metrics: dict, config: BacktestConfig, data_mode: str, data_quality: pd.DataFrame) -> str:
    quality_counts = data_quality["status"].value_counts().to_dict()
    warning_count = int(quality_counts.get("warning", 0))
    error_count = int(quality_counts.get("error", 0))
    return f"""# ETF 动量轮动回测报告

## 配置

- 数据模式：{data_mode}
- 回测区间：{metrics["start"]} 至 {metrics["end"]}
- 调仓频率：{config.rebalance}
- 持仓数量：Top {config.top_n}
- 单边交易成本：{pct(config.fee_rate)}
- 波动率惩罚：{config.risk_penalty}
- 正动量过滤窗口：{config.min_momentum_window} 日
- 数据质量：ok {int(quality_counts.get("ok", 0))} / warning {warning_count} / error {error_count}

## 策略结果

- 总收益：{pct(metrics["total_return"])}
- 年化收益：{pct(metrics["annualized_return"])}
- 年化波动：{pct(metrics["annualized_volatility"])}
- 夏普比率：{metrics["sharpe_no_risk_free"]:.2f}
- 最大回撤：{pct(metrics["max_drawdown"])}
- 最大回撤区间：{metrics["max_drawdown_peak"]} 至 {metrics["max_drawdown_trough"]}
- Calmar：{metrics["calmar"]:.2f}
- 日胜率：{pct(metrics["win_rate_daily"])}
- 平均每日换手：{pct(metrics["avg_daily_turnover"])}
- 调仓次数：{metrics["rebalance_count"]}
- 平均持仓数量：{metrics["avg_holding_count"]:.2f}

## 等权基准

- 基准总收益：{pct(metrics["benchmark_total_return"])}
- 基准年化收益：{pct(metrics["benchmark_annualized_return"])}
- 基准年化波动：{pct(metrics["benchmark_annualized_volatility"])}
- 基准最大回撤：{pct(metrics["benchmark_max_drawdown"])}

## 下一步

1. 使用真实 AkShare/Tushare 数据重新跑一遍。
2. 加入成交额过滤，避免买到流动性差的 ETF。
3. 做参数稳定性测试：Top N、20/60/120 权重、周频/月频。
4. 加入样本外验证，例如 2018-2022 优化，2023-2026 验证。
5. 接入模拟盘前，先增加日志、异常处理和风控上限。
"""


def print_summary(metrics: dict, load_result: PriceLoadResult) -> None:
    quality_counts = load_result.data_quality["status"].value_counts().to_dict()
    print("\nBacktest complete")
    print(f"Data mode: {load_result.actual_data_mode}")
    print(f"Data quality: {quality_counts}")
    print(f"Period: {metrics['start']} -> {metrics['end']} ({metrics['trading_days']} trading days)")
    print(f"Strategy total return: {pct(metrics['total_return'])}")
    print(f"Strategy annualized return: {pct(metrics['annualized_return'])}")
    print(f"Strategy max drawdown: {pct(metrics['max_drawdown'])}")
    print(f"Benchmark total return: {pct(metrics['benchmark_total_return'])}")
    print(f"Outputs: {OUTPUT_DIR}")


def main() -> None:
    try:
        config = parse_args()
        ensure_dirs()
        load_result = load_prices(config)
        results = run_backtest(load_result.prices, config)
        save_outputs(results, config, load_result)
        print_summary(results["metrics"], load_result)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
