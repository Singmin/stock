from __future__ import annotations

import csv
import importlib.metadata
import json
import os
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
FUTU_APPDATA_DIR = ROOT / ".futu_appdata"
SKILL_SCRIPT_DIR = ROOT.parent / ".codex" / "skills" / "futuapi" / "scripts"
TRADE_ENV = "SIMULATE"
TARGET_MARKET = "CN"
LOT_SIZE = 100

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


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def futu_symbol(code: str) -> str:
    if code.startswith(("5", "6")):
        return f"SH.{code}"
    return f"SZ.{code}"


def local_code(futu_code: str) -> str:
    return futu_code.split(".", 1)[1] if "." in futu_code else futu_code


def now_text() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    ensure_output_dir()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: Iterable[Dict[str, Any]], fields: List[str]) -> None:
    ensure_output_dir()
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    ensure_output_dir()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def sdk_version() -> str:
    try:
        return importlib.metadata.version("futu-api")
    except importlib.metadata.PackageNotFoundError:
        return ""


def opend_reachable(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def skill_script_path(category: str, script_name: str) -> Path:
    path = SKILL_SCRIPT_DIR / category / script_name
    if not path.exists():
        raise FileNotFoundError(f"Futu skill script not found: {path}")
    return path


def skill_env() -> Dict[str, str]:
    env = os.environ.copy()
    (FUTU_APPDATA_DIR / "com.futunn.FutuOpenD" / "Log").mkdir(parents=True, exist_ok=True)
    for key in list(env):
        if key.lower() == "appdata":
            env.pop(key, None)
    env["appdata"] = str(FUTU_APPDATA_DIR)
    env.setdefault("FUTU_TRD_ENV", TRADE_ENV)
    return env


def run_skill_json(category: str, script_name: str, args: List[str], timeout: int = 60) -> Dict[str, Any]:
    command = [sys.executable, str(skill_script_path(category, script_name)), *args, "--json"]
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        env=skill_env(),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
    )
    output = (proc.stdout or "").strip()
    if proc.returncode != 0:
        error_text = "\n".join(
            part for part in [(proc.stderr or "").strip(), output, f"exit code {proc.returncode}"] if part
        )
        raise RuntimeError(error_text)
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Expected JSON from {script_name}, got: {output[:500]}") from exc


def account_supports_cn(account: Dict[str, Any]) -> bool:
    auth = {str(item).upper() for item in account.get("trdmarket_auth", [])}
    return TARGET_MARKET in auth or "SH" in auth or "SZ" in auth


