import os
import json
import logging
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import pandas as pd
import numpy as np
import requests
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("ai_business_doctor")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# Twilio config (reused from main.py)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
twilio_client = None

if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        logger.info("Twilio client initialized in analysis_engine.py")
    except Exception as e:
        logger.error(f"Failed to initialize Twilio client in analysis_engine.py: {e}")


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


def get_business_goal(authenticated_supabase_client) -> Optional[str]:
    """
    Helper function to fetch the current user's business goal from their profile.
    Takes an authenticated Supabase client (per-request auth).
    """
    try:
        response = authenticated_supabase_client.table('profiles').select('business_goal').single().execute()
        return getattr(response.data, 'business_goal', None) if hasattr(response, 'data') else response.data.get('business_goal')
    except Exception as e:
        logger.error(f"Failed to fetch business goal: {e}")
        return None


def normalize_date_series(date_series: pd.Series) -> pd.Series:
    """Normalize date values, including Excel serial dates from uploaded files."""
    if date_series.dtype.kind in "biuf":
        try:
            normalized = pd.to_datetime(date_series, unit="D", origin="1899-12-30")
            if normalized.notna().all():
                return normalized
        except Exception:
            pass

    parsed = pd.to_datetime(date_series, errors="coerce")
    if parsed.isna().any():
        numeric = pd.to_numeric(date_series, errors="coerce")
        if numeric.notna().all() and numeric.between(30, 60000).all():
            try:
                parsed = pd.to_datetime(numeric, unit="D", origin="1899-12-30")
            except Exception:
                pass

    return parsed


def capture_daily_snapshot(user_id: int):
    user_dir = os.path.join(os.path.dirname(__file__), "user_data", str(user_id))
    config_path = os.path.join(user_dir, "data_source_config.json")
    if not os.path.exists(config_path):
        return

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except Exception:
        return

    if config.get("mode") != "live":
        return

    live_sales_path = config.get("sales_path")
    if not live_sales_path or not os.path.exists(live_sales_path):
        return

    live_mtime = os.path.getmtime(live_sales_path)
    last_captured_mtime = config.get("last_captured_mtime", 0.0)

    if live_mtime > last_captured_mtime:
        try:
            if live_sales_path.lower().endswith(('.xlsx', '.xls')):
                live_df = pd.read_excel(live_sales_path, engine='openpyxl')
            else:
                live_df = pd.read_csv(live_sales_path)

            required_cols = ["product", "units_sold", "revenue", "profit"]
            if not all(col in live_df.columns for col in required_cols):
                logger.error("Live sales file is missing required columns during snapshot capture.")
                return

            live_df = live_df[required_cols].copy()
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            live_df["date"] = today_str
            live_df = live_df[["date", "product", "units_sold", "revenue", "profit"]]

            acc_path = os.path.join(user_dir, "accumulated_sales_data.csv")
            if os.path.exists(acc_path) and os.path.getsize(acc_path) > 0:
                try:
                    acc_df = pd.read_csv(acc_path)
                except Exception:
                    acc_df = pd.DataFrame(columns=["date", "product", "units_sold", "revenue", "profit"])
            else:
                acc_df = pd.DataFrame(columns=["date", "product", "units_sold", "revenue", "profit"])

            if not acc_df.empty:
                # Upsert: remove today's entries matching products in live_df
                mask = (acc_df["date"] == today_str) & (acc_df["product"].isin(live_df["product"]))
                acc_df = acc_df[~mask]

            new_acc_df = pd.concat([acc_df, live_df], ignore_index=True)
            new_acc_df.to_csv(acc_path, index=False)

            config["last_captured_mtime"] = live_mtime
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)

            logger.info(f"Captured sales snapshot for user {user_id} on {today_str} (mtime: {live_mtime})")
        except Exception as e:
            logger.error(f"Failed to capture daily snapshot for user {user_id}: {e}")


def normalize_date_series(date_series: pd.Series) -> pd.Series:
    """Normalize date values, including Excel serial dates from uploaded files."""
    if date_series.dtype.kind in "biuf":
        try:
            normalized = pd.to_datetime(date_series, unit="D", origin="1899-12-30")
            if normalized.notna().all():
                return normalized
        except Exception:
            pass

    parsed = pd.to_datetime(date_series, errors="coerce")
    if parsed.isna().any():
        numeric = pd.to_numeric(date_series, errors="coerce")
        if numeric.notna().all() and numeric.between(30, 60000).all():
            try:
                parsed = pd.to_datetime(numeric, unit="D", origin="1899-12-30")
            except Exception:
                pass

    return parsed


