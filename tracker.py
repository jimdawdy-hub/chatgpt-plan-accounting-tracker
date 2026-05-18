import csv
import json
from json import JSONDecodeError
import sqlite3
from pathlib import Path


APP_TITLE = "ChatGPT Plan Accounting Tracker"
DB_PATH = Path(__file__).parent / "usage.db"

RATE_CARD_URL = "https://help.openai.com/en/articles/20001106-codex-rate-card#codex-rate-card-token-based-pricing"
CHATGPT_PRICING_URL = "https://chatgpt.com/pricing/"

# Credits per 1M tokens from the OpenAI Codex rate card, fetched May 17, 2026.
CODEX_RATE_CARD = {
    "gpt-5.5": {"input": 125.0, "cached_input": 12.5, "output": 750.0},
    "gpt-5.4": {"input": 62.5, "cached_input": 6.25, "output": 375.0},
    "gpt-5.4-mini": {"input": 18.75, "cached_input": 1.875, "output": 113.0},
    "gpt-5.3-codex": {"input": 43.75, "cached_input": 4.375, "output": 350.0},
    "gpt-5.2": {"input": 43.75, "cached_input": 4.375, "output": 350.0},
    "gpt-image-2.0-image": {"input": 200.0, "cached_input": 50.0, "output": 750.0},
    "gpt-image-2.0-text": {"input": 125.0, "cached_input": 31.25, "output": 250.0},
}

# Standard API pricing per 1M text tokens from OpenAI API model docs, fetched May 17, 2026.
API_PRICING = {
    "gpt-5.5": {"input": 5.00, "cached_input": 0.50, "output": 30.00},
    "gpt-5.4": {"input": 2.50, "cached_input": 0.25, "output": 15.00},
    "gpt-5.4-mini": {"input": 0.75, "cached_input": 0.075, "output": 4.50},
}

PLAN_DETAILS = {
    "Free": {
        "label": "ChatGPT Free",
        "monthly_usd": 0,
        "billing_unit": "month",
        "notes": "Limited Codex access.",
        "codex_access": "Temporary limited access",
        "limit_policy": "Limited; public docs do not publish a numeric Codex credit cap.",
        "credit_policy": "Free users are prompted to upgrade for Codex rather than adding Codex credits.",
        "same_workload": "Unlikely",
    },
    "Go": {
        "label": "ChatGPT Go",
        "monthly_usd": 8,
        "billing_unit": "month",
        "notes": "Expanded consumer access; availability and local price can vary by region.",
        "codex_access": "Temporary limited access",
        "limit_policy": "Limited; public docs do not publish a numeric Codex credit cap.",
        "credit_policy": "Go users are prompted to upgrade for Codex rather than adding Codex credits.",
        "same_workload": "Unlikely",
    },
    "Plus": {
        "label": "ChatGPT Plus",
        "monthly_usd": 20,
        "billing_unit": "month",
        "notes": "Personal subscription with expanded Codex usage.",
        "codex_access": "Included",
        "limit_policy": "Plan included usage first; Codex credits can extend usage after limits. Numeric cap is not public.",
        "credit_policy": "Eligible Plus users can buy Codex credits and may use auto top-up.",
        "same_workload": "Unknown",
    },
    "Pro": {
        "label": "ChatGPT Pro",
        "monthly_usd": 200,
        "billing_unit": "month",
        "notes": "Heavy personal tier with Pro reasoning and maximum Codex tasks.",
        "codex_access": "Included, expanded",
        "limit_policy": "Higher included usage than Plus; numeric cap is not public.",
        "credit_policy": "Eligible Pro users can buy Codex credits and may use auto top-up.",
        "same_workload": "Possible but not guaranteed",
    },
    "Business Codex": {
        "label": "Business Codex",
        "monthly_usd": 0,
        "billing_unit": "workspace",
        "notes": "No fixed seat fee; pay as you go based on usage.",
        "codex_access": "Included as usage-priced product",
        "limit_policy": "No fixed seat fee; usage is priced from the Codex rate card.",
        "credit_policy": "Pay as you go based on usage.",
        "same_workload": "Likely, subject to workspace controls",
    },
    "Business": {
        "label": "Business ChatGPT & Codex",
        "monthly_usd": 25,
        "annual_monthly_usd": 25,
        "billing_unit": "user/month",
        "minimum_users": 2,
        "notes": "Workspace subscription; $25/seat/month with a 2-seat minimum.",
        "codex_access": "Included",
        "limit_policy": "Workspace plan with Codex support; exact usable volume depends on usage credits, settings, and controls.",
        "credit_policy": "Workspace/admin credit and spend controls may apply.",
        "same_workload": "Selected plan",
    },
    "Enterprise": {
        "label": "ChatGPT Enterprise",
        "monthly_usd": None,
        "billing_unit": "custom",
        "notes": "Custom pricing; contract terms may override defaults.",
        "codex_access": "Included when enabled",
        "limit_policy": "Custom contract/workspace controls; some Enterprise plans may have legacy rate-card treatment.",
        "credit_policy": "Contract-specific.",
        "same_workload": "Unknown; depends on contract",
    },
}


