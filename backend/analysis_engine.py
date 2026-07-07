import os
import json
import logging

import pandas as pd
import numpy as np
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("ai_business_doctor")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


def to_native(obj):
    """Recursively convert numpy/pandas types to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: to_native(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_native(v) for v in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj


def load_data():
    sales = pd.read_csv("sales_data.csv")
    inventory = pd.read_csv("inventory_data.csv")
    sales["date"] = pd.to_datetime(sales["date"])
    return sales, inventory


def analyze_profit_drop(sales: pd.DataFrame):
    """Compares last 15 days vs previous 15 days to find what's driving any profit change."""
    max_date = sales["date"].max()
    recent_start = max_date - pd.Timedelta(days=14)
    prev_start = max_date - pd.Timedelta(days=29)
    prev_end = max_date - pd.Timedelta(days=15)

    recent = sales[sales["date"] >= recent_start]
    previous = sales[(sales["date"] >= prev_start) & (sales["date"] <= prev_end)]

    recent_by_product = recent.groupby("product")["profit"].sum()
    prev_by_product = previous.groupby("product")["profit"].sum()

    comparison = pd.DataFrame({
        "recent_profit": recent_by_product,
        "previous_profit": prev_by_product
    }).fillna(0)

    comparison["change"] = comparison["recent_profit"] - comparison["previous_profit"]
    comparison["pct_change"] = np.where(
        comparison["previous_profit"] > 0,
        (comparison["change"] / comparison["previous_profit"]) * 100,
        0
    )

    total_change = comparison["change"].sum()
    top_drags = comparison.sort_values("change").head(3)

    drivers = []
    for product, row in top_drags.iterrows():
        if row["change"] < 0:
            drivers.append({
                "product": product,
                "profit_change": round(float(row["change"]), 2),
                "pct_change": round(float(row["pct_change"]), 1),
                "reasoning": f"{product} profit dropped by Rs {abs(round(row['change']))} ({abs(round(row['pct_change'],1))}% decline) in the last 15 days compared to the prior 15 days."
            })

    return {
        "total_profit_change": round(float(total_change), 2),
        "summary": f"Overall profit {'declined' if total_change < 0 else 'grew'} by Rs {abs(round(total_change))} over the last 15 days.",
        "top_drivers": drivers
    }


def recommend_stop_selling(sales: pd.DataFrame, inventory: pd.DataFrame):
    """Flags consistently low-selling, low-margin-contribution products."""
    product_stats = sales.groupby("product").agg(
        total_units=("units_sold", "sum"),
        total_profit=("profit", "sum"),
        avg_daily_units=("units_sold", "mean")
    ).reset_index()

    threshold_units = product_stats["avg_daily_units"].quantile(0.25)
    threshold_profit = product_stats["total_profit"].quantile(0.4)

    candidates = product_stats[
        (product_stats["avg_daily_units"] <= threshold_units) &
        (product_stats["total_profit"] <= threshold_profit)
    ].sort_values("total_profit")

    recommendations = []
    for _, row in candidates.iterrows():
        stock_row = inventory[inventory["product"] == row["product"]]
        current_stock = int(stock_row["current_stock"].values[0]) if not stock_row.empty else 0
        stock_capital = current_stock * float(stock_row["unit_cost"].values[0]) if not stock_row.empty else 0
        recommendations.append({
            "product": row["product"],
            "avg_daily_units": round(float(row["avg_daily_units"]), 1),
            "total_profit_90days": round(float(row["total_profit"]), 2),
            "current_stock": current_stock,
            "reasoning": f"Averages only {round(row['avg_daily_units'],1)} units/day over 90 days, contributing just Rs {round(row['total_profit'])} total profit while tying up Rs {stock_capital:.0f} in stock capital."
        })

    return recommendations[:3]


