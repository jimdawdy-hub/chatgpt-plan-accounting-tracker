import os

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from tracker import (
    APP_TITLE,
    CHATGPT_PRICING_URL,
    CODEX_RATE_CARD,
    API_PRICING,
    PLAN_DETAILS,
    RATE_CARD_URL,
    days_between,
    estimate_api_cost_usd,
    get_setting,
    get_db,
    import_reports,
    init_db,
    plan_monthly_cost,
    rows,
    set_setting,
    summary,
)


app = Flask(__name__)
CORS(app, origins=["http://localhost:5050", "http://127.0.0.1:5050"])


@app.before_request
def ensure_db():
    conn = get_db()
    init_db(conn)
    conn.close()


@app.get("/")
def index():
    return render_template("index.html", title=APP_TITLE)


@app.post("/api/sync")
def sync():
    return jsonify(import_reports(force=True))


@app.get("/api/summary")
def api_summary():
    return jsonify(summary())


@app.post("/api/plan")
def api_set_plan():
    body = request.get_json(force=True)
    plan = body.get("plan")
    if plan not in PLAN_DETAILS:
        return jsonify({"error": "unknown plan", "options": PLAN_DETAILS}), 400
    set_setting("active_plan", plan)
    return jsonify({"active_plan": plan, "summary": summary()})


@app.post("/api/settings")
def api_set_settings():
    body = request.get_json(force=True)
    if "plan_start_date" in body:
        set_setting("plan_start_date", body.get("plan_start_date") or "")
    if "seat_count" in body:
        try:
            seats = max(int(body.get("seat_count") or 1), 1)
        except ValueError:
            return jsonify({"error": "seat_count must be a number"}), 400
        set_setting("seat_count", str(seats))
    return jsonify(summary())


@app.get("/api/daily")
def api_daily():
    return jsonify(rows("SELECT * FROM daily_usage ORDER BY date"))


@app.get("/api/models")
def api_models():
    conn = get_db()
    init_db(conn)
    plan_start_date = get_setting(conn, "plan_start_date")
    if not plan_start_date:
        first = conn.execute("SELECT MIN(date) AS start FROM daily_usage").fetchone()
        plan_start_date = first["start"] if first else None
    active_plan = get_setting(conn, "active_plan", "Business")
    seats = int(get_setting(conn, "seat_count", "2") or 2)
    last = conn.execute("SELECT MAX(date) AS end FROM daily_usage WHERE date >= ?", (plan_start_date,)).fetchone() if plan_start_date else None
    days_elapsed = max(days_between(plan_start_date, last["end"]) + 1, 1) if plan_start_date and last and last["end"] else 1
    selected_plan_cost = plan_monthly_cost(PLAN_DETAILS.get(active_plan, PLAN_DETAILS["Business"]), seats) or 0
    model_rows = [
        dict(row)
        for row in conn.execute(
        """
        SELECT
            model,
            SUM(credits) AS credits,
            SUM(estimated_credits) AS estimated_credits,
            SUM(uncached_text_input_tokens) AS uncached,
            SUM(cached_text_input_tokens) AS cached,
            SUM(text_output_tokens) AS output,
            SUM(text_total_tokens) AS total_tokens
        FROM model_usage
        WHERE date >= ?
        GROUP BY model
        ORDER BY credits DESC
        """,
            (plan_start_date,),
        ).fetchall()
    ]
    conn.close()

    for row in model_rows:
        costs = estimate_api_cost_usd(row["model"], row["uncached"] or 0, row["cached"] or 0, row["output"] or 0)
        row["api_input_cost_usd"] = costs["input"]
        row["api_cached_cost_usd"] = costs["cached"]
        row["api_output_cost_usd"] = costs["output"]
        row["api_total_cost_usd"] = costs["total"]
        row["api_projected_30d_cost_usd"] = (costs["total"] / days_elapsed * 30) if costs["total"] is not None else None
        row["api_rates"] = API_PRICING.get((row["model"] or "").lower())
    total_projected_api = sum((row["api_projected_30d_cost_usd"] or 0) for row in model_rows)
    for row in model_rows:
        share = ((row["api_projected_30d_cost_usd"] or 0) / total_projected_api) if total_projected_api else 0
        allocated_plan_cost = selected_plan_cost * share
        row["selected_plan_cost_share_usd"] = allocated_plan_cost
        row["api_projected_30d_savings_vs_plan_usd"] = (
            row["api_projected_30d_cost_usd"] - allocated_plan_cost
            if row["api_projected_30d_cost_usd"] is not None
            else None
        )
        row["projection_days_elapsed"] = days_elapsed
        row["selected_plan_cost_usd"] = selected_plan_cost
    return jsonify(model_rows)


@app.get("/api/clients")
def api_clients():
    return jsonify(
        rows(
            """
            SELECT
                client_id,
                SUM(users) AS users,
                SUM(threads) AS threads,
                SUM(turns) AS turns,
                SUM(credits) AS credits
            FROM client_usage
            GROUP BY client_id
            ORDER BY turns DESC
            """
        )
    )


@app.get("/api/credit-events")
def api_credit_events():
    return jsonify(rows("SELECT * FROM credit_events ORDER BY date, usage_type"))


@app.get("/api/reference")
def api_reference():
    return jsonify(
        {
            "plans": PLAN_DETAILS,
            "codex_rate_card": CODEX_RATE_CARD,
            "api_pricing": API_PRICING,
            "rate_card_url": RATE_CARD_URL,
            "chatgpt_pricing_url": CHATGPT_PRICING_URL,
        }
    )


if __name__ == "__main__":
    conn = get_db()
    init_db(conn)
    conn.close()
    import_reports()
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="127.0.0.1", port=5050, debug=debug)