def load_data(user_id: int):
    user_dir = os.path.join(os.path.dirname(__file__), "user_data", str(user_id))
    config_path = os.path.join(user_dir, "data_source_config.json")
    
    # Default user-scoped paths
    sales_path = os.path.join(user_dir, "sales_data.csv")
    inventory_path = os.path.join(user_dir, "inventory_data.csv")
    
    mode = "demo"
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
                mode = config.get("mode", "demo")
                if mode == "uploaded":
                    sales_path = config.get("sales_path") or os.path.join(user_dir, "sales_data.csv")
                    inventory_path = config.get("inventory_path") or os.path.join(user_dir, "inventory_data.csv")
                elif mode == "live":
                    # Pre-create empty accumulated file if it doesn't exist
                    acc_path = os.path.join(user_dir, "accumulated_sales_data.csv")
                    if not os.path.exists(acc_path):
                        df = pd.DataFrame(columns=["date", "product", "units_sold", "revenue", "profit"])
                        df.to_csv(acc_path, index=False)

                    capture_daily_snapshot(user_id)
                    sales_path = acc_path
                    inventory_path = config.get("inventory_path")
        except Exception as e:
            logger.error(f"Failed to read data_source_config.json for user {user_id}: {e}")

    # Fallbacks if path is empty or file doesn't exist
    if not sales_path or not os.path.exists(sales_path):
        sales_path = os.path.join(user_dir, "sales_data.csv")
    if not inventory_path or not os.path.exists(inventory_path):
        inventory_path = os.path.join(user_dir, "inventory_data.csv")

    # If those STILL don't exist, fall back to global demo
    if not os.path.exists(sales_path):
        sales_path = os.path.join(os.path.dirname(__file__), "demo_sales_data.csv")
    if not os.path.exists(inventory_path):
        inventory_path = os.path.join(os.path.dirname(__file__), "demo_inventory_data.csv")

    def read_file(path: str) -> pd.DataFrame:
        if path.lower().endswith(('.xlsx', '.xls')):
            return pd.read_excel(path, engine='openpyxl')
        else:
            return pd.read_csv(path)

    sales = read_file(sales_path)
    inventory = read_file(inventory_path)
    sales["date"] = normalize_date_series(sales["date"])
    return sales, inventory



def analyze_profit_drop(sales: pd.DataFrame):
    """Compares last 15 days vs previous 15 days to find what's driving any profit change."""
    if sales.empty or sales["date"].dt.date.nunique() < 15:
        return {
            "total_profit_change": 0.0,
            "summary": "Still learning your business — check back after a few more days of data (at least 15 days) to see profit trends.",
            "top_drivers": [],
            "insufficient_data": True
        }

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
    if profit_analysis.get("insufficient_data"):
        return {
            "score": 100.0,
            "label": "Pending",
            "breakdown": ["Health score calculations are pending. Awaiting at least 15 days of store history."],
            "insufficient_data": True
        }

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
    if sales.empty or sales["date"].dt.date.nunique() < 15:
        return {
            "forecast_period_days": days_forward,
            "forecast_total": 0.0,
            "forecast_daily_avg": 0.0,
            "trend_direction": "flat",
            "trend_slope_per_day": 0.0,
            "reasoning": "Still learning your business — check back after a few more days of data (at least 15 days) to see profit forecasts.",
            "insufficient_data": True
        }

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


def _extract_top_risk(priority_actions: list, anomalies: list, profit: dict) -> str:
    critical = [a for a in anomalies if a["severity"] == "critical"]
    if critical:
        return critical[0]["message"]
    if priority_actions:
        top = priority_actions[0]
        return f"{top['product']}: {top['recommended_action']} (Rs {top['impact_rupees']:,.0f} impact)"
    if profit.get("top_drivers"):
        d = profit["top_drivers"][0]
        return f"{d['product']} profit dropped Rs {abs(d['profit_change']):,.0f} in the last 15 days"
    return "No critical risks flagged — business metrics are within normal range."


def _extract_top_opportunity(anomalies: list) -> str:
    opportunities = [a for a in anomalies if a["severity"] == "opportunity"]
    if opportunities:
        return opportunities[0]["message"]
    return "No major demand spikes detected — focus on protecting margins and stock levels."


def _call_groq_narrative(system_prompt: str, user_prompt: str = "Open the meeting.", max_tokens: int = 350) -> str | None:
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY is not set")
        return None
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
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.5,
                "max_tokens": max_tokens,
            },
            timeout=15,
        )
        logger.info(f"Groq API response status code: {response.status_code}")
        logger.info(f"Groq API response headers: {dict(response.headers)}")
        logger.info(f"Groq API response text: {response.text}")
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except requests.exceptions.RequestException as e:
        logger.exception(f"Groq API request failed (exception type: {type(e).__name__}): {e}")
        return None
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.exception(f"Groq API response parsing failed (exception type: {type(e).__name__}): {e}")
        return None