def get_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS daily_usage (
            date TEXT PRIMARY KEY,
            users INTEGER DEFAULT 0,
            threads INTEGER DEFAULT 0,
            turns INTEGER DEFAULT 0,
            credits REAL DEFAULT 0,
            on_demand_credits REAL DEFAULT 0,
            uncached_text_input_tokens INTEGER DEFAULT 0,
            cached_text_input_tokens INTEGER DEFAULT 0,
            text_output_tokens INTEGER DEFAULT 0,
            text_total_tokens INTEGER DEFAULT 0,
            source TEXT
        );

        CREATE TABLE IF NOT EXISTS model_usage (
            date TEXT,
            model TEXT,
            credits REAL DEFAULT 0,
            estimated_credits REAL DEFAULT 0,
            uncached_text_input_tokens INTEGER DEFAULT 0,
            cached_text_input_tokens INTEGER DEFAULT 0,
            text_output_tokens INTEGER DEFAULT 0,
            text_total_tokens INTEGER DEFAULT 0,
            PRIMARY KEY (date, model)
        );

        CREATE TABLE IF NOT EXISTS client_usage (
            date TEXT,
            client_id TEXT,
            users INTEGER DEFAULT 0,
            threads INTEGER DEFAULT 0,
            turns INTEGER DEFAULT 0,
            credits REAL DEFAULT 0,
            PRIMARY KEY (date, client_id)
        );

        CREATE TABLE IF NOT EXISTS credit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            account_id TEXT,
            account_user_id TEXT,
            email TEXT,
            name TEXT,
            public_id TEXT,
            seat_type TEXT,
            usage_type TEXT,
            usage_credits REAL DEFAULT 0,
            usage_quantity REAL DEFAULT 0,
            usage_units TEXT,
            UNIQUE(date, account_user_id, usage_type, usage_credits, usage_quantity)
        );

        CREATE TABLE IF NOT EXISTS imported_files (
            path TEXT PRIMARY KEY,
            mtime REAL,
            kind TEXT,
            imported_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    conn.commit()


def get_setting(conn, key, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_db()
    init_db(conn)
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def _num(value):
    if value in (None, ""):
        return 0
    return float(value)


def _int(value):
    return int(_num(value))


def estimate_model_credits(model, uncached, cached, output):
    rates = CODEX_RATE_CARD.get((model or "").lower())
    if not rates:
        return 0
    return (
        (uncached / 1_000_000) * rates["input"]
        + (cached / 1_000_000) * rates["cached_input"]
        + (output / 1_000_000) * rates["output"]
    )


def estimate_api_cost_usd(model, uncached, cached, output):
    rates = API_PRICING.get((model or "").lower())
    if not rates:
        return {"input": None, "cached": None, "output": None, "total": None}
    input_cost = (uncached / 1_000_000) * rates["input"]
    cached_cost = (cached / 1_000_000) * rates["cached_input"]
    output_cost = (output / 1_000_000) * rates["output"]
    return {
        "input": input_cost,
        "cached": cached_cost,
        "output": output_cost,
        "total": input_cost + cached_cost + output_cost,
    }


def discover_reports():
    roots = [Path(__file__).parent / "data", Path.home() / "Downloads"]
    patterns = [
        "*.csv",
        "codex-daily-sessions-messages-counts-*.json",
        "codex-daily-workspace-usage-counts-*.json",
    ]
    found = []
    for root in roots:
        if not root.exists():
            continue
        for pattern in patterns:
            found.extend(root.glob(pattern))
    return sorted({p.resolve() for p in found})


def classify_report(path):
    name = path.name.lower()
    if name.endswith(".csv") and ("credit usage report" in name or looks_like_credit_csv(path)):
        return "credit_csv"
    if "workspace-usage" in name:
        return "workspace_json"
    if "sessions-messages" in name:
        return "sessions_json"
    if name.endswith(".json"):
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, UnicodeDecodeError, JSONDecodeError):
            return None
        rows = data.get("data") or []
        if rows and "totals" in rows[0]:
            return "workspace_json"
        if rows and "n_new_sessions_total" in rows[0]:
            return "sessions_json"
    return None


def looks_like_credit_csv(path):
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader, [])
    except (OSError, UnicodeDecodeError):
        return False
    required = {"date_partition", "usage_type", "usage_credits", "usage_quantity"}
    return required.issubset(set(header))


