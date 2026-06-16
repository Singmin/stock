from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from etf_rotation_backtest import (
    BacktestConfig,
    OUTPUT_DIR,
    build_intraday_outputs,
    ensure_dirs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh ETF intraday market output only")
    parser.add_argument("--data-source", choices=["futu", "akshare", "cached"], default="futu")
    parser.add_argument("--clear-proxy", action="store_true")
    parser.add_argument("--futu-host", default="127.0.0.1")
    parser.add_argument("--futu-port", type=int, default=11111)
    return parser.parse_args()


def load_prices_used() -> pd.DataFrame:
    path = OUTPUT_DIR / "prices_used.csv"
    if not path.exists():
        raise FileNotFoundError("Missing output/prices_used.csv. Run etf_rotation_backtest.py first.")
    prices = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    if prices.empty:
        raise ValueError("output/prices_used.csv is empty")
    return prices.apply(pd.to_numeric, errors="coerce")


def write_json_atomic(path: Path, payload: object) -> None:
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def main() -> None:
    args = parse_args()
    try:
        ensure_dirs()
        prices = load_prices_used()
        config = BacktestConfig(
            start=prices.index[0].strftime("%Y-%m-%d"),
            end=pd.Timestamp.today().strftime("%Y-%m-%d"),
            data_source=args.data_source,
            rebalance="W-FRI",
            top_n=2,
            fee_rate=0.0008,
            risk_penalty=0.15,
            min_momentum_window=120,
            clear_proxy=args.clear_proxy,
            futu_host=args.futu_host,
            futu_port=args.futu_port,
        )
        intraday_series, market_snapshot = build_intraday_outputs(prices, config, args.data_source)
        if args.data_source == "futu" and not any(
            item.get("source") == "futu_minute" for item in intraday_series.values()
        ):
            raise RuntimeError("Futu minute data unavailable; keeping previous intraday output.")
        write_json_atomic(OUTPUT_DIR / "intraday_series.json", intraday_series)
        write_json_atomic(OUTPUT_DIR / "market_snapshot.json", market_snapshot)
        print(
            json.dumps(
                {
                    "ok": True,
                    "source": market_snapshot.get("source"),
                    "generated_at": market_snapshot.get("generated_at"),
                    "warnings": market_snapshot.get("warnings", []),
                },
                ensure_ascii=False,
            )
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