def get_executive_summary(sales: pd.DataFrame, inventory: pd.DataFrame, mode: str | None = None) -> dict:
    """
    Board-meeting opening narrative combining health score, priority actions,
    anomaly alerts, and a 15-day profit forecast. Returns structured fields
    plus an LLM-written narrative with deterministic fallback.
    """
    insufficient_history = sales.empty or sales["date"].dt.date.nunique() < 15
    if insufficient_history:
        if mode == "live":
            narrative = (
                "Good afternoon. We are currently in learning mode. AI Business Doctor is building a history from your daily updates. "
                "Please continue updating your sales data. Once 15 days of history are accumulated, we will generate your board narrative and forecast."
            )
        else:
            narrative = (
                "Good afternoon. We have less than 15 days of historical data available, so the board narrative and forecast are not yet ready. "
                "Please upload a larger dataset or add more sales history to unlock the full diagnostic report."
            )

        return {
            "narrative": narrative,
            "health_score": 100.0,
            "health_label": "Pending",
            "profit_forecast_next_15_days": 0.0,
            "top_risk": "Insufficient history (less than 15 days)",
            "top_opportunity": "Data accumulation in progress",
            "generated_by": "fallback",
            "context": {},
            "insufficient_data": True
        }

    profit = analyze_profit_drop(sales)
    priority_actions = get_priority_actions(sales, inventory)
    anomalies = detect_anomalies(sales, inventory)
    health = calculate_health_score(profit, priority_actions, anomalies)
    forecast = forecast_next_period_profit(sales)

    top_risk = _extract_top_risk(priority_actions, anomalies, profit)
    top_opportunity = _extract_top_opportunity(anomalies)
    profit_forecast = forecast["forecast_total"]

    context = {
        "health_score": health,
        "profit_analysis": profit,
        "top_priority_actions": priority_actions[:3],
        "anomaly_alerts": anomalies,
        "forecast_next_period": forecast,
        "top_risk": top_risk,
        "top_opportunity": top_opportunity,
    }
    native_context = to_native(context)

    top_action = priority_actions[0]["recommended_action"] if priority_actions else "maintain current operations"
    fallback_narrative = (
        f"Good afternoon. Here's today's business review. "
        f"Your business health score is {health['score']}/100 ({health['label']}). "
        f"{profit['summary']} "
        f"The single biggest risk right now: {top_risk} "
        f"Top opportunity: {top_opportunity} "
        f"Profit forecast for the next 15 days is approximately Rs {profit_forecast:,.0f} "
        f"({forecast['trend_direction']} trend). "
        f"The one action that matters most today: {top_action}."
    )

    system_prompt = (
        "You are 'AI Business Doctor', opening a business review meeting for a small Indian "
        "kirana/retail store owner. Write a confident 4-6 sentence executive summary using "
        "ONLY the JSON data provided below.\n\n"
        "Start with: 'Good afternoon. Here's today's business review.'\n"
        "Then cover in order: current health (cite score and label), the single biggest risk, "
        "the top opportunity if any, the 15-day profit forecast (cite Rs figure), and the "
        "one action that matters most today.\n\n"
        "Rules: Cite real Rs figures and product names. No bullet points, no headers, no "
        "markdown — write it as spoken prose. Keep it under 160 words.\n\n"
        f"DATA:\n{json.dumps(native_context, default=str)}"
    )

    narrative = _call_groq_narrative(system_prompt)
    generated_by = "llm" if narrative else "fallback"
    if not narrative:
        if not GROQ_API_KEY:
            logger.warning("GROQ_API_KEY not set — returning fallback executive summary.")
        narrative = fallback_narrative

    return {
        "narrative": narrative,
        "health_score": health["score"],
        "health_label": health["label"],
        "profit_forecast_next_15_days": profit_forecast,
        "top_risk": top_risk,
        "top_opportunity": top_opportunity,
        "generated_by": generated_by,
        "context": native_context,
    }


def generate_executive_summary(sales: pd.DataFrame, inventory: pd.DataFrame) -> dict:
    """Backward-compatible wrapper used by get_all_insights and PDF export."""
    result = get_executive_summary(sales, inventory)
    return {
        "summary": result["narrative"],
        "generated_by": result["generated_by"],
        "context": result["context"],
        "insufficient_data": result.get("insufficient_data")
    }