def recommend_reorder(sales: pd.DataFrame, inventory: pd.DataFrame):
    """Flags products where recent demand trend + low stock signals a reorder need."""
    max_date = sales["date"].max()
    recent_start = max_date - pd.Timedelta(days=14)
    recent = sales[sales["date"] >= recent_start]

    recent_demand = recent.groupby("product")["units_sold"].sum().reset_index()
    recent_demand["daily_avg"] = recent_demand["units_sold"] / 15
    recent_demand["projected_7day_need"] = (recent_demand["daily_avg"] * 7).round().astype(int)

    merged = recent_demand.merge(inventory[["product", "current_stock"]], on="product", how="left")
    merged["days_of_stock_left"] = np.where(
        merged["daily_avg"] > 0,
        merged["current_stock"] / merged["daily_avg"],
        999
    )

    urgent = merged[merged["days_of_stock_left"] <= 7].sort_values("days_of_stock_left")

    recommendations = []
    for _, row in urgent.iterrows():
        recommendations.append({
            "product": row["product"],
            "current_stock": int(row["current_stock"]),
            "daily_avg_demand": round(float(row["daily_avg"]), 1),
            "days_of_stock_left": round(float(row["days_of_stock_left"]), 1),
            "recommended_reorder_qty": int(row["projected_7day_need"]),
            "reasoning": f"Selling ~{round(row['daily_avg'],1)} units/day, only {round(row['days_of_stock_left'],1)} days of stock left. Reorder at least {row['projected_7day_need']} units to cover next 7 days."
        })

    return recommendations


def get_profit_trend(sales: pd.DataFrame, days: int = 30):
    """Returns daily total profit for the last N days — chart-ready time series."""
    max_date = sales["date"].max()
    start_date = max_date - pd.Timedelta(days=days - 1)
    recent = sales[sales["date"] >= start_date]

    daily = recent.groupby("date")["profit"].sum().reset_index()
    daily = daily.sort_values("date")

    return [
        {"date": row["date"].strftime("%b %d"), "profit": round(float(row["profit"]), 2)}
        for _, row in daily.iterrows()
    ]


def get_raw_summary_table(sales: pd.DataFrame, inventory: pd.DataFrame):
    """
    Returns the 'boring spreadsheet' view — raw aggregated numbers with
    zero interpretation. Used to visually contrast against the AI's
    diagnosis, making the value of the recommendation layer obvious.
    """
    product_stats = sales.groupby("product").agg(
        total_units=("units_sold", "sum"),
        total_revenue=("revenue", "sum"),
        total_profit=("profit", "sum"),
    ).reset_index()

    merged = product_stats.merge(
        inventory[["product", "current_stock"]], on="product", how="left"
    )

    return [
        {
            "product": row["product"],
            "total_units": int(row["total_units"]),
            "total_revenue": round(float(row["total_revenue"]), 2),
            "total_profit": round(float(row["total_profit"]), 2),
            "current_stock": int(row["current_stock"]) if pd.notna(row["current_stock"]) else 0,
        }
        for _, row in merged.sort_values("total_profit", ascending=False).iterrows()
    ]


def detect_anomalies(sales: pd.DataFrame, inventory: pd.DataFrame):
    """
    Proactively surfaces things the owner hasn't asked about yet:
    - Demand spikes: sudden jump in sales — an opportunity to stock up before
      it becomes a stockout, not just a problem to react to.
    - Overstock: capital sitting idle in slow-moving inventory (broader net
      than stop_selling, which also requires low profit — this just flags
      excess days-of-stock regardless of profitability).
    - Critical stockouts: items with 3 days or less of stock left — more
      urgent than the standard 7-day reorder window, worth calling out
      separately so it isn't buried in a longer list.
    """
    anomalies = []
    max_date = sales["date"].max()

    # --- Demand spike detection: last 7 days vs prior 7 days ---
    last7_start = max_date - pd.Timedelta(days=6)
    prev7_start = max_date - pd.Timedelta(days=13)
    prev7_end = max_date - pd.Timedelta(days=7)

    last7 = sales[sales["date"] >= last7_start].groupby("product")["units_sold"].sum()
    prev7 = sales[(sales["date"] >= prev7_start) & (sales["date"] <= prev7_end)].groupby("product")["units_sold"].sum()

    spike_df = pd.DataFrame({"last7": last7, "prev7": prev7}).fillna(0)
    spike_df["pct_change"] = np.where(
        spike_df["prev7"] > 0,
        (spike_df["last7"] - spike_df["prev7"]) / spike_df["prev7"] * 100,
        0
    )
    spikes = spike_df[spike_df["pct_change"] >= 50].sort_values("pct_change", ascending=False)

    for product, row in spikes.iterrows():
        anomalies.append({
            "type": "demand_spike",
            "product": product,
            "severity": "opportunity",
            "message": f"{product} demand jumped {row['pct_change']:.0f}% in the last 7 days ({int(row['prev7'])} to {int(row['last7'])} units). Consider increasing stock to capture the trend before it turns into a stockout."
        })

    # --- Overstock detection: excess days-of-stock relative to demand ---
    product_stats = sales.groupby("product").agg(avg_daily_units=("units_sold", "mean")).reset_index()
    merged = product_stats.merge(inventory[["product", "current_stock", "unit_cost"]], on="product", how="left")
    merged["days_of_stock"] = np.where(
        merged["avg_daily_units"] > 0,
        merged["current_stock"] / merged["avg_daily_units"],
        999
    )
    overstocked = merged[merged["days_of_stock"] >= 45]

    for _, row in overstocked.iterrows():
        capital = row["current_stock"] * row["unit_cost"]
        anomalies.append({
            "type": "overstock",
            "product": row["product"],
            "severity": "warning",
            "message": f"{row['product']} has about {row['days_of_stock']:.0f} days of stock at current demand — Rs {capital:.0f} sitting idle. A short promotion could free up that capital faster."
        })

    # --- Critical stockouts: 3 days or less, more urgent than the 7-day window ---
    reorder_items = recommend_reorder(sales, inventory)
    critical = [r for r in reorder_items if r["days_of_stock_left"] <= 3]

    for r in critical:
        anomalies.append({
            "type": "critical_stockout",
            "product": r["product"],
            "severity": "critical",
            "message": f"{r['product']} will run out in {r['days_of_stock_left']} day(s) — this needs action today, not sometime this week."
        })

    return anomalies


