from __future__ import annotations

import argparse
import time

from futu_sim_common import (
    OUTPUT_DIR,
    TRADE_ENV,
    account_from_snapshot,
    append_jsonl,
    get_portfolio,
    get_today_orders,
    load_account_snapshot,
    now_text,
    place_sim_order,
    print_json,
    read_json,
    write_json,
)


def execute_orders(confirmed: bool, delay: float) -> dict:
    if not confirmed:
        raise RuntimeError("Refusing to execute without --confirmed.")

    preview = read_json(OUTPUT_DIR / "futu_sim_order_preview.json")
    if not preview:
        raise FileNotFoundError("Missing output/futu_sim_order_preview.json. Run generate_futu_sim_orders.py first.")
    if preview.get("risk", {}).get("status") != "pass":
        raise RuntimeError("Order preview risk status is not pass; execution is blocked.")

    account = account_from_snapshot(load_account_snapshot())
    results = []
    for order in preview.get("orders", []):
        args = [
            "--code",
            order["code"],
            "--side",
            order["side"],
            "--quantity",
            str(int(order["quantity"])),
            "--price",
            str(float(order["price"])),
            "--order-type",
            order.get("order_type", "NORMAL"),
            "--trd-env",
            TRADE_ENV,
            "--acc-id",
            str(account["acc_id"]),
        ]
        firm = str(account.get("security_firm") or "")
        if firm and firm != "NONE":
            args += ["--security-firm", firm]
        started_at = now_text()
        try:
            result = place_sim_order(account, order)
            row = {"started_at": started_at, "finished_at": now_text(), "ok": True, "order": order, "result": result}
        except Exception as exc:
            row = {"started_at": started_at, "finished_at": now_text(), "ok": False, "order": order, "error": str(exc)}
        append_jsonl(OUTPUT_DIR / "futu_sim_execution_log.jsonl", row)
        results.append(row)
        time.sleep(delay)

    orders_snapshot = get_today_orders(account)
    portfolio_snapshot = get_portfolio(account)
    write_json(OUTPUT_DIR / "futu_sim_recent_orders.json", {"generated_at": now_text(), **orders_snapshot})
    write_json(
        OUTPUT_DIR / "futu_sim_positions.json",
        {
            "generated_at": now_text(),
            "funds": portfolio_snapshot.get("funds", {}),
            "positions": portfolio_snapshot.get("positions", []),
        },
    )
    payload = {
        "generated_at": now_text(),
        "ok": all(row["ok"] for row in results),
        "submitted_count": sum(1 for row in results if row["ok"]),
        "failed_count": sum(1 for row in results if not row["ok"]),
        "results": results,
        "orders_snapshot": orders_snapshot,
    }
    write_json(OUTPUT_DIR / "futu_sim_last_execution.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute latest Futu SIMULATE ETF order preview.")
    parser.add_argument("--confirmed", action="store_true", help="Required. Confirms simulated order execution.")
    parser.add_argument("--delay", type=float, default=0.08, help="Delay between simulated orders in seconds")
    args = parser.parse_args()
    payload = execute_orders(args.confirmed, args.delay)
    print_json(payload)
    raise SystemExit(0 if payload["ok"] else 1)


if __name__ == "__main__":
    main()