def simulate_scenario(product: str, demand_change_pct: float, user_id: int) -> dict:
    """
    Re-runs reorder and profit projections assuming a product's daily demand
    shifts by the given percentage.
    """
    sales, inventory = load_data(user_id)

    inv_row = inventory[inventory["product"] == product]
    if inv_row.empty:
        raise ValueError(f"Product '{product}' not found in inventory.")

    current_stock = int(inv_row["current_stock"].values[0])

    max_date = sales["date"].max()
    recent_start = max_date - pd.Timedelta(days=14)
    recent = sales[(sales["date"] >= recent_start) & (sales["product"] == product)]
    baseline_daily = float(recent["units_sold"].sum() / 15) if not recent.empty else 0.0

    multiplier = 1 + (demand_change_pct / 100)
    adjusted_daily = baseline_daily * multiplier

    baseline_days = current_stock / baseline_daily if baseline_daily > 0 else 999.0
    projected_days = current_stock / adjusted_daily if adjusted_daily > 0 else 999.0

    product_sales = sales[sales["product"] == product]
    total_units = product_sales["units_sold"].sum()
    ppu = float(product_sales["profit"].sum() / total_units) if total_units > 0 else 0.0

    daily_profit_delta = (adjusted_daily - baseline_daily) * ppu
    projected_profit_impact = round(daily_profit_delta * 7, 2)

    if demand_change_pct > 0:
        if projected_days <= 7:
            reorder_qty = max(1, int(adjusted_daily * 7))
            recommended_action = (
                f"Demand up {demand_change_pct:.0f}% — stock falls to {projected_days:.1f} days. "
                f"Reorder ~{reorder_qty} units of {product} immediately to avoid stockout."
            )
        else:
            recommended_action = (
                f"Demand up {demand_change_pct:.0f}% — adds ~Rs {projected_profit_impact:,.0f} profit "
                f"over 7 days. Stock still covers {projected_days:.1f} days; monitor weekly."
            )
    elif demand_change_pct < 0:
        if projected_days >= 45:
            recommended_action = (
                f"Demand down {abs(demand_change_pct):.0f}% — stock stretches to {projected_days:.0f} days. "
                f"Pause reorders on {product} and consider a promotion to free capital."
            )
        else:
            recommended_action = (
                f"Demand down {abs(demand_change_pct):.0f}% — projected profit impact "
                f"Rs {projected_profit_impact:,.0f} over 7 days. Adjust reorder quantities accordingly."
            )
    else:
        recommended_action = f"No demand change assumed for {product} — baseline scenario holds."

    return {
        "product": product,
        "demand_change_pct": demand_change_pct,
        "baseline_days_of_stock_left": round(baseline_days, 1),
        "projected_days_of_stock_left": round(projected_days, 1),
        "projected_profit_impact": projected_profit_impact,
        "recommended_action": recommended_action,
    }


def _advisor_prompt(role: str, lens: str, context_json: str) -> str:
    return (
        f"You are a {role} advisor on a panel reviewing a small Indian kirana/retail store. "
        f"Give a 2-3 sentence take from a {lens} perspective using ONLY the JSON data below. "
        f"Cite real Rs figures and product names. Be direct and professional — no bullet points, "
        f"no markdown.\n\nDATA:\n{context_json}"
    )


def get_advisor_panel(sales: pd.DataFrame, inventory: pd.DataFrame) -> dict:
    """
    Calls Groq three times (Finance, Operations, Marketing) with the same
    business context, running requests concurrently via thread pool.
    """
    profit = analyze_profit_drop(sales)
    priority_actions = get_priority_actions(sales, inventory)
    anomalies = detect_anomalies(sales, inventory)
    health = calculate_health_score(profit, priority_actions, anomalies)
    forecast = forecast_next_period_profit(sales)

    context = to_native({
        "health_score": health,
        "profit_analysis": profit,
        "top_priority_actions": priority_actions[:5],
        "anomaly_alerts": anomalies,
        "forecast_next_period": forecast,
        "stop_selling": recommend_stop_selling(sales, inventory),
        "reorder": recommend_reorder(sales, inventory),
    })
    context_json = json.dumps(context, default=str)

    advisors = [
        ("finance_take", "Finance", "cash flow, margins, capital tied up in stock, and profit risk"),
        ("operations_take", "Operations", "inventory levels, reorder timing, stockouts, and supply chain"),
        ("marketing_take", "Marketing", "demand trends, promotions, product mix, and growth opportunities"),
    ]

    fallbacks = {
        "finance_take": (
            f"From a finance lens: health is {health['score']}/100 ({health['label']}). "
            f"15-day profit change is Rs {profit['total_profit_change']:,.0f}. "
            f"Next 15 days forecast ~Rs {forecast['forecast_total']:,.0f}."
        ),
        "operations_take": (
            f"Operations view: {len(recommend_reorder(sales, inventory))} products need urgent reorder. "
            + (f"Top priority — {priority_actions[0]['recommended_action']}" if priority_actions else "No urgent ops actions.")
        ),
        "marketing_take": (
            f"Marketing view: {len([a for a in anomalies if a['severity'] == 'opportunity'])} demand opportunities detected. "
            + (anomalies[0]["message"] if anomalies else "Focus on core sellers and margin protection.")
        ),
    }

    results = {}

    def _fetch_take(key, role, lens):
        prompt = _advisor_prompt(role, lens, context_json)
        text = _call_groq_narrative(prompt, user_prompt="Give your professional take.", max_tokens=200)
        return key, text or fallbacks[key]

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(_fetch_take, key, role, lens): key
            for key, role, lens in advisors
        }
        for future in as_completed(futures):
            key, text = future.result()
            results[key] = text

    return {
        "finance_take": results.get("finance_take", fallbacks["finance_take"]),
        "operations_take": results.get("operations_take", fallbacks["operations_take"]),
        "marketing_take": results.get("marketing_take", fallbacks["marketing_take"]),
    }


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


def ask_question(question: str, history: list | None = None, user_id: int = None):
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
    sales, inventory = load_data(user_id)

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


# --- AI Root Cause Engine ---