def import_reports(paths=None, force=False):
    conn = get_db()
    init_db(conn)
    stats = {"files": 0, "daily_rows": 0, "model_rows": 0, "client_rows": 0, "credit_events": 0, "skipped": 0}
    for raw_path in paths or discover_reports():
        path = Path(raw_path).expanduser().resolve()
        if not path.exists():
            continue
        kind = classify_report(path)
        if not kind:
            continue
        mtime = path.stat().st_mtime
        previous = conn.execute("SELECT mtime FROM imported_files WHERE path = ?", (str(path),)).fetchone()
        if previous and abs(previous["mtime"] - mtime) < 0.01 and not force:
            stats["skipped"] += 1
            continue
        try:
            if kind == "credit_csv":
                imported = import_credit_csv(conn, path)
                stats["credit_events"] += imported
            else:
                imported = import_codex_json(conn, path, kind)
                stats["daily_rows"] += imported["daily_rows"]
                stats["model_rows"] += imported["model_rows"]
                stats["client_rows"] += imported["client_rows"]
        except (OSError, UnicodeDecodeError, JSONDecodeError, csv.Error):
            stats.setdefault("failed", 0)
            stats["failed"] += 1
            continue
        conn.execute(
            "INSERT OR REPLACE INTO imported_files (path, mtime, kind, imported_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (str(path), mtime, kind),
        )
        conn.commit()
        stats["files"] += 1
    conn.close()
    return stats