def calculate_health_score(profit_analysis: dict, priority_actions: list, anomaly_alerts: list) -> dict:
    """
    Combines everything already computed into ONE explainable 0-100 score,
    so the owner (or a judge glancing at the dashboard) gets an instant
    read on business health instead of having to piece it together from
    three separate lists.

    Deductions are deliberately transparent (not a black-box ML score) so
    every point lost traces back to a specific, real reason — this is
    what makes the score trustworthy rather than a vague vibe.
    """
    score = 100.0
    reasons = []

    # Profit trend: reward growth, penalize decline
    change = profit_analysis["total_profit_change"]
    if change < 0:
        score -= 15
        reasons.append(f"-15: Profit declined Rs {abs(change):.0f} over the last 15 days")
    else:
        score += 5
        reasons.append(f"+5: Profit grew Rs {change:.0f} over the last 15 days")

    # Priority actions: weight by urgency
    for action in priority_actions:
        if action["urgency_label"] == "URGENT":
            score -= 8
            reasons.append(f"-8: Urgent action needed on {action['product']}")
        elif action["urgency_label"] == "HIGH":
            score -= 5
            reasons.append(f"-5: High-priority action needed on {action['product']}")
        else:
            score -= 2

    # Anomalies: critical hurts most, warnings hurt some, opportunities don't hurt
    for alert in anomaly_alerts:
        if alert["severity"] == "critical":
            score -= 10
            reasons.append(f"-10: Critical alert on {alert['product']}")
        elif alert["severity"] == "warning":
            score -= 4
            reasons.append(f"-4: Warning alert on {alert['product']}")

    score = max(0, min(100, round(score, 1)))

    if score >= 80:
        label = "Excellent"
    elif score >= 60:
        label = "Good"
    elif score >= 40:
        label = "Needs Attention"
    else:
        label = "Critical"

    return {
        "score": score,
        "label": label,
        "breakdown": reasons[:6],  # cap for readability
    }