# Threshold constants (not magic numbers!)
SALES_DROP_THRESHOLD_PCT = 20.0  # 20% or more drop = anomaly
MARGIN_DROP_THRESHOLD_PCT = 15.0  # 15% or more drop = anomaly
CRITICAL_IMPACT_THRESHOLD = 5000.0  # Rs 5000+ = Critical
HIGH_IMPACT_THRESHOLD = 2000.0  # Rs 2000+ = High
MEDIUM_IMPACT_THRESHOLD = 500.0  # Rs 500+ = Medium
MIN_DATA_DAYS = 30  # Need at least 30 days of data


def calculate_root_causes(user_id: int, authenticated_supabase_client) -> dict:
    """
    Calculates root causes of business performance issues with:
    - Deterministic anomaly detection
    - Financial impact calculations
    - Severity ranking
    - Confidence scores (based on data availability)
    - Template-based recommendations with LLM fallback
    """
    # Load data
    sales, inventory = load_data(user_id)
    causes = []
    data_sufficiency_note = ""
    period_compared = {}

    # Step 1: Check data sufficiency
    if sales.empty or sales["date"].dt.date.nunique() < MIN_DATA_DAYS:
        data_sufficiency_note = (
            f"Need at least {MIN_DATA_DAYS} days of sales history for full root cause analysis. "
            f"Currently have {sales['date'].dt.date.nunique()} days of data."
        )
        return {
            "period_compared": period_compared,
            "causes": causes,
            "data_sufficiency_note": data_sufficiency_note,
            "insufficient_data": True
        }

    # Step 2: Split into current month and previous month
    max_date = sales["date"].max()
    current_month = max_date.replace(day=1)
    previous_month = (current_month - pd.Timedelta(days=1)).replace(day=1)

    current_month_sales = sales[sales["date"].dt.to_period("M") == current_month.to_period("M")]
    previous_month_sales = sales[sales["date"].dt.to_period("M") == previous_month.to_period("M")]

    period_compared = {
        "current_month_start": current_month.isoformat(),
        "previous_month_start": previous_month.isoformat(),
        "current_month_days": current_month_sales["date"].dt.date.nunique(),
        "previous_month_days": previous_month_sales["date"].dt.date.nunique()
    }

    # Calculate confidence: based on data availability
    min_days = min(period_compared["current_month_days"], period_compared["previous_month_days"])
    confidence_base = min(1.0, min_days / 15.0)  # Full confidence at 15 days per month

    # Step 3: Analyze per product
    if not current_month_sales.empty and not previous_month_sales.empty:
        # Aggregate by product
        current_agg = current_month_sales.groupby("product").agg(
            total_units=("units_sold", "sum"),
            total_revenue=("revenue", "sum"),
            total_profit=("profit", "sum")
        ).reset_index()

        previous_agg = previous_month_sales.groupby("product").agg(
            total_units=("units_sold", "sum"),
            total_revenue=("revenue", "sum"),
            total_profit=("profit", "sum")
        ).reset_index()

        merged = current_agg.merge(previous_agg, on="product", suffixes=("_current", "_previous"), how="outer").fillna(0)

        # Calculate deltas
        merged["sales_delta_pct"] = np.where(
            merged["total_units_previous"] > 0,
            (merged["total_units_current"] - merged["total_units_previous"]) / merged["total_units_previous"] * 100,
            0
        )

        merged["current_margin_pct"] = np.where(
            merged["total_revenue_current"] > 0,
            (merged["total_profit_current"] / merged["total_revenue_current"] * 100),
            0
        )

        merged["previous_margin_pct"] = np.where(
            merged["total_revenue_previous"] > 0,
            (merged["total_profit_previous"] / merged["total_revenue_previous"] * 100),
            0
        )

        merged["margin_delta_pct"] = merged["current_margin_pct"] - merged["previous_margin_pct"]

        # Check for anomalies
        for _, row in merged.iterrows():
            product = row["product"]
            # 1. Sales drop anomaly
            if row["sales_delta_pct"] <= -SALES_DROP_THRESHOLD_PCT and row["total_units_previous"] > 0:
                financial_impact = row["total_profit_previous"] - row["total_profit_current"]
                if financial_impact > 0:
                    causes.append(_create_root_cause(
                        title=f"Sales Drop for {product}",
                        explanation=(
                            f"Sales of {product} dropped by {abs(row['sales_delta_pct']):.1f}% this month compared to last month, "
                            f"from {int(row['total_units_previous'])} units to {int(row['total_units_current'])} units."
                        ),
                        financial_impact=financial_impact,
                        recommended_action=f"Investigate why {product} sales dropped—check pricing, competition, or stock availability.",
                        expected_recovery=financial_impact * 0.8,  # 80% recovery expected if fixed
                        confidence=confidence_base,
                        product=product,
                        cause_type="sales_drop"
                    ))

            # 2. Margin drop anomaly
            if row["margin_delta_pct"] <= -MARGIN_DROP_THRESHOLD_PCT and row["total_units_current"] > 0:
                financial_impact = row["total_units_current"] * (row["previous_margin_pct"] - row["current_margin_pct"]) / 100
                if financial_impact > 0:
                    causes.append(_create_root_cause(
                        title=f"Margin Drop for {product}",
                        explanation=(
                            f"Margin for {product} dropped by {abs(row['margin_delta_pct']):.1f} percentage points this month."
                        ),
                        financial_impact=financial_impact,
                        recommended_action=f"Review {product}'s cost structure and pricing strategy.",
                        expected_recovery=financial_impact * 0.9,  # 90% recovery expected
                        confidence=confidence_base,
                        product=product,
                        cause_type="margin_drop"
                    ))

    # Step 4: Check for stockout days (using inventory and recent sales)
    if not inventory.empty and not current_month_sales.empty:
        recent_sales = current_month_sales[current_month_sales["date"] >= (max_date - pd.Timedelta(days=14))]
        recent_demand = recent_sales.groupby("product")["units_sold"].sum().reset_index()
        recent_demand["daily_avg"] = recent_demand["units_sold"] / 14
        inventory_with_demand = inventory.merge(recent_demand, on="product", how="left").fillna(0)

        for _, row in inventory_with_demand.iterrows():
            product = row["product"]
            daily_avg = row["daily_avg"]
            current_stock = row["current_stock"]
            if daily_avg > 0:
                days_of_stock = current_stock / daily_avg
                if days_of_stock <= 3:
                    profit_per_unit = 0
                    product_sales = current_month_sales[current_month_sales["product"] == product]
                    if not product_sales.empty:
                        total_units = product_sales["units_sold"].sum()
                        if total_units > 0:
                            profit_per_unit = product_sales["profit"].sum() / total_units
                    financial_impact = daily_avg * profit_per_unit * 7  # 7 days of lost profit
                    if financial_impact > 0:
                        causes.append(_create_root_cause(
                            title=f"Critical Stockout Risk for {product}",
                            explanation=(
                                f"{product} has only {days_of_stock:.1f} days of stock left at current demand levels."
                            ),
                            financial_impact=financial_impact,
                            recommended_action=f"Reorder {product} immediately—at least {int(daily_avg * 7)} units for 7 days coverage.",
                            expected_recovery=financial_impact,
                            confidence=confidence_base,
                            product=product,
                            cause_type="stockout_risk"
                        ))

    # Step 5: Rank causes by financial impact descending
    causes.sort(key=lambda x: x["financial_impact"], reverse=True)

    return {
        "period_compared": period_compared,
        "causes": causes,
        "data_sufficiency_note": data_sufficiency_note if data_sufficiency_note else None,
        "insufficient_data": False
    }