def import_credit_csv(conn, path):
    count = 0
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            before = conn.total_changes
            conn.execute(
                """
                INSERT OR IGNORE INTO credit_events
                    (date, account_id, account_user_id, email, name, public_id, seat_type,
                     usage_type, usage_credits, usage_quantity, usage_units)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("date_partition"),
                    row.get("account_id"),
                    row.get("account_user_id"),
                    row.get("email"),
                    row.get("name"),
                    row.get("public_id"),
                    row.get("seat_type"),
                    row.get("usage_type"),
                    _num(row.get("usage_credits")),
                    _num(row.get("usage_quantity")),
                    row.get("usage_units"),
                ),
            )
            count += conn.total_changes - before
    conn.commit()
    return count


def import_codex_json(conn, path, kind):
    with path.open(encoding="utf-8") as f:
        payload = json.load(f)
    stats = {"daily_rows": 0, "model_rows": 0, "client_rows": 0}
    for row in payload.get("data", []):
        if kind == "workspace_json":
            totals = row.get("totals", {})
            daily = {
                "date": row.get("date"),
                "users": _int(totals.get("users")),
                "threads": _int(totals.get("threads")),
                "turns": _int(totals.get("turns")),
                "credits": _num(totals.get("credits")),
                "on_demand_credits": _num(totals.get("on_demand_credits")),
                "uncached": _int(totals.get("uncached_text_input_tokens")),
                "cached": _int(totals.get("cached_text_input_tokens")),
                "output": _int(totals.get("text_output_tokens")),
                "total": _int(totals.get("text_total_tokens")),
            }
            clients = row.get("clients", [])
        else:
            daily = {
                "date": row.get("date"),
                "users": _int(row.get("n_users_used_codex")),
                "threads": _int(row.get("n_new_sessions_total")),
                "turns": _int(row.get("n_user_messages_total")),
                "credits": _num(row.get("credit_total")),
                "on_demand_credits": _num(row.get("on_demand_credits")),
                "uncached": _int(row.get("uncached_text_input_tokens")),
                "cached": _int(row.get("cached_text_input_tokens")),
                "output": _int(row.get("text_output_tokens")),
                "total": _int(row.get("text_total_tokens")),
            }
            clients = _clients_from_session_row(row)

        conn.execute(
            """
            INSERT OR REPLACE INTO daily_usage
                (date, users, threads, turns, credits, on_demand_credits,
                 uncached_text_input_tokens, cached_text_input_tokens, text_output_tokens,
                 text_total_tokens, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                daily["date"],
                daily["users"],
                daily["threads"],
                daily["turns"],
                daily["credits"],
                daily["on_demand_credits"],
                daily["uncached"],
                daily["cached"],
                daily["output"],
                daily["total"],
                kind,
            ),
        )
        stats["daily_rows"] += 1

        for model in row.get("models", []):
            model_name = model.get("model") or "unknown"
            uncached = _int(model.get("uncached_text_input_tokens"))
            cached = _int(model.get("cached_text_input_tokens"))
            output = _int(model.get("text_output_tokens"))
            conn.execute(
                """
                INSERT OR REPLACE INTO model_usage
                    (date, model, credits, estimated_credits, uncached_text_input_tokens,
                     cached_text_input_tokens, text_output_tokens, text_total_tokens)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("date"),
                    model_name,
                    _num(model.get("credits")),
                    estimate_model_credits(model_name, uncached, cached, output),
                    uncached,
                    cached,
                    output,
                    _int(model.get("text_total_tokens")),
                ),
            )
            stats["model_rows"] += 1

        for client in clients:
            conn.execute(
                """
                INSERT OR REPLACE INTO client_usage
                    (date, client_id, users, threads, turns, credits)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("date"),
                    client.get("client_id"),
                    _int(client.get("users")),
                    _int(client.get("threads")),
                    _int(client.get("turns")),
                    _num(client.get("credits")),
                ),
            )
            stats["client_rows"] += 1
    conn.commit()
    return stats


def _clients_from_session_row(row):
    clients = []
    fields = {
        "CODEX_CLI": ("n_new_sessions_cli", "n_user_messages_cli", "credit_cli"),
        "CODEX_VSCODE": ("n_new_sessions_vscode", "n_user_messages_vscode", "credit_vscode"),
        "CODEX_EXEC": ("n_new_sessions_exec", "n_user_messages_exec", "credit_exec"),
        "CODEX_SDK_TS": ("n_new_sessions_sdk_ts", "n_user_messages_sdk_ts", "credit_sdk_ts"),
        "CODEX_DESKTOP": ("n_new_sessions_desktop", "n_user_messages_desktop", "credit_desktop"),
        "CODEX_UNKNOWN_DEFAULT": ("n_new_sessions_other", "n_user_messages_other", None),
    }
    for client_id, (threads_key, turns_key, credits_key) in fields.items():
        threads = _int(row.get(threads_key))
        turns = _int(row.get(turns_key))
        credits = _num(row.get(credits_key)) if credits_key else 0
        if threads or turns or credits:
            clients.append({"client_id": client_id, "users": row.get("n_users_used_codex", 1), "threads": threads, "turns": turns, "credits": credits})
    return clients