def get_priority_actions(sales: pd.DataFrame, inventory: pd.DataFrame, top_n: int = 5):
    """
    Merges profit drivers, stop-selling candidates, and reorder needs into
    ONE ranked action list, comparable across categories by real rupee
    impact:

    - profit_driver: rupees already lost in the last 15 days (measured)
    - stop_selling: rupees of capital currently tied up in dead stock (recoverable now)
    - reorder: rupees of profit at risk over the next 7 days if it stocks out (projected)

    This answers the single most valuable question a business owner asks:
    "Out of everything wrong, what do I fix FIRST?"
    """
    profit = analyze_profit_drop(sales)
    stop_items = recommend_stop_selling(sales, inventory)
    reorder_items = recommend_reorder(sales, inventory)

    actions = []

    # --- Profit drivers: real, already-realized rupee loss ---
    for d in profit["top_drivers"]:
        actions.append({
            "category": "investigate_profit_driver",
            "product": d["product"],
            "impact_rupees": abs(d["profit_change"]),
            "reasoning": d["reasoning"],
            "recommended_action": f"Investigate why {d['product']} dropped and address the root cause (pricing, demand shift, or competition)."
        })

    # --- Stop-selling: rupees of capital currently tied up ---
    for item in stop_items:
        stock_row = inventory[inventory["product"] == item["product"]]
        unit_cost = float(stock_row["unit_cost"].values[0]) if not stock_row.empty else 0
        capital_tied_up = item["current_stock"] * unit_cost
        actions.append({
            "category": "stop_selling",
            "product": item["product"],
            "impact_rupees": round(capital_tied_up, 2),
            "reasoning": item["reasoning"],
            "recommended_action": f"Stop reordering {item['product']} and liquidate remaining stock to free up Rs {capital_tied_up:.0f} in capital."
        })

    # --- Reorder: projected rupees at risk over next 7 days if stocked out ---
    profit_per_unit = sales.groupby("product").apply(
        lambda g: g["profit"].sum() / g["units_sold"].sum() if g["units_sold"].sum() > 0 else 0
    )
    for item in reorder_items:
        ppu = float(profit_per_unit.get(item["product"], 0))
        potential_loss = item["daily_avg_demand"] * ppu * 7
        actions.append({
            "category": "reorder",
            "product": item["product"],
            "impact_rupees": round(potential_loss, 2),
            "reasoning": item["reasoning"],
            "recommended_action": f"Reorder {item['recommended_reorder_qty']} units of {item['product']} within {item['days_of_stock_left']} days to avoid an estimated Rs {potential_loss:.0f} in lost profit."
        })

    # Rank purely by rupee impact, regardless of category
    actions.sort(key=lambda x: x["impact_rupees"], reverse=True)
    top_actions = actions[:top_n]

    max_impact = top_actions[0]["impact_rupees"] if top_actions else 1
    for i, a in enumerate(top_actions):
        score = (a["impact_rupees"] / max_impact) * 100 if max_impact > 0 else 0
        a["priority_score"] = round(score, 1)
        a["rank"] = i + 1
        a["urgency_label"] = "URGENT" if score >= 70 else ("HIGH" if score >= 40 else "MEDIUM")

    return top_actions


def forecast_next_period_profit(sales: pd.DataFrame, days_back: int = 30, days_forward: int = 15):
    """
    Simple linear trend extrapolation on daily profit over the last
    `days_back` days, projected forward `days_forward` days. This gives
    a forward-looking number instead of only ever reporting on what
    already happened — the difference between a diagnostic tool and a
    genuinely predictive one.

    Uses ordinary least squares (np.polyfit, degree 1) on day-index vs
    daily profit. Deliberately simple/explainable over a heavier model
    (ARIMA/Prophet) since the demo needs speed and a defensible "why"
    behind the number, not marginal accuracy gains.
    """
    max_date = sales["date"].max()
    start_date = max_date - pd.Timedelta(days=days_back - 1)
    recent = sales[sales["date"] >= start_date]

    daily = recent.groupby("date")["profit"].sum().reset_index().sort_values("date")

    if len(daily) < 2:
        return {
            "forecast_period_days": days_forward,
            "forecast_total": 0.0,
            "forecast_daily_avg": 0.0,
            "trend_direction": "flat",
            "trend_slope_per_day": 0.0,
            "reasoning": "Not enough historical data to forecast reliably."
        }

    x = np.arange(len(daily))
    y = daily["profit"].values

    slope, intercept = np.polyfit(x, y, 1)

    future_x = np.arange(len(daily), len(daily) + days_forward)
    future_y = slope * future_x + intercept
    future_y = np.maximum(future_y, 0)  # display floor at 0, no negative profit forecast

    forecast_total = float(future_y.sum())
    forecast_daily_avg = float(future_y.mean())

    if slope > 1:
        direction = "upward"
    elif slope < -1:
        direction = "downward"
    else:
        direction = "flat"

    return {
        "forecast_period_days": days_forward,
        "forecast_total": round(forecast_total, 2),
        "forecast_daily_avg": round(forecast_daily_avg, 2),
        "trend_direction": direction,
        "trend_slope_per_day": round(float(slope), 2),
        "reasoning": (
            f"Based on the last {days_back} days' daily profit trend ({direction}, "
            f"Rs {slope:.0f}/day change), projected profit for the next {days_forward} "
            f"days is approximately Rs {forecast_total:.0f}."
        )
    }


