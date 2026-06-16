from __future__ import annotations

import argparse
from typing import Any, Dict, List

from futu_sim_common import (
    ETF_UNIVERSE,
    LOT_SIZE,
    OUTPUT_DIR,
    TRADE_ENV,
    account_from_snapshot,
    futu_symbol,
    get_portfolio,
    load_account_snapshot,
    load_trade_signal,
    now_text,
    print_json,
    safe_float,
    safe_int,
    write_csv,
    write_json,
)


def round_to_lot(raw_qty: float) -> int:
    return int(raw_qty // LOT_SIZE) * LOT_SIZE


def portfolio_maps(portfolio: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    funds = portfolio.get("funds") or {}
    positions = {}
    for item in portfolio.get("positions", []):
        code = str(item.get("code") or "")
        if code:
            positions[code] = item
    return funds, positions


def normalized_target_weights(weights: Dict[str, float]) -> Dict[str, float]:
    positive = {code: weight for code, weight in weights.items() if weight > 0}
    total = sum(positive.values())
    if total <= 0:
        return {}
    return {code: weight / total for code, weight in positive.items()}


def append_order(
    rows: List[Dict[str, Any]],
    *,
    code: str,
    local_code: str,
    name: str,
    side: str,
    quantity: int,
    price: float,
    target_weight: float,
    current_qty: int,
    can_sell_qty: int,
    current_value: float,
    target_value: float,
) -> None:
    if quantity <= 0:
        return
    rows.append(
        {
            "code": code,
            "local_code": local_code,
            "name": name,
            "side": side,
            "quantity": quantity,
            "price": round(price, 4),
            "order_type": "NORMAL",
            "target_weight": target_weight,
            "current_qty": current_qty,
            "can_sell_qty": can_sell_qty,
            "current_value": round(current_value, 2),
            "target_value": round(target_value, 2),
            "estimated_value": round(quantity * price, 2),
        }
    )


def build_orders(args: argparse.Namespace) -> dict:
    if args.trd_env != TRADE_ENV:
        raise RuntimeError("Only SIMULATE trading is supported by this project workflow.")

    signal = load_trade_signal()
    account_snapshot = load_account_snapshot()
    account = account_from_snapshot(account_snapshot)
    portfolio = get_portfolio(account)
    funds, positions = portfolio_maps(portfolio)

    total_assets = safe_float(funds.get("total_assets"))
    available_funds = safe_float(funds.get("available_funds"), safe_float(funds.get("cash")))
    if total_assets <= 0:
        raise RuntimeError("Account total_assets is zero; cannot generate order preview.")

    targets = signal.get("targets") or []
    prices = {str(item.get("futu_code")): safe_float(item.get("latest_price")) for item in targets}
    weights = {str(item.get("futu_code")): safe_float(item.get("target_weight")) for item in targets}
    unknown_codes = [code for code in weights if code.split(".", 1)[-1] not in ETF_UNIVERSE]
    if unknown_codes:
        raise RuntimeError(f"Target contains unsupported ETF code(s): {', '.join(unknown_codes)}")

    rows: List[Dict[str, Any]] = []
    risk_errors: List[str] = []
    risk_warnings: List[str] = []
    mode_notes: List[str] = []
    reserved_cash = total_assets * args.cash_buffer
    normalized_weights = normalized_target_weights(weights)

    if args.mode == "observe":
        mode_notes.append("Observe mode: no executable orders are generated.")
    elif not normalized_weights:
        risk_warnings.append("Strategy target is empty; no orders generated.")

    if args.mode == "full-account":
        for code, position in positions.items():
            if code.split(".", 1)[-1] in ETF_UNIVERSE:
                continue
            current_qty = safe_int(position.get("qty"))
            can_sell_qty = safe_int(position.get("can_sell_qty"), current_qty)
            price = safe_float(position.get("current_price"), safe_float(position.get("nominal_price")))
            quantity = min(current_qty, can_sell_qty)
            current_value = safe_float(position.get("market_val"), quantity * price)
            if quantity <= 0 or current_value < args.min_order_value:
                continue
            append_order(
                rows,
                code=code,
                local_code=code.split(".", 1)[-1],
                name=str(position.get("name") or code),
                side="SELL",
                quantity=quantity,
                price=price,
                target_weight=0.0,
                current_qty=current_qty,
                can_sell_qty=can_sell_qty,
                current_value=current_value,
                target_value=0.0,
            )
    elif args.mode == "cash-only":
        mode_notes.append("Cash-only mode: existing non-ETF positions will not be sold.")

    for local_code, name in ETF_UNIVERSE.items():
        code = futu_symbol(local_code)
        price = prices.get(code, 0.0)
        target_weight = weights.get(code, 0.0)
        position = positions.get(code, {})
        current_qty = safe_int(position.get("qty"))
        can_sell_qty = safe_int(position.get("can_sell_qty"), current_qty)
        current_value = safe_float(position.get("market_val"), current_qty * price)
        if args.mode == "observe":
            target_value = current_value
        elif args.mode == "cash-only":
            deployable_cash = max(0.0, available_funds - reserved_cash)
            target_universe_value = sum(
                safe_float(positions.get(target_code, {}).get("market_val"))
                for target_code in normalized_weights
            )
            target_value = (target_universe_value + deployable_cash) * normalized_weights.get(code, 0.0)
        else:
            target_value = total_assets * (1 - args.cash_buffer) * target_weight
        diff_value = target_value - current_value

        if price <= 0 and abs(diff_value) >= args.min_order_value:
            risk_errors.append(f"{code} has no usable price.")
            continue

        if diff_value > args.min_order_value:
            quantity = round_to_lot(diff_value / price)
            side = "BUY"
        elif diff_value < -args.min_order_value and args.mode == "full-account":
            quantity = min(round_to_lot(abs(diff_value) / price), round_to_lot(can_sell_qty))
            side = "SELL"
        elif diff_value < -args.min_order_value and args.mode == "cash-only":
            risk_warnings.append(f"{code} is above cash-only target; no sell order generated.")
            quantity = 0
            side = "HOLD"
        else:
            quantity = 0
            side = "HOLD"

        order_value = quantity * price
        if quantity <= 0:
            continue
        if side == "BUY" and quantity % LOT_SIZE != 0:
            risk_errors.append(f"{code} quantity {quantity} is not a {LOT_SIZE}-share lot.")
        if order_value > args.max_single_order_value:
            risk_errors.append(f"{code} order value {order_value:.2f} exceeds max single order value.")
        if side == "SELL" and quantity > can_sell_qty:
            risk_errors.append(f"{code} sell quantity exceeds can_sell_qty.")

        append_order(
            rows,
            code=code,
            local_code=local_code,
            name=name,
            side=side,
            quantity=quantity,
            price=price,
            target_weight=target_weight,
            current_qty=current_qty,
            can_sell_qty=can_sell_qty,
            current_value=current_value,
            target_value=target_value,
        )

    rows.sort(key=lambda row: 0 if row["side"] == "SELL" else 1)
    sell_value = sum(row["estimated_value"] for row in rows if row["side"] == "SELL")
    buy_value = sum(row["estimated_value"] for row in rows if row["side"] == "BUY")
    gross_value = sell_value + buy_value

    if gross_value > args.max_total_order_value:
        risk_errors.append(f"Total order value {gross_value:.2f} exceeds max total order value.")
    if total_assets > 0 and gross_value / total_assets > args.max_turnover:
        risk_errors.append(f"Estimated turnover {gross_value / total_assets:.2%} exceeds max turnover.")
    if buy_value > available_funds + sell_value:
        risk_errors.append("Estimated buys exceed available funds plus planned sells.")
    if available_funds + sell_value - buy_value < reserved_cash:
        risk_errors.append("Estimated remaining cash is below configured cash buffer.")

    risk = {
        "status": "blocked" if risk_errors else "pass",
        "errors": risk_errors,
        "warnings": risk_warnings,
        "rules": {
            "mode": args.mode,
            "trd_env": TRADE_ENV,
            "lot_size": LOT_SIZE,
            "cash_buffer": args.cash_buffer,
            "min_order_value": args.min_order_value,
            "max_single_order_value": args.max_single_order_value,
            "max_total_order_value": args.max_total_order_value,
            "max_turnover": args.max_turnover,
        },
    }

    preview = {
        "generated_at": now_text(),
        "account": account,
        "trade_signal": {
            "generated_at": signal.get("generated_at"),
            "signal_date": signal.get("signal_date"),
            "suggested_rebalance_date": signal.get("suggested_rebalance_date"),
            "data_mode": signal.get("data_mode"),
        },
        "funds": funds,
        "mode": {
            "selected": args.mode,
            "label": {
                "observe": "观察模式",
                "cash-only": "只用现金调仓",
                "full-account": "全账户调仓",
            }[args.mode],
            "notes": mode_notes,
        },
        "positions": portfolio.get("positions", []),
        "summary": {
            "total_assets": total_assets,
            "available_funds": available_funds,
            "reserved_cash": reserved_cash,
            "sell_value": round(sell_value, 2),
            "buy_value": round(buy_value, 2),
            "gross_order_value": round(gross_value, 2),
            "order_count": len(rows),
        },
        "risk": risk,
        "orders": rows,
    }
    write_json(OUTPUT_DIR / "futu_sim_positions.json", {"generated_at": now_text(), "funds": funds, "positions": portfolio.get("positions", [])})
    write_json(OUTPUT_DIR / "futu_sim_order_preview.json", preview)
    write_csv(
        OUTPUT_DIR / "futu_sim_orders.csv",
        rows,
        [
            "code",
            "local_code",
            "name",
            "side",
            "quantity",
            "price",
            "order_type",
            "target_weight",
            "current_qty",
            "can_sell_qty",
            "current_value",
            "target_value",
            "estimated_value",
        ],
    )
    return preview


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Futu SIMULATE ETF order preview from latest strategy signal.")
    parser.add_argument("--trd-env", default=TRADE_ENV, choices=[TRADE_ENV], help="Trading environment, fixed to SIMULATE")
    parser.add_argument(
        "--mode",
        choices=["observe", "cash-only", "full-account"],
        default="observe",
        help="observe=no orders, cash-only=buy target ETFs with cash only, full-account=liquidate non-universe positions and rebalance",
    )
    parser.add_argument("--cash-buffer", type=float, default=0.05, help="Minimum cash reserve as a fraction of total assets")
    parser.add_argument("--min-order-value", type=float, default=100.0, help="Ignore small differences below this amount")
    parser.add_argument("--max-single-order-value", type=float, default=100000.0, help="Block any single order above this amount")
    parser.add_argument("--max-total-order-value", type=float, default=500000.0, help="Block total order value above this amount")
    parser.add_argument("--max-turnover", type=float, default=1.0, help="Block if gross order value / total assets exceeds this ratio")
    args = parser.parse_args()
    preview = build_orders(args)
    print_json(preview)
    raise SystemExit(0 if preview["risk"]["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