def summary():
    conn = get_db()
    init_db(conn)
    totals = conn.execute(
        """
        SELECT
            COALESCE(SUM(threads), 0) AS threads,
            COALESCE(SUM(turns), 0) AS turns,
            COALESCE(SUM(credits), 0) AS codex_credits,
            COALESCE(SUM(on_demand_credits), 0) AS on_demand_credits,
            COALESCE(SUM(uncached_text_input_tokens), 0) AS uncached,
            COALESCE(SUM(cached_text_input_tokens), 0) AS cached,
            COALESCE(SUM(text_output_tokens), 0) AS output,
            COALESCE(SUM(text_total_tokens), 0) AS total_tokens
        FROM daily_usage
        """
    ).fetchone()
    billed = conn.execute(
        """
        SELECT
            COALESCE(SUM(usage_credits), 0) AS billable_credits,
            COALESCE(SUM(usage_quantity), 0) AS billable_quantity,
            COUNT(*) AS events
        FROM credit_events
        """
    ).fetchone()
    date_range = conn.execute("SELECT MIN(date) AS start, MAX(date) AS end FROM daily_usage").fetchone()
    active_plan = get_setting(conn, "active_plan", "Business")
    plan_start_date = get_setting(conn, "plan_start_date", (date_range["start"] if date_range and date_range["start"] else None))
    seats = int(get_setting(conn, "seat_count", "2") or 2)
    projection = projection_summary(conn, active_plan, plan_start_date, seats)
    conn.close()
    total = dict(totals)
    bill = dict(billed)
    token_total = total.get("total_tokens") or 0
    cache_ratio = (total.get("cached") or 0) / token_total if token_total else 0
    visible_gap = (total.get("codex_credits") or 0) - (bill.get("billable_credits") or 0)
    credit_usd_rate = get_credit_usd_rate()
    plan_costs = plan_cost_comparison(bill.get("billable_credits") or 0, credit_usd_rate, seats)
    plan_value = plan_value_summary(active_plan, total.get("codex_credits") or 0, bill.get("billable_credits") or 0, credit_usd_rate, seats)
    return {
        "title": APP_TITLE,
        "date_range": dict(date_range),
        "totals": total,
        "billing": bill,
        "cache_ratio": cache_ratio,
        "visible_gap": visible_gap,
        "active_plan": active_plan,
        "plan_start_date": plan_start_date,
        "seat_count": seats,
        "credit_usd_rate": credit_usd_rate,
        "plan_value": plan_value,
        "projection": projection,
        "plan_costs": plan_costs,
        "plans": PLAN_DETAILS,
        "rate_card_url": RATE_CARD_URL,
        "chatgpt_pricing_url": CHATGPT_PRICING_URL,
    }


def get_credit_usd_rate():
    return 20 / 500


def plan_monthly_cost(plan, seats=1, use_annual=False):
    base = plan.get("annual_monthly_usd") if use_annual and plan.get("annual_monthly_usd") is not None else plan.get("monthly_usd")
    if base is None:
        return None
    if plan.get("billing_unit") == "user/month":
        minimum = plan.get("minimum_users") or 1
        return base * max(seats, minimum)
    return base


def plan_value_summary(active_plan, internal_credits, visible_billable_credits, credit_usd_rate=None, seats=1):
    credit_usd_rate = credit_usd_rate if credit_usd_rate is not None else get_credit_usd_rate()
    plan = PLAN_DETAILS.get(active_plan) or PLAN_DETAILS["Business"]
    base_cost = plan_monthly_cost(plan, seats)
    annual_base = plan_monthly_cost(plan, seats, use_annual=True) if plan.get("annual_monthly_usd") is not None else None
    usage_value = internal_credits * credit_usd_rate
    visible_extra_cost = visible_billable_credits * credit_usd_rate

    if base_cost is None:
        net_value = None
        annual_net_value = None
    else:
        net_value = usage_value - base_cost - visible_extra_cost
        annual_net_value = usage_value - annual_base - visible_extra_cost if annual_base is not None else None

    return {
        "plan_key": active_plan,
        "label": plan["label"],
        "base_monthly_usd": base_cost,
        "annual_monthly_usd": annual_base,
        "seat_count": seats,
        "usage_value_usd": usage_value,
        "visible_extra_cost_usd": visible_extra_cost,
        "net_value_usd": net_value,
        "annual_net_value_usd": annual_net_value,
        "credit_usd_rate": credit_usd_rate,
        "formula": "internal Codex credits value - plan base cost - visible billable credits value",
    }