def generate_executive_summary(sales: pd.DataFrame, inventory: pd.DataFrame) -> dict:
    """
    Produces the 'board meeting opening' — a short, high-conviction LLM
    narrative that ties together health score, top priority actions,
    critical anomalies, and the forward-looking forecast into the exact
    2-paragraph summary an owner would want read aloud before a meeting.

    Unlike ask_question (reactive — answers whatever's asked), this is
    proactive: always freshly generated from current data, with a fixed
    structure (state of business -> biggest risk/opportunity -> first
    move) so it reads consistently regardless of what the LLM emphasizes.

    Falls back to a deterministic templated summary if the LLM call
    fails for any reason — this is a demo centerpiece, so it must never
    show a blank error on stage.
    """
    profit = analyze_profit_drop(sales)
    priority_actions = get_priority_actions(sales, inventory)
    anomalies = detect_anomalies(sales, inventory)
    health = calculate_health_score(profit, priority_actions, anomalies)
    forecast = forecast_next_period_profit(sales)

    context = {
        "health_score": health,
        "profit_analysis": profit,
        "top_priority_actions": priority_actions[:3],
        "critical_anomalies": [a for a in anomalies if a["severity"] == "critical"],
        "forecast_next_period": forecast,
    }
    native_context = to_native(context)

    fallback_summary = (
        f"Business health is {health['label']} at {health['score']}/100. "
        f"{profit['summary']} "
        + (f"Top priority: {priority_actions[0]['recommended_action']} " if priority_actions else "")
        + forecast.get("reasoning", "")
    )

    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set — returning fallback executive summary.")
        return {"summary": fallback_summary, "generated_by": "fallback", "context": native_context}

    system_prompt = (
        "You are 'AI Business Doctor', opening a board meeting for a small Indian "
        "kirana/retail store owner. Write a short, confident, 2-paragraph executive "
        "summary using ONLY the JSON data provided below.\n\n"
        "Paragraph 1: State overall business health (cite the score and label) and the "
        "single biggest driver of that score, in plain conversational language.\n"
        "Paragraph 2: State the ONE most important action to take first (from "
        "top_priority_actions), the projected profit outlook (from forecast_next_period), "
        "and end with a clear, confident recommendation.\n\n"
        "Rules: Cite real Rs figures and product names. No bullet points, no headers, no "
        "markdown — write it as something a person would say out loud opening a meeting. "
        "Keep it under 130 words total.\n\n"
        f"DATA:\n{json.dumps(native_context, default=str)}"
    )

    try:
        response = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Open the meeting."},
                ],
                "temperature": 0.5,
                "max_tokens": 300,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        summary_text = data["choices"][0]["message"]["content"].strip()
        return {"summary": summary_text, "generated_by": "llm", "context": native_context}
    except requests.exceptions.RequestException as e:
        logger.error(f"Groq API request failed during executive summary: {e}")
        return {"summary": fallback_summary, "generated_by": "fallback", "context": native_context}
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.error(f"Unexpected Groq response format during executive summary: {e}")
        return {"summary": fallback_summary, "generated_by": "fallback", "context": native_context}


def build_llm_context(sales: pd.DataFrame, inventory: pd.DataFrame) -> str:
    """
    Builds a compact, token-efficient summary of the business data for the
    LLM to reason over. Deliberately condensed (not the full raw CSVs) to
    keep latency and cost low while still giving the model everything it
    needs to answer arbitrary questions accurately.
    """
    profit = analyze_profit_drop(sales)
    stop_selling = recommend_stop_selling(sales, inventory)
    reorder = recommend_reorder(sales, inventory)
    raw_summary = get_raw_summary_table(sales, inventory)
    trend = get_profit_trend(sales)
    priority_actions = get_priority_actions(sales, inventory)
    anomalies = detect_anomalies(sales, inventory)
    health = calculate_health_score(profit, priority_actions, anomalies)

    trend_start = trend[0]["profit"] if trend else 0
    trend_end = trend[-1]["profit"] if trend else 0

    context = {
        "profit_analysis": profit,
        "stop_selling_candidates": stop_selling,
        "reorder_candidates": reorder,
        "product_totals_90days": raw_summary,
        "profit_trend_first_day": trend_start,
        "profit_trend_last_day": trend_end,
        "top_priority_actions_ranked_by_rupee_impact": priority_actions,
        "proactive_anomaly_alerts": anomalies,
        "business_health_score": health,
    }
    return json.dumps(context, default=str)