def _create_root_cause(title: str, explanation: str, financial_impact: float, recommended_action: str, expected_recovery: float, confidence: float, product: str, cause_type: str) -> dict:
    """Helper to create root cause object with severity and template-based recommendation"""
    # Calculate severity based on financial impact
    if financial_impact >= CRITICAL_IMPACT_THRESHOLD:
        severity = "Critical"
    elif financial_impact >= HIGH_IMPACT_THRESHOLD:
        severity = "High"
    elif financial_impact >= MEDIUM_IMPACT_THRESHOLD:
        severity = "Medium"
    else:
        severity = "Low"

    # Template-based recommendation is already passed in, try to enhance with LLM
    # But for now, use template (we can add LLM enhancement later if needed)
    return {
        "title": title,
        "explanation": explanation,
        "financial_impact": round(financial_impact, 2),
        "severity": severity,
        "confidence": round(confidence, 2),
        "recommended_action": recommended_action,
        "expected_recovery": round(expected_recovery, 2),
        "product": product,
        "cause_type": cause_type
    }


def get_daily_summary(sales: pd.DataFrame, inventory: pd.DataFrame, test_date: datetime.date | None = None) -> dict:
    """
    Returns daily business summary:
    - today's total profit/loss
    - list of top-selling items today
    - placeholder for restocked items (since no restock history exists yet)
    """
    today = test_date or datetime.date.today()
    # Filter sales for today
    today_sales = sales[sales["date"].dt.date == today].copy()
    
    # Total profit today
    total_profit_today = round(float(today_sales["profit"].sum()), 2)
    
    # Top-selling items: group by product, sum units and revenue
    if not today_sales.empty:
        top_sellers = (
            today_sales
            .groupby("product")
            .agg(units_sold=("units_sold", "sum"), revenue=("revenue", "sum"))
            .reset_index()
            .sort_values("units_sold", ascending=False)
        )
        top_sellers_list = [
            {
                "product": row["product"],
                "units_sold": int(row["units_sold"]),
                "revenue": round(float(row["revenue"]), 2)
            }
            for _, row in top_sellers.iterrows()
        ]
    else:
        top_sellers_list = []
    
    # No restock history available yet, so return empty list
    restocked_today = []
    
    return {
        "date": today.isoformat(),
        "total_profit_today": total_profit_today,
        "top_selling_items": top_sellers_list,
        "restocked_items_today": restocked_today
    }


