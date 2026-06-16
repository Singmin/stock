from __future__ import annotations

import argparse

from futu_sim_common import (
    OUTPUT_DIR,
    account_supports_cn,
    choose_sim_account,
    get_accounts,
    now_text,
    opend_reachable,
    print_json,
    sdk_version,
    write_json,
)


def build_preflight(host: str, port: int) -> dict:
    version = sdk_version()
    port_ok = opend_reachable(host, port)
    accounts = []
    selected = None
    errors = []
    warnings = []

    if not version:
        errors.append("futu-api is not installed.")
    if not port_ok:
        errors.append(f"OpenD is not reachable at {host}:{port}.")

    if version and port_ok:
        try:
            payload = get_accounts()
            accounts = payload.get("accounts", [])
            selected = choose_sim_account(accounts)
            if not selected:
                errors.append("No SIMULATE account with CN/SH/SZ trading permission was found.")
        except Exception as exc:
            errors.append(f"Failed to query Futu accounts: {exc}")

    unsupported = [
        account
        for account in accounts
        if str(account.get("trd_env", "")).upper() == "SIMULATE" and not account_supports_cn(account)
    ]
    if unsupported:
        warnings.append(f"{len(unsupported)} SIMULATE account(s) do not include CN/SH/SZ permission.")

    result = {
        "generated_at": now_text(),
        "ok": len(errors) == 0,
        "host": host,
        "port": port,
        "sdk_version": version or "missing",
        "opend_reachable": port_ok,
        "target_env": "SIMULATE",
        "target_market": "CN",
        "selected_account": selected,
        "accounts": accounts,
        "warnings": warnings,
        "errors": errors,
        "message": "Futu SIMULATE account is ready." if len(errors) == 0 else "Futu SIMULATE preflight failed.",
    }
    write_json(OUTPUT_DIR / "futu_sim_account.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Futu OpenD and SIMULATE account readiness.")
    parser.add_argument("--host", default="127.0.0.1", help="Futu OpenD host")
    parser.add_argument("--port", type=int, default=11111, help="Futu OpenD port")
    args = parser.parse_args()
    result = build_preflight(args.host, args.port)
    print_json(result)
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