def plan_cost_comparison(visible_billable_credits, credit_usd_rate=None, seats=1):
    credit_usd_rate = credit_usd_rate if credit_usd_rate is not None else get_credit_usd_rate()
    visible_billable_usd = visible_billable_credits * credit_usd_rate
    comparisons = {}
    for key, plan in PLAN_DETAILS.items():
        base = plan_monthly_cost(plan, seats)
        annual_base = plan_monthly_cost(plan, seats, use_annual=True) if plan.get("annual_monthly_usd") is not None else None
        if base is None:
            monthly_total = None
            annual_total = None
        else:
            monthly_total = base + visible_billable_usd
            annual_total = (annual_base + visible_billable_usd) if annual_base is not None else None
        comparisons[key] = {
            "label": plan["label"],
            "base_monthly_usd": base,
            "annual_monthly_usd": annual_base,
            "billing_unit": plan.get("billing_unit"),
            "minimum_users": plan.get("minimum_users"),
            "seat_count": seats,
            "visible_billable_credits": visible_billable_credits,
            "visible_billable_usd": visible_billable_usd,
            "monthly_total_with_visible_credits": monthly_total,
            "annual_monthly_total_with_visible_credits": annual_total,
            "notes": plan.get("notes"),
        }
    return comparisons


def projection_summary(conn, active_plan, start_date, seats=1):
    if not start_date:
        return {}
    credit_rate = get_credit_usd_rate()
    row = conn.execute(
        """
        SELECT
            COALESCE(SUM(credits), 0) AS credits,
            COALESCE(SUM(on_demand_credits), 0) AS on_demand_credits,
            COALESCE(SUM(threads), 0) AS threads,
            COALESCE(SUM(turns), 0) AS turns,
            COUNT(*) AS days_with_data,
            MIN(date) AS first_date,
            MAX(date) AS last_date
        FROM daily_usage
        WHERE date >= ?
        """,
        (start_date,),
    ).fetchone()
    if not row:
        return {}
    data = dict(row)
    days_elapsed = max(days_between(start_date, data.get("last_date")) + 1, 1) if data.get("last_date") else 1
    daily_credit_rate = (data["credits"] or 0) / days_elapsed
    projected_credits = daily_credit_rate * 30
    projected_usage_value = projected_credits * credit_rate

    plan = PLAN_DETAILS.get(active_plan) or PLAN_DETAILS["Business"]
    selected_plan_cost = plan_monthly_cost(plan, seats)
    selected_plan_savings = None if selected_plan_cost is None else projected_usage_value - selected_plan_cost

    comparisons = {}
    for key, candidate in PLAN_DETAILS.items():
        candidate_cost = plan_monthly_cost(candidate, seats)
        is_selected = key == active_plan
        comparisons[key] = {
            "label": candidate["label"],
            "monthly_cost_usd": candidate_cost,
            "projected_savings_usd": (None if candidate_cost is None else projected_usage_value - candidate_cost) if is_selected else None,
            "comparable": is_selected,
            "comparison_note": "Selected plan projection" if is_selected else "Not projected: other plans may not allow this same Codex workload or quota.",
            "notes": candidate.get("notes"),
            "codex_access": candidate.get("codex_access"),
            "limit_policy": candidate.get("limit_policy"),
            "credit_policy": candidate.get("credit_policy"),
            "same_workload": candidate.get("same_workload"),
        }

    return {
        "start_date": start_date,
        "first_data_date": data.get("first_date"),
        "last_data_date": data.get("last_date"),
        "days_elapsed": days_elapsed,
        "days_with_data": data.get("days_with_data"),
        "credits_to_date": data.get("credits"),
        "daily_credit_rate": daily_credit_rate,
        "projected_30d_credits": projected_credits,
        "projected_30d_usage_value_usd": projected_usage_value,
        "selected_plan": active_plan,
        "selected_plan_cost_usd": selected_plan_cost,
        "selected_plan_projected_savings_usd": selected_plan_savings,
        "comparisons": comparisons,
    }


def days_between(start, end):
    from datetime import date

    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except (TypeError, ValueError):
        return 0
    return (end_date - start_date).days


def rows(query, params=()):
    conn = get_db()
    conn.row_factory = sqlite3.Row
    result = [dict(row) for row in conn.execute(query, params).fetchall()]
    conn.close()
    return result