def send_daily_email(summary: dict, recipient_email: str) -> None:
    """
    Sends daily summary email via Gmail SMTP
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        logger.warning("GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set — skipping email")
        return
    
    subject = f"Daily Business Report - {summary['date']}"
    
    # Build body
    body = f"Daily Business Report for {summary['date']}\n"
    body += "=======================================\n\n"
    body += f"Total Profit Today: Rs {summary['total_profit_today']:,.2f}\n\n"
    
    if summary['top_selling_items']:
        body += "Top Selling Items:\n"
        body += "-------------------\n"
        for item in summary['top_selling_items'][:5]:  # Top 5
            body += f"- {item['product']}: {item['units_sold']} units sold, Rs {item['revenue']:,.2f}\n"
        body += "\n"
    
    if summary['restocked_items_today']:
        body += "Items Restocked Today:\n"
        body += "-----------------------\n"
        for item in summary['restocked_items_today']:
            body += f"- {item['product']}: {item['qty']} units\n"
    else:
        body += "No items restocked today.\n\n"
    
    # Create message
    msg = MIMEMultipart()
    msg['From'] = GMAIL_ADDRESS
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            text = msg.as_string()
            server.sendmail(GMAIL_ADDRESS, recipient_email, text)
        logger.info(f"Successfully sent daily report email to {recipient_email}")
    except Exception as e:
        logger.exception(f"Failed to send daily report email: {e}")


def send_daily_whatsapp(summary: dict, recipient_phone: str) -> None:
    """
    Sends daily summary via WhatsApp using Twilio
    """
    if not twilio_client or not TWILIO_WHATSAPP_NUMBER:
        logger.warning("Twilio not configured — skipping WhatsApp message")
        return
    
    # Build message body
    body = f"📊 Daily Business Report - {summary['date']}\n"
    body += "--------------------------------\n"
    body += f"Total Profit Today: Rs {summary['total_profit_today']:,.2f}\n\n"
    
    if summary['top_selling_items']:
        body += "🏆 Top Selling Items:\n"
        for i, item in enumerate(summary['top_selling_items'][:5], 1):
            body += f"{i}. {item['product']}: {item['units_sold']} units, Rs {item['revenue']:,.2f}\n"
        body += "\n"
    
    if summary['restocked_items_today']:
        body += "📦 Restocked Items:\n"
        for item in summary['restocked_items_today']:
            body += f"- {item['product']}: {item['qty']} units\n"
    else:
        body += "📦 No items restocked today.\n"
    
    try:
        message = twilio_client.messages.create(
            from_=f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
            body=body,
            to=f"whatsapp:{recipient_phone}"
        )
        logger.info(f"Successfully sent daily WhatsApp report to {recipient_phone}: SID {message.sid}")
    except Exception as e:
        logger.exception(f"Failed to send daily WhatsApp report: {e}")


def get_all_insights(user_id: int):
    sales, inventory = load_data(user_id)
    insufficient_data = sales.empty or sales["date"].dt.date.nunique() < 15
    
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
    result["insufficient_data"] = insufficient_data
    return to_native(result)


# ─────────────────────────────────────────────────────────────────────────────
# AI ACTION PLANNER
# Converts Root Cause Engine output into a prioritised daily task checklist.
# ─────────────────────────────────────────────────────────────────────────────

import hashlib


def _task_id_from_cause(cause: dict) -> str:
    """
    Derive a stable, collision-resistant task_id from the cause's product +
    cause_type pair so the same underlying issue maps to the same row in
    task_status across requests.
    """
    raw = f"{cause['product']}|{cause['cause_type']}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _priority_tier(severity: str, financial_impact: float) -> str:
    """
    Map severity (from _create_root_cause) + financial_impact to a 4-level
    priority tier.  Uses deterministic rules — no new scale invented.

    Critical severity   → Urgent
    High severity       → High
    Medium + impact≥500 → High  (elevated because meaningful rupee risk)
    Medium              → Medium
    Low                 → Low
    """
    sev = severity.lower()
    if sev == "critical":
        return "Urgent"
    if sev == "high":
        return "High"
    if sev == "medium" and financial_impact >= 500:
        return "High"
    if sev == "medium":
        return "Medium"
    return "Low"


_TIER_ORDER = {"Urgent": 0, "High": 1, "Medium": 2, "Low": 3}


def _task_heuristics(cause: dict) -> tuple[str, str]:
    """
    Return (estimated_time, difficulty) using a simple keyword heuristic on
    cause_type.  Clearly labelled as estimates so users understand these are
    rough guides, not measured figures.
    """
    ct = cause.get("cause_type", "").lower()
    if "reorder" in ct or "stock" in ct:
        return "~5 min (est.)", "Easy"
    if "stop" in ct or "liquidat" in ct or "dead" in ct:
        return "~10 min (est.)", "Easy"
    if "margin" in ct or "pricing" in ct or "cost" in ct:
        return "~20 min (est.)", "Medium"
    if "sales_drop" in ct or "investigate" in ct:
        return "~15 min (est.)", "Medium"
    return "~10 min (est.)", "Medium"


def _action_title(cause: dict) -> str:
    """
    Convert a cause into an action-oriented task title.
    Follows pattern: <Verb> + <Product>   e.g. 'Reorder Cooking Oil' not
    'Cooking oil is low'.
    """
    ct = cause.get("cause_type", "").lower()
    product = cause.get("product", "Unknown")
    if "reorder" in ct:
        return f"Reorder {product}"
    if "stop" in ct or "dead" in ct:
        return f"Liquidate dead stock: {product}"
    if "margin" in ct or "pricing" in ct:
        return f"Review pricing for {product}"
    if "sales_drop" in ct:
        return f"Investigate sales drop: {product}"
    if "cost" in ct:
        return f"Audit costs for {product}"
    # Fallback: use the original title if cause_type doesn't match patterns
    return cause.get("title", f"Action: {product}")


def _expected_benefit(cause: dict) -> str:
    """
    Derive a short benefit phrase from the existing explanation field —
    nothing is fabricated.
    """
    explanation = cause.get("explanation", "")
    recovery = cause.get("expected_recovery", 0)
    if recovery > 0:
        return f"Recover up to ₹{recovery:,.0f} — {explanation[:120].rstrip('.')}."
    return explanation[:140].rstrip('.') + '.' if explanation else "Resolve identified issue."


def generate_action_plan(user_id: str, authenticated_supabase_client) -> dict:
    """
    Converts Root Cause Engine output into a prioritised daily task checklist.

    Steps:
    1. Call calculate_root_causes() — no logic duplicated.
    2. Map each cause → task with action-oriented title, priority tier,
       financial figures (reused verbatim), heuristic time/difficulty, and
       a benefit phrase derived from the existing explanation.
    3. Sort by priority tier then financial_impact desc.
    4. Load persisted task_status from Supabase for this user.
    5. Split tasks into pending / completed.
    6. total_potential_savings = sum of financial figures for pending tasks only.
    """
    root_cause_result = calculate_root_causes(user_id, authenticated_supabase_client)

    # Propagate insufficient-data state immediately
    if root_cause_result.get("insufficient_data"):
        return {
            "insufficient_data": True,
            "data_sufficiency_note": root_cause_result.get("data_sufficiency_note", ""),
            "pending": [],
            "completed": [],
            "total_potential_savings": 0.0,
        }

    causes = root_cause_result.get("causes", [])

    # ── Build raw task list ────────────────────────────────────────────────
    tasks = []
    for cause in causes:
        task_id = _task_id_from_cause(cause)
        priority = _priority_tier(cause["severity"], cause["financial_impact"])
        estimated_time, difficulty = _task_heuristics(cause)

        # Reuse cause financial figures verbatim — never recalculate
        profit_risk = cause["financial_impact"]
        expected_saving = cause["expected_recovery"]

        tasks.append({
            "task_id": task_id,
            "title": _action_title(cause),
            "priority": priority,
            "profit_risk": round(profit_risk, 2),
            "expected_saving": round(expected_saving, 2),
            "estimated_time": estimated_time,
            "difficulty": difficulty,
            "expected_benefit": _expected_benefit(cause),
            # Keep cause context for UI display
            "severity": cause["severity"],
            "confidence": cause["confidence"],
            "product": cause["product"],
            "cause_type": cause["cause_type"],
        })

    # ── Sort: tier first, then financial_impact desc within tier ──────────
    tasks.sort(
        key=lambda t: (_TIER_ORDER.get(t["priority"], 99), -t["profit_risk"])
    )

    # ── Fetch persisted completion status from Supabase ───────────────────
    completed_ids: set[str] = set()
    completed_at_map: dict[str, str] = {}
    try:
        resp = authenticated_supabase_client.table("task_status") \
            .select("task_id, status, completed_at") \
            .eq("user_id", str(user_id)) \
            .eq("status", "completed") \
            .execute()
        for row in (resp.data or []):
            completed_ids.add(row["task_id"])
            completed_at_map[row["task_id"]] = row.get("completed_at")
    except Exception as e:
        logger.warning(f"Could not load task_status for user {user_id}: {e}")
        # Degrade gracefully — treat all as pending

    # ── Split into pending / completed ────────────────────────────────────
    pending = []
    completed = []
    for t in tasks:
        if t["task_id"] in completed_ids:
            completed.append({**t, "completed_at": completed_at_map.get(t["task_id"])})
        else:
            pending.append(t)

    total_potential_savings = round(
        sum(t["expected_saving"] for t in pending), 2
    )

    return {
        "insufficient_data": False,
        "data_sufficiency_note": None,
        "pending": pending,
        "completed": completed,
        "total_potential_savings": total_potential_savings,
    }


if __name__ == "__main__":
    import json
    insights = get_all_insights(user_id=1)
    print(json.dumps(insights, indent=2, default=str))