def call_groq_llm(question: str, sales: pd.DataFrame, inventory: pd.DataFrame, history: list | None = None) -> str | None:
    """
    Sends the user's question + computed business data to Groq's Llama 4
    Scout model, so the assistant can answer ANY phrasing of a question,
    not just the fixed intents handled by keyword matching above.

    `history` (if provided) is a list of {"question": ..., "answer": ...}
    dicts from earlier in the same session, sent as real user/assistant
    message turns — not text-pasted — so follow-up questions like
    "what about last month?" are understood in context.

    Returns None on any failure (missing key, network issue, bad response)
    so the caller can fall back to the safe canned message instead of
    crashing or showing a blank error during a live demo.
    """
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set — skipping LLM fallback.")
        return None

    context = build_llm_context(sales, inventory)

    system_prompt = (
        "You are 'AI Business Doctor', a business advisor for a small Indian "
        "kirana/retail store. Answer the owner's question using ONLY the JSON "
        "business data provided below. Be conversational, specific, and concise "
        "(2-4 sentences). Always cite real numbers and product names from the "
        "data when relevant. Use the conversation history to understand "
        "follow-up questions (e.g. 'what about last month' refers back to "
        "whatever was just discussed). If the question cannot be answered from "
        "this data (e.g. it's unrelated to the business, like a joke or the "
        "weather), politely say you can only help with questions about their "
        "sales, profit, inventory, and stock — do not make up an answer.\n\n"
        f"BUSINESS DATA:\n{context}"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for turn in (history or [])[-6:]:
        messages.append({"role": "user", "content": turn["question"]})
        messages.append({"role": "assistant", "content": turn["answer"]})
    messages.append({"role": "user", "content": question})

    try:
        response = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": messages,
                "temperature": 0.4,
                "max_tokens": 300,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except requests.exceptions.RequestException as e:
        logger.error(f"Groq API request failed: {e}")
        return None
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.error(f"Unexpected Groq response format: {e}")
        return None


def ask_question(question: str, history: list | None = None):
    """
    Hybrid intent router:
    1. Fast-path: keyword matching for core, high-frequency questions
       (profit, stop-selling, reorder, priority, anomalies, overview) —
       instant, free, zero network dependency, deterministic for demo
       reliability.
    2. LLM fallback: anything that doesn't match a known intent is routed
       to Groq's Llama 4 Scout, grounded in the same computed business
       data plus recent conversation history, so follow-up questions
       ("what about last month?") are understood in context.
    3. Safety net: if the LLM call fails for any reason, falls back to a
       clear canned message instead of crashing.
    """
    q = question.lower()
    sales, inventory = load_data()

    if any(word in q for word in ["profit", "why", "decline", "down", "loss", "margin"]):
        analysis = analyze_profit_drop(sales)
        if not analysis["top_drivers"]:
            answer = "Profit has been stable — no significant negative drivers found in the last 15 days."
        else:
            top = analysis["top_drivers"][0]
            others = ", ".join(d["product"] for d in analysis["top_drivers"][1:])
            answer = (
                f"{analysis['summary']} The biggest contributor is {top['product']}, "
                f"which alone dropped Rs {abs(top['profit_change']):.0f} ({abs(top['pct_change'])}%). "
                + (f"Other contributing products: {others}." if others else "")
            )
        return {"intent": "profit_analysis", "answer": answer.strip(), "data": analysis}

    if any(word in q for word in ["stop", "discontinue", "remove", "underperform", "worst", "drop selling"]):
        items = recommend_stop_selling(sales, inventory)
        if not items:
            answer = "No products currently qualify as stop-selling candidates — inventory is performing reasonably across the board."
        else:
            names = ", ".join(i["product"] for i in items)
            answer = f"Based on 90 days of data, {len(items)} product(s) are worth reconsidering: {names}. These combine low daily sales with low total profit contribution, meaning they tie up shelf space and capital without earning it back."
        return {"intent": "stop_selling", "answer": answer, "data": items}

    if any(word in q for word in ["reorder", "restock", "stock out", "running out", "order", "supply"]):
        items = recommend_reorder(sales, inventory)
        if not items:
            answer = "Nothing is urgently low on stock right now — no reorders needed in the next 7 days based on current demand."
        else:
            most_urgent = items[0]
            answer = (
                f"{len(items)} product(s) need reordering soon. Most urgent: {most_urgent['product']}, "
                f"with only {most_urgent['days_of_stock_left']} days of stock left at current demand — "
                f"reorder at least {most_urgent['recommended_reorder_qty']} units to stay covered for the next week."
            )
        return {"intent": "reorder", "answer": answer, "data": items}

    if any(word in q for word in ["health score", "score", "rating", "grade"]):
        profit = analyze_profit_drop(sales)
        actions = get_priority_actions(sales, inventory)
        anomalies = detect_anomalies(sales, inventory)
        health = calculate_health_score(profit, actions, anomalies)
        answer = f"Your business health score is {health['score']}/100 ({health['label']}). " + " ".join(health["breakdown"][:2])
        return {"intent": "health_score", "answer": answer.strip(), "data": health}

    if any(word in q for word in ["anomaly", "anomalies", "alert", "unusual", "anything i should know", "watch out", "spike", "overstock"]):
        anomalies = detect_anomalies(sales, inventory)
        if not anomalies:
            answer = "Nothing unusual right now — no demand spikes, overstock, or critical stockouts detected."
        else:
            critical_count = sum(1 for a in anomalies if a["severity"] == "critical")
            top = anomalies[0]
            answer = (
                f"Found {len(anomalies)} thing(s) worth flagging"
                + (f", including {critical_count} critical." if critical_count else ".")
                + f" Most notable: {top['message']}"
            )
        return {"intent": "anomaly_alerts", "answer": answer.strip(), "data": anomalies}

    if any(word in q for word in ["priority", "prioritize", "what should i do", "action plan", "first", "most important", "top action"]):
        actions = get_priority_actions(sales, inventory)
        if not actions:
            answer = "Everything looks stable right now — no urgent actions needed today."
        else:
            top = actions[0]
            answer = (
                f"Your top priority: {top['recommended_action']} "
                f"(Rs {top['impact_rupees']:.0f} impact, {top['urgency_label']}). "
                + (f"After that, {len(actions) - 1} more action(s) are worth addressing this week." if len(actions) > 1 else "")
            )
        return {"intent": "priority_actions", "answer": answer.strip(), "data": actions}

    if any(word in q for word in ["risk", "health", "summary", "overview", "doing"]):
        profit = analyze_profit_drop(sales)
        stop = recommend_stop_selling(sales, inventory)
        reorder = recommend_reorder(sales, inventory)
        answer = (
            f"{profit['summary']} {len(stop)} product(s) are dragging on capital and worth discontinuing. "
            f"{len(reorder)} product(s) need urgent reordering to avoid stockouts. "
            f"Overall, the business needs attention on {len(stop) + len(reorder)} specific items this week."
        )
        return {"intent": "overview", "answer": answer, "data": {"profit": profit, "stop_selling": stop, "reorder": reorder}}

    llm_answer = call_groq_llm(question, sales, inventory, history=history)
    if llm_answer:
        return {"intent": "llm_general", "answer": llm_answer, "data": None}

    return {
        "intent": "unknown",
        "answer": "I can currently answer questions about profit trends, which products to stop selling, and what to reorder. Try asking something like 'Why are profits down?' or 'What should I reorder?'",
        "data": None
    }


def get_all_insights():
    sales, inventory = load_data()
    result = {
        "profit_analysis": analyze_profit_drop(sales),
        "stop_selling": recommend_stop_selling(sales, inventory),
        "reorder": recommend_reorder(sales, inventory),
        "profit_trend": get_profit_trend(sales),
        "raw_summary": get_raw_summary_table(sales, inventory),
        "priority_actions": get_priority_actions(sales, inventory),
        "anomaly_alerts": detect_anomalies(sales, inventory),
    }
    result["health_score"] = calculate_health_score(
        result["profit_analysis"], result["priority_actions"], result["anomaly_alerts"]
    )
    result["executive_summary"] = generate_executive_summary(sales, inventory)
    return to_native(result)


if __name__ == "__main__":
    import json
    insights = get_all_insights()
    print(json.dumps(insights, indent=2, default=str))