def choose_sim_account(accounts: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    candidates = [
        account
        for account in accounts
        if str(account.get("trd_env", "")).upper() == TRADE_ENV
        and str(account.get("acc_role", "")).upper() != "MASTER"
        and account_supports_cn(account)
    ]
    if not candidates:
        return None
    stock_and_option = [a for a in candidates if str(a.get("sim_acc_type", "")).upper() == "STOCK_AND_OPTION"]
    return (stock_and_option or candidates)[0]


def get_accounts() -> Dict[str, Any]:
    env = skill_env()
    old_env = os.environ.copy()
    try:
        os.environ.clear()
        os.environ.update(env)
        from futu import OpenSecTradeContext, SecurityFirm, TrdMarket

        firms = [
            SecurityFirm.NONE,
            SecurityFirm.FUTUSECURITIES,
            SecurityFirm.FUTUINC,
            SecurityFirm.FUTUSG,
            SecurityFirm.FUTUAU,
            SecurityFirm.FUTUCA,
            SecurityFirm.FUTUJP,
            SecurityFirm.FUTUMY,
        ]
        seen = set()
        accounts = []
        for firm in firms:
            ctx = None
            try:
                ctx = OpenSecTradeContext(
                    filter_trdmarket=TrdMarket.NONE,
                    host=os.getenv("FUTU_OPEND_HOST", "127.0.0.1"),
                    port=int(os.getenv("FUTU_OPEND_PORT", "11111")),
                    security_firm=firm,
                )
                ret, data = ctx.get_acc_list()
                if ret != 0 or data is None or len(data) == 0:
                    continue
                for _, row in data.iterrows():
                    acc = parse_account_row(row)
                    if acc["acc_id"] in seen or acc["acc_status"] == "DISABLED":
                        continue
                    seen.add(acc["acc_id"])
                    accounts.append(acc)
            except Exception:
                continue
            finally:
                if ctx is not None:
                    ctx.close()
        return {"accounts": accounts}
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def format_enum(value: Any) -> str:
    text = str(value)
    if "." in text:
        return text.rsplit(".", 1)[-1]
    return text


def parse_trdmarket_auth(value: Any) -> List[str]:
    if isinstance(value, list):
        return [format_enum(item) for item in value]
    if isinstance(value, str):
        return [item.strip() for item in value.strip("[]").split(",") if item.strip()]
    try:
        import pandas as pd

        if value is pd.NA:
            return []
    except Exception:
        pass
    return []


def parse_account_row(row: Any) -> Dict[str, Any]:
    sim_acc_type = format_enum(row.get("sim_acc_type", "NONE"))
    competition_name = row.get("competition_acc_name", "")
    return {
        "acc_id": safe_int(row.get("acc_id")),
        "acc_type": format_enum(row.get("acc_type", "")),
        "acc_role": format_enum(row.get("acc_role", "")),
        "trd_env": format_enum(row.get("trd_env", "")),
        "card_num": str(row.get("card_num", "")),
        "security_firm": format_enum(row.get("security_firm", "")),
        "trdmarket_auth": parse_trdmarket_auth(row.get("trdmarket_auth", [])),
        "acc_status": format_enum(row.get("acc_status", "")),
        "sim_acc_type": sim_acc_type,
        "competition_acc_name": competition_name if sim_acc_type == "COMPETITION" and competition_name else "N/A",
    }


def get_portfolio(account: Dict[str, Any]) -> Dict[str, Any]:
    env = skill_env()
    old_env = os.environ.copy()
    try:
        os.environ.clear()
        os.environ.update(env)
        from futu import OpenSecTradeContext, TrdEnv, TrdMarket

        ctx = OpenSecTradeContext(
            filter_trdmarket=TrdMarket.CN,
            host=os.getenv("FUTU_OPEND_HOST", "127.0.0.1"),
            port=int(os.getenv("FUTU_OPEND_PORT", "11111")),
            security_firm=parse_security_firm(account.get("security_firm")),
        )
        try:
            ret, acc_data = ctx.accinfo_query(trd_env=TrdEnv.SIMULATE, acc_id=int(account["acc_id"]), refresh_cache=True)
            if ret != 0:
                raise RuntimeError(str(acc_data))
            ret, pos_data = ctx.position_list_query(
                trd_env=TrdEnv.SIMULATE,
                acc_id=int(account["acc_id"]),
                refresh_cache=True,
            )
            if ret != 0:
                raise RuntimeError(str(pos_data))
            funds = parse_funds(acc_data)
            snapshot_map = fetch_position_snapshots(pos_data)
            return {"funds": funds, "positions": parse_positions(pos_data, snapshot_map, safe_float(funds.get("total_assets")))}
        finally:
            ctx.close()
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def get_today_orders(account: Dict[str, Any]) -> Dict[str, Any]:
    env = skill_env()
    old_env = os.environ.copy()
    try:
        os.environ.clear()
        os.environ.update(env)
        from futu import OpenSecTradeContext, TrdEnv, TrdMarket

        ctx = OpenSecTradeContext(
            filter_trdmarket=TrdMarket.CN,
            host=os.getenv("FUTU_OPEND_HOST", "127.0.0.1"),
            port=int(os.getenv("FUTU_OPEND_PORT", "11111")),
            security_firm=parse_security_firm(account.get("security_firm")),
        )
        try:
            ret, data = ctx.order_list_query(trd_env=TrdEnv.SIMULATE, acc_id=int(account["acc_id"]), refresh_cache=True)
            if ret != 0:
                raise RuntimeError(str(data))
            return {"market": TARGET_MARKET, "orders": parse_orders(data)}
        finally:
            ctx.close()
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def place_sim_order(account: Dict[str, Any], order: Dict[str, Any]) -> Dict[str, Any]:
    env = skill_env()
    old_env = os.environ.copy()
    try:
        os.environ.clear()
        os.environ.update(env)
        from futu import OpenSecTradeContext, OrderType, TrdEnv, TrdMarket, TrdSide

        side = TrdSide.BUY if str(order["side"]).upper() == "BUY" else TrdSide.SELL
        order_type = OrderType.MARKET if str(order.get("order_type", "")).upper() == "MARKET" else OrderType.NORMAL
        ctx = OpenSecTradeContext(
            filter_trdmarket=TrdMarket.CN,
            host=os.getenv("FUTU_OPEND_HOST", "127.0.0.1"),
            port=int(os.getenv("FUTU_OPEND_PORT", "11111")),
            security_firm=parse_security_firm(account.get("security_firm")),
        )
        try:
            ret, data = ctx.place_order(
                price=float(order["price"]),
                qty=int(order["quantity"]),
                code=str(order["code"]),
                trd_side=side,
                order_type=order_type,
                trd_env=TrdEnv.SIMULATE,
                acc_id=int(account["acc_id"]),
            )
            if ret != 0:
                raise RuntimeError(str(data))
            if hasattr(data, "iloc") and len(data) > 0:
                row = data.iloc[0]
                order_id = row.get("order_id", row.get("orderID", ""))
            else:
                order_id = ""
            return {
                "order_id": str(order_id),
                "code": str(order["code"]),
                "side": str(order["side"]).upper(),
                "quantity": int(order["quantity"]),
                "price": float(order["price"]),
                "order_type": str(order.get("order_type", "NORMAL")).upper(),
                "trd_env": TRADE_ENV,
                "status": "submitted",
            }
        finally:
            ctx.close()
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def parse_security_firm(value: Any) -> Any:
    from futu import SecurityFirm

    key = str(value or "").upper()
    if key in {"", "N/A", "NONE"}:
        return SecurityFirm.NONE
    return getattr(SecurityFirm, key, SecurityFirm.NONE)


def first_row(df: Any) -> Any | None:
    if df is None or len(df) == 0:
        return None
    return df.iloc[0] if hasattr(df, "iloc") else df[0]


def parse_funds(data: Any) -> Dict[str, Any]:
    row = first_row(data)
    if row is None:
        return {}
    total_assets = safe_float(row.get("total_assets"))
    cash = safe_float(row.get("cash"))
    initial_margin = safe_float(row.get("initial_margin"))
    available_raw = row.get("available_funds", "N/A")
    available_funds = safe_float(available_raw)
    if str(available_raw) == "N/A" or available_raw in (None, ""):
        available_funds = cash if cash > 0 else total_assets - initial_margin if initial_margin > 0 else total_assets
    return {
        "currency": row.get("currency", "N/A"),
        "total_assets": total_assets,
        "cash": cash,
        "market_val": safe_float(row.get("market_val")),
        "long_mv": safe_float(row.get("long_mv")),
        "short_mv": safe_float(row.get("short_mv")),
        "frozen_cash": safe_float(row.get("frozen_cash")),
        "avl_withdrawal_cash": safe_float(row.get("avl_withdrawal_cash")),
        "power": safe_float(row.get("power", row.get("buying_power", 0))),
        "available_funds": available_funds,
        "initial_margin": initial_margin,
        "maintenance_margin": safe_float(row.get("maintenance_margin")),
        "risk_status": row.get("risk_status", "N/A"),
    }


def parse_positions(data: Any, snapshot_map: Dict[str, Dict[str, Any]] | None = None, total_assets: float = 0.0) -> List[Dict[str, Any]]:
    if data is None or len(data) == 0:
        return []
    snapshot_map = snapshot_map or {}
    rows = []
    for _, row in data.iterrows():
        code = row.get("code", "")
        qty = safe_float(row.get("qty"))
        average_cost = safe_float(row.get("average_cost"))
        nominal_price = safe_float(row.get("nominal_price"))
        market_val = safe_float(row.get("market_val"))
        unrealized_pl = safe_float(row.get("unrealized_pl"))
        pl_ratio = safe_float(row.get("pl_ratio_avg_cost"))
        today_pl = safe_float(row.get("today_pl_val"))
        snapshot = snapshot_map.get(code, {})
        current_price = safe_float(snapshot.get("last_price"), nominal_price)
        prev_close = safe_float(snapshot.get("prev_close_price"))
        if current_price <= 0:
            current_price = nominal_price
        if market_val <= 0 and current_price > 0:
            market_val = qty * current_price
        calculated_pl = (current_price - average_cost) * qty if average_cost > 0 and qty > 0 else unrealized_pl
        if abs(unrealized_pl) < 0.0001 and abs(calculated_pl) > 0.0001:
            unrealized_pl = calculated_pl
        calculated_ratio = (current_price / average_cost - 1) * 100 if average_cost > 0 and current_price > 0 else pl_ratio
        if abs(pl_ratio) < 0.0001 and abs(calculated_ratio) > 0.0001:
            pl_ratio = calculated_ratio
        today_ratio = (current_price / prev_close - 1) * 100 if prev_close > 0 and current_price > 0 else 0.0
        calculated_today_pl = (current_price - prev_close) * qty if prev_close > 0 and qty > 0 else today_pl
        if abs(today_pl) < 0.0001 and abs(calculated_today_pl) > 0.0001:
            today_pl = calculated_today_pl
        rows.append(
            {
                "code": code,
                "name": row.get("stock_name", ""),
                "qty": qty,
                "can_sell_qty": safe_float(row.get("can_sell_qty")),
                "average_cost": average_cost,
                "nominal_price": nominal_price,
                "current_price": current_price,
                "prev_close": prev_close,
                "market_val": market_val,
                "unrealized_pl": unrealized_pl,
                "pl_ratio_avg_cost": pl_ratio,
                "realized_pl": safe_float(row.get("realized_pl")),
                "today_pl_val": today_pl,
                "today_pl_ratio": today_ratio,
                "position_percent": market_val / total_assets * 100 if total_assets > 0 else 0.0,
                "acc_id": row.get("acc_id", ""),
            }
        )
    return rows


def fetch_position_snapshots(pos_data: Any) -> Dict[str, Dict[str, Any]]:
    if pos_data is None or len(pos_data) == 0:
        return {}
    codes = [str(row.get("code", "")) for _, row in pos_data.iterrows() if row.get("code", "")]
    if not codes:
        return {}
    env = skill_env()
    old_env = os.environ.copy()
    try:
        os.environ.clear()
        os.environ.update(env)
        from futu import OpenQuoteContext

        ctx = OpenQuoteContext(
            host=os.getenv("FUTU_OPEND_HOST", "127.0.0.1"),
            port=int(os.getenv("FUTU_OPEND_PORT", "11111")),
        )
        try:
            ret, data = ctx.get_market_snapshot(codes)
            if ret != 0 or data is None or len(data) == 0:
                return {}
            snapshots = {}
            for _, row in data.iterrows():
                code = str(row.get("code", ""))
                if code:
                    snapshots[code] = {
                        "last_price": safe_float(row.get("last_price")),
                        "prev_close_price": safe_float(row.get("prev_close_price")),
                        "update_time": row.get("update_time", ""),
                    }
            return snapshots
        finally:
            ctx.close()
    except Exception:
        return {}
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def parse_orders(data: Any) -> List[Dict[str, Any]]:
    if data is None or len(data) == 0:
        return []
    orders = []
    for _, row in data.iterrows():
        orders.append(
            {
                "order_id": str(row.get("order_id", row.get("orderID", "N/A"))),
                "code": row.get("code", "N/A"),
                "side": format_enum(row.get("trd_side", row.get("side", "N/A"))),
                "status": format_enum(row.get("order_status", row.get("status", "N/A"))),
                "qty": safe_float(row.get("qty", row.get("quantity", 0))),
                "price": safe_float(row.get("price")),
                "dealt_qty": safe_float(row.get("dealt_qty")),
                "dealt_avg_price": safe_float(row.get("dealt_avg_price")),
            }
        )
    return orders


def load_trade_signal() -> Dict[str, Any]:
    signal = read_json(OUTPUT_DIR / "trade_signal.json")
    if not signal:
        raise FileNotFoundError("Missing output/trade_signal.json. Run etf_rotation_backtest.py first.")
    return signal


def load_account_snapshot() -> Dict[str, Any]:
    snapshot = read_json(OUTPUT_DIR / "futu_sim_account.json")
    if not snapshot or not snapshot.get("selected_account"):
        raise FileNotFoundError("Missing usable output/futu_sim_account.json. Run futu_sim_preflight.py first.")
    if not snapshot.get("ok"):
        raise RuntimeError(snapshot.get("message") or "Futu simulation preflight is not OK.")
    return snapshot


def account_from_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    selected = snapshot.get("selected_account") or {}
    if not selected.get("acc_id"):
        raise RuntimeError("No selected Futu simulation account in preflight snapshot.")
    return selected


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, "", "N/A"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, "", "N/A"):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
