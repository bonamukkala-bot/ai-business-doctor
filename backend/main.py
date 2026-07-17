import logging
import os
import io
import json
import shutil
import datetime
from typing import List
import pandas as pd
import requests
from twilio.rest import Client
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import auth
from supabase_client import supabase, supabase_client_initialized, supabase_init_error

from analysis_engine import (
    get_all_insights,
    ask_question,
    to_native,
    get_executive_summary,
    get_advisor_panel,
    simulate_scenario,
    load_data,
    GROQ_API_KEY,
    GROQ_URL,
    GROQ_MODEL,
    get_daily_summary,
    send_daily_email,
    send_daily_whatsapp,
    calculate_root_causes,
    generate_action_plan,
    predict_cash_flow,
    get_inventory_optimizer,
)
from pdf_report import build_pdf_report

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_business_doctor")

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
twilio_client = None

if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        logger.info("Twilio client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Twilio client: {e}")
else:
    logger.warning("Twilio credentials not configured - WhatsApp features disabled")

app = FastAPI(
    title="AI Business Doctor API",
    description="Diagnostic engine that turns raw sales & inventory data into explained business recommendations.",
    version="1.0.0",
)

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if supabase_client_initialized:
    logger.info("Supabase client initialized successfully.")
else:
    logger.error(f"Supabase client initialization failed: {supabase_init_error}")

# Initialize scheduler
scheduler = BackgroundScheduler(timezone=pytz.timezone("Asia/Kolkata"))

def run_daily_report():
    """
    Scheduled job to run daily at 10 PM IST:
    Get daily summary and send email/WhatsApp to all users
    """
    logger.info("Running daily report job...")
    try:
        # Fetch all users from profiles table
        if not supabase_client_initialized:
            logger.error("Supabase not initialized — skipping daily report")
            return
        
        response = supabase.table("profiles").select("id, email, phone_number").execute()
        users = response.data
        if not users:
            logger.warning("No users found — skipping daily report")
            return
        
        for user in users:
            user_id = user["id"]
            user_email = user.get("email")
            user_phone = user.get("phone_number")
            
            logger.info(f"Processing daily report for user {user_id}")
            
            try:
                sales, inventory = load_data(user_id)
                summary = get_daily_summary(sales, inventory)
                
                # Send email if we have email
                if user_email:
                    send_daily_email(summary, user_email)
                
                # Send WhatsApp if we have phone number
                if user_phone:
                    send_daily_whatsapp(summary, user_phone)
            
            except Exception as e:
                logger.exception(f"Failed to process daily report for user {user_id}: {e}")
        
        logger.info("Daily report job complete!")
    
    except Exception as e:
        logger.exception(f"Daily report job failed: {e}")


# ---------- FastAPI Startup/Shutdown Events ----------
@app.on_event("startup")
def start_scheduler():
    # Add daily job at 10 PM IST (Asia/Kolkata)
    scheduler.add_job(
        run_daily_report,
        trigger=CronTrigger(hour=22, minute=0, timezone=pytz.timezone("Asia/Kolkata")),
        id="daily_report_job",
        name="Daily Business Report",
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler started — daily report scheduled for 10 PM IST")


@app.on_event("shutdown")
def stop_scheduler():
    scheduler.shutdown()
    logger.info("Scheduler stopped")


# ---------- Authentication Schemas ----------

class CompleteProfileRequest(BaseModel):
    shop_name: str
    business_type: str | None = None

class UserResponse(BaseModel):
    id: str
    email: str
    shop_name: str | None = None
    business_type: str | None = None

    class Config:
        from_attributes = True


# ---------- Response Schemas ----------

class ProfitDriver(BaseModel):
    product: str
    profit_change: float
    pct_change: float
    reasoning: str


class ProfitAnalysis(BaseModel):
    total_profit_change: float
    summary: str
    top_drivers: List[ProfitDriver]
    insufficient_data: bool | None = None


class StopSellingItem(BaseModel):
    product: str
    avg_daily_units: float
    total_profit_90days: float
    current_stock: int
    reasoning: str


class ReorderItem(BaseModel):
    product: str
    current_stock: int
    daily_avg_demand: float
    days_of_stock_left: float
    recommended_reorder_qty: int
    reasoning: str


class ProfitTrendPoint(BaseModel):
    date: str
    profit: float


class RawSummaryItem(BaseModel):
    product: str
    total_units: int
    total_revenue: float
    total_profit: float
    current_stock: int


class PriorityAction(BaseModel):
    category: str
    product: str
    impact_rupees: float
    reasoning: str
    recommended_action: str
    priority_score: float
    rank: int
    urgency_label: str


class AnomalyAlert(BaseModel):
    type: str
    product: str
    severity: str
    message: str


class HealthScore(BaseModel):
    score: float
    label: str
    breakdown: List[str]
    insufficient_data: bool | None = None


class ExecutiveSummaryLegacy(BaseModel):
    summary: str
    generated_by: str
    context: dict
    insufficient_data: bool | None = None


class ExecutiveSummaryResponse(BaseModel):
    narrative: str
    health_score: float
    health_label: str
    profit_forecast_next_15_days: float
    top_risk: str
    top_opportunity: str
    generated_by: str = "fallback"
    insufficient_data: bool | None = None


class InsightsResponse(BaseModel):
    profit_analysis: ProfitAnalysis
    stop_selling: List[StopSellingItem]
    reorder: List[ReorderItem]
    profit_trend: List[ProfitTrendPoint]
    raw_summary: List[RawSummaryItem]
    priority_actions: List[PriorityAction]
    anomaly_alerts: List[AnomalyAlert]
    health_score: HealthScore
    executive_summary: ExecutiveSummaryLegacy
    insufficient_data: bool | None = None


class HealthResponse(BaseModel):
    status: str
    service: str


class AskRequest(BaseModel):
    question: str
    session_id: str | None = None


class AskResponse(BaseModel):
    intent: str
    answer: str
    data: dict | list | None = None


class SimulateRequest(BaseModel):
    product: str
    demand_change_pct: float = Field(ge=-50, le=100)


class SimulateResponse(BaseModel):
    product: str
    demand_change_pct: float
    baseline_days_of_stock_left: float
    projected_days_of_stock_left: float
    projected_profit_impact: float
    recommended_action: str


class RootCause(BaseModel):
    title: str
    explanation: str
    financial_impact: float
    severity: str
    confidence: float
    recommended_action: str
    expected_recovery: float
    product: str
    cause_type: str

class RootCauseAnalysisResponse(BaseModel):
    period_compared: dict
    causes: List[RootCause]
    data_sufficiency_note: str | None = None
    insufficient_data: bool = False

# ── Action Planner models ─────────────────────────────────────────────────────

class ActionTask(BaseModel):
    task_id: str
    title: str
    priority: str
    profit_risk: float
    expected_saving: float
    estimated_time: str
    difficulty: str
    expected_benefit: str
    severity: str
    confidence: float
    product: str
    cause_type: str
    completed_at: str | None = None

class ActionPlanResponse(BaseModel):
    insufficient_data: bool = False
    data_sufficiency_note: str | None = None
    pending: List[ActionTask]
    completed: List[ActionTask]
    total_potential_savings: float

# ── Cash Flow Predictor models ────────────────────────────────────────────────

class CashFlowProjection(BaseModel):
    day: int
    label: str
    projected_cash: float
    risk_level: str

class CashFlowChartPoint(BaseModel):
    day: int
    label: str
    projected_cash: float

class CashFlowRecommendation(BaseModel):
    title: str
    explanation: str
    financial_impact: float
    impact_basis: str

class CashFlowResponse(BaseModel):
    insufficient_data: bool = False
    data_sufficiency_note: str | None = None
    current_cash_position: float | None = None
    is_estimate: bool = True
    position_basis: str | None = None
    projections: List[CashFlowProjection]
    chart_series: List[CashFlowChartPoint] = []
    daily_avg_net_cash: float | None = None
    trend_direction: str | None = None
    trend_slope_per_day: float | None = None
    trailing_days: int | None = None
    confidence: float | None = None
    recommendations: List[CashFlowRecommendation]

# ── Inventory Optimizer models ────────────────────────────────────────────────

class InventoryOptimizerItem(BaseModel):
    product: str
    current_stock: int
    daily_avg_demand: float
    stock_coverage_days: float
    expected_demand: float
    safety_stock: float | None = None
    safety_stock_note: str | None = None
    recommended_purchase_qty: int
    unit_cost: float
    estimated_cost: float
    estimated_savings: float
    explanation: str

class InventoryOptimizerResponse(BaseModel):
    insufficient_data: bool = False
    data_sufficiency_note: str | None = None
    items: List[InventoryOptimizerItem]
    total_recommended_spend: float
    total_estimated_savings: float
    trailing_days: int | None = None
    coverage_target_days: int | None = None
    safety_factor: float | None = None

class AdvisorPanelResponse(BaseModel):
    finance_take: str
    operations_take: str
    marketing_take: str


class DataStatusResponse(BaseModel):
    source: str
    sales_path: str | None = None
    inventory_path: str | None = None
    last_modified: str | None = None
    days: int
    products: int
    date_range: str
    days_of_history_captured: int | None = None


class UploadSuccessResponse(BaseModel):
    status: str
    message: str
    summary: DataStatusResponse


def get_user_dir(user_id: int) -> str:
    user_dir = os.path.join(os.path.dirname(__file__), "user_data", str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

def get_config(user_id: int) -> dict:
    user_dir = get_user_dir(user_id)
    config_file = os.path.join(user_dir, "data_source_config.json")
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "mode": "demo",
        "sales_path": None,
        "inventory_path": None,
        "uploaded_sales_path": None,
        "uploaded_inventory_path": None
    }

def save_config(user_id: int, config: dict):
    user_dir = get_user_dir(user_id)
    config_file = os.path.join(user_dir, "data_source_config.json")
    try:
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save config for user {user_id}: {e}")

def compute_summary(sales_df: pd.DataFrame, inventory_df: pd.DataFrame) -> dict:
    try:
        if sales_df.empty or inventory_df.empty:
            return {
                "days": 0,
                "products": 0,
                "date_range": "No data"
            }
        
        sales_df["parsed_date"] = pd.to_datetime(sales_df["date"])
        min_date = sales_df["parsed_date"].min()
        max_date = sales_df["parsed_date"].max()
        
        days = sales_df["parsed_date"].dt.date.nunique()
        products = sales_df["product"].nunique()
        
        if pd.isna(min_date) or pd.isna(max_date):
            date_range = "N/A"
        else:
            date_range = f"{min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}"
            
        return {
            "days": int(days),
            "products": int(products),
            "date_range": date_range
        }
    except Exception as e:
        logger.error(f"Failed to compute summary: {e}")
        return {
            "days": 0,
            "products": 0,
            "date_range": "Unknown"
        }

def read_upload_file(file: UploadFile, content: bytes) -> pd.DataFrame:
    filename = file.filename or ""
    if filename.lower().endswith(('.xlsx', '.xls')):
        return pd.read_excel(io.BytesIO(content), engine='openpyxl')
    else:
        return pd.read_csv(io.BytesIO(content))

def read_path_file(path: str) -> pd.DataFrame:
    if path.lower().endswith(('.xlsx', '.xls')):
        return pd.read_excel(path, engine='openpyxl')
    else:
        return pd.read_csv(path)

def validate_dfs(sales_df: pd.DataFrame, inventory_df: pd.DataFrame, source_label: str = "File"):
    # Validate Sales columns
    required_sales_cols = ["date", "product", "units_sold", "revenue", "profit"]
    found_sales_cols = list(sales_df.columns)
    missing_sales_cols = [col for col in required_sales_cols if col not in found_sales_cols]
    if missing_sales_cols:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Sales {source_label.lower()} is missing required columns.",
                "missing": missing_sales_cols,
                "found": found_sales_cols
            }
        )

    # Validate Inventory columns
    required_inventory_cols = ["product", "current_stock", "unit_cost"]
    found_inventory_cols = list(inventory_df.columns)
    missing_inventory_cols = [col for col in required_inventory_cols if col not in found_inventory_cols]
    if missing_inventory_cols:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Inventory {source_label.lower()} is missing required columns.",
                "missing": missing_inventory_cols,
                "found": found_inventory_cols
            }
        )

    # Validate date column format
    try:
        sales_df["parsed_date"] = pd.to_datetime(sales_df["date"], errors="raise")
    except Exception:
        raise HTTPException(
            status_code=400,
            detail=f"The 'date' column in the Sales {source_label.lower()} contains invalid date values. Please ensure all dates are in YYYY-MM-DD format (or similar parseable formats)."
        )

    # Validate numeric columns
    for col in ["units_sold", "revenue", "profit"]:
        try:
            pd.to_numeric(sales_df[col], errors="raise")
        except Exception:
            raise HTTPException(
                status_code=400,
                detail=f"The '{col}' column in the Sales {source_label.lower()} contains non-numeric values. All values in this column must be numeric."
            )

    for col in ["current_stock", "unit_cost"]:
        try:
            pd.to_numeric(inventory_df[col], errors="raise")
        except Exception:
            raise HTTPException(
                status_code=400,
                detail=f"The '{col}' column in the Inventory {source_label.lower()} contains non-numeric values. All values in this column must be numeric."
            )


SESSION_HISTORY: dict[str, list] = {}
MAX_HISTORY_PER_SESSION = 6


# ---------- Routes ----------

@app.post("/auth/complete-profile", response_model=UserResponse)
def complete_profile(
    request: CompleteProfileRequest,
    current_user: auth.AuthenticatedSupabaseUser = Depends(auth.get_current_user),
):
    try:
        current_user.supabase.table('profiles').upsert({
            'id': current_user.id,
            'shop_name': request.shop_name,
            'business_type': request.business_type,
        }).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Failed to save profile to Supabase: {exc}')

    return {
        'id': current_user.id,
        'email': current_user.email,
        'shop_name': request.shop_name,
        'business_type': request.business_type,
    }


@app.get('/auth/me', response_model=UserResponse)
def get_me(
    current_user: auth.AuthenticatedSupabaseUser = Depends(auth.get_current_user),
):
    try:
        result = current_user.supabase.table('profiles').select('shop_name,business_type').eq('id', current_user.id).maybe_single().execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Failed to fetch profile from Supabase: {exc}')

    profile = result.data or {}
    return {
        'id': current_user.id,
        'email': current_user.email,
        'shop_name': profile.get('shop_name'),
        'business_type': profile.get('business_type'),
    }


@app.get("/", response_model=HealthResponse)
def root():
    """Basic health check to confirm the API is up."""
    return {"status": "ok", "service": "AI Business Doctor API"}


@app.get("/supabase-health")
def supabase_health():
    """Verifies the Supabase client can connect and authenticate."""
    if supabase is None:
        return {"status": "disconnected", "detail": str(supabase_init_error) if supabase_init_error else "Supabase client not initialized."}

    try:
        response = supabase.table("_healthcheck").select("*").limit(1).execute()
        return {"status": "connected", "detail": "ok"}
    except Exception as exc:
        return {"status": "connected", "detail": str(exc)}


@app.get("/data-status", response_model=DataStatusResponse)
def data_status(current_user: auth.SupabaseUser = Depends(auth.get_current_user)):
    try:
        user_dir = get_user_dir(current_user.id)
        config = get_config(current_user.id)
        mode = config.get("mode", "demo")
        
        # Default user-scoped paths
        sales_path = os.path.join(user_dir, "sales_data.csv")
        inventory_path = os.path.join(user_dir, "inventory_data.csv")
        
        if mode == "uploaded":
            sales_path = config.get("sales_path") or os.path.join(user_dir, "sales_data.csv")
            inventory_path = config.get("inventory_path") or os.path.join(user_dir, "inventory_data.csv")
        elif mode == "live":
            sales_path = config.get("sales_path")
            inventory_path = config.get("inventory_path")

        # Fallbacks if files don't exist
        if not sales_path or not os.path.exists(sales_path):
            sales_path = os.path.join(user_dir, "sales_data.csv")
        if not inventory_path or not os.path.exists(inventory_path):
            inventory_path = os.path.join(user_dir, "inventory_data.csv")

        # If STILL don't exist, fall back to global demo
        if not os.path.exists(sales_path):
            sales_path = os.path.join(os.path.dirname(__file__), "demo_sales_data.csv")
        if not os.path.exists(inventory_path):
            inventory_path = os.path.join(os.path.dirname(__file__), "demo_inventory_data.csv")

        sales, inventory = load_data(current_user.id)
        summary = compute_summary(sales, inventory)

        sales_mtime = os.path.getmtime(sales_path) if os.path.exists(sales_path) else 0
        inventory_mtime = os.path.getmtime(inventory_path) if os.path.exists(inventory_path) else 0
        max_mtime = max(sales_mtime, inventory_mtime)
        last_modified = datetime.datetime.fromtimestamp(max_mtime, datetime.timezone.utc).isoformat() if max_mtime > 0 else None

        try:
            days_of_history_captured = int(sales["date"].dt.date.nunique())
        except Exception:
            days_of_history_captured = 0

        return {
            "source": mode,
            "sales_path": config.get("sales_path") if mode == "live" else None,
            "inventory_path": config.get("inventory_path") if mode == "live" else None,
            "last_modified": last_modified,
            "days": summary["days"],
            "products": summary["products"],
            "date_range": summary["date_range"],
            "days_of_history_captured": days_of_history_captured
        }
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Business data files not found. Run create_dataset.py before starting the API."
        )
    except Exception as e:
        logger.exception("Failed to get data status")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check data status: {str(e)}"
        )


@app.post("/upload-data", response_model=UploadSuccessResponse)
async def upload_data(
    sales_file: UploadFile = File(...),
    inventory_file: UploadFile = File(...),
    current_user: auth.SupabaseUser = Depends(auth.get_current_user)
):
    user_dir = get_user_dir(current_user.id)
    try:
        sales_content = await sales_file.read()
        sales_df = read_upload_file(sales_file, sales_content)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse Sales file: {str(e)}"
        )

    try:
        inventory_content = await inventory_file.read()
        inventory_df = read_upload_file(inventory_file, inventory_content)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse Inventory file: {str(e)}"
        )

    validate_dfs(sales_df, inventory_df, source_label="Uploaded CSV/Excel")

    sales_ext = ".xlsx" if sales_file.filename.lower().endswith(('.xlsx', '.xls')) else ".csv"
    inventory_ext = ".xlsx" if inventory_file.filename.lower().endswith(('.xlsx', '.xls')) else ".csv"
    
    sales_path = os.path.join(user_dir, f"sales_data{sales_ext}")
    inventory_path = os.path.join(user_dir, f"inventory_data{inventory_ext}")

    for ext in [".csv", ".xlsx"]:
        other_sales = os.path.join(user_dir, f"sales_data{ext}")
        other_inv = os.path.join(user_dir, f"inventory_data{ext}")
        if other_sales != sales_path and os.path.exists(other_sales):
            try:
                os.remove(other_sales)
            except Exception:
                pass
        if other_inv != inventory_path and os.path.exists(other_inv):
            try:
                os.remove(other_inv)
            except Exception:
                pass

    try:
        if sales_ext == ".xlsx":
            sales_df.drop(columns=["parsed_date"]).to_excel(sales_path, index=False, engine='openpyxl')
        else:
            sales_df.drop(columns=["parsed_date"]).to_csv(sales_path, index=False)

        if inventory_ext == ".xlsx":
            inventory_df.to_excel(inventory_path, index=False, engine='openpyxl')
        else:
            inventory_df.to_csv(inventory_path, index=False)
    except Exception as e:
        logger.exception("Failed to write uploaded files to disk")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save uploaded files: {str(e)}"
        )

    config = get_config(current_user.id)
    config["mode"] = "uploaded"
    config["sales_path"] = sales_path
    config["inventory_path"] = inventory_path
    config["uploaded_sales_path"] = sales_path
    config["uploaded_inventory_path"] = inventory_path
    save_config(current_user.id, config)

    sales, inventory = load_data(current_user.id)
    summary = compute_summary(sales, inventory)

    sales_mtime = os.path.getmtime(sales_path) if os.path.exists(sales_path) else 0
    inventory_mtime = os.path.getmtime(inventory_path) if os.path.exists(inventory_path) else 0
    max_mtime = max(sales_mtime, inventory_mtime)
    last_modified = datetime.datetime.fromtimestamp(max_mtime, datetime.timezone.utc).isoformat() if max_mtime > 0 else None

    return {
        "status": "success",
        "message": "Data uploaded and validated successfully.",
        "summary": {
            "source": "uploaded",
            "sales_path": sales_path,
            "inventory_path": inventory_path,
            "last_modified": last_modified,
            "days": summary["days"],
            "products": summary["products"],
            "date_range": summary["date_range"]
        }
    }


@app.post("/reset-demo-data", response_model=UploadSuccessResponse)
def reset_demo_data(current_user: auth.SupabaseUser = Depends(auth.get_current_user)):
    user_dir = get_user_dir(current_user.id)
    try:
        config = {
            "mode": "demo",
            "sales_path": None,
            "inventory_path": None,
            "uploaded_sales_path": None,
            "uploaded_inventory_path": None
        }
        for filename in ["sales_data.csv", "sales_data.xlsx", "inventory_data.csv", "inventory_data.xlsx"]:
            path = os.path.join(user_dir, filename)
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

        # Re-seed the demo files in the user's directory
        demo_sales_src = os.path.join(os.path.dirname(__file__), "demo_sales_data.csv")
        demo_inventory_src = os.path.join(os.path.dirname(__file__), "demo_inventory_data.csv")
        shutil.copy(demo_sales_src, os.path.join(user_dir, "sales_data.csv"))
        shutil.copy(demo_inventory_src, os.path.join(user_dir, "inventory_data.csv"))

        save_config(current_user.id, config)
        sales, inventory = load_data(current_user.id)
        summary = compute_summary(sales, inventory)
        
        sales_path = os.path.join(user_dir, "sales_data.csv")
        inventory_path = os.path.join(user_dir, "inventory_data.csv")
        sales_mtime = os.path.getmtime(sales_path) if os.path.exists(sales_path) else 0
        inventory_mtime = os.path.getmtime(inventory_path) if os.path.exists(inventory_path) else 0
        max_mtime = max(sales_mtime, inventory_mtime)
        last_modified = datetime.datetime.fromtimestamp(max_mtime, datetime.timezone.utc).isoformat() if max_mtime > 0 else None

        return {
            "status": "success",
            "message": "Demo data restored successfully.",
            "summary": {
                "source": "demo",
                "sales_path": None,
                "inventory_path": None,
                "last_modified": last_modified,
                "days": summary["days"],
                "products": summary["products"],
                "date_range": summary["date_range"]
            }
        }
    except Exception as e:
        logger.exception("Failed to reset demo data")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset demo data: {str(e)}"
        )


class ConnectLiveRequest(BaseModel):
    sales_path: str
    inventory_path: str


@app.post("/onboarding/complete", response_model=UploadSuccessResponse)
async def onboarding_complete(
    business_type: str = Form(...),
    shop_name: str = Form(...),
    source: str = Form(...),
    sales_file: UploadFile | None = File(None),
    manual_rows: str | None = Form(None),
    current_user: auth.SupabaseUser = Depends(auth.get_current_user),
):
    if supabase is None:
        raise HTTPException(status_code=500, detail='Supabase client not initialized.')

    user_dir = get_user_dir(current_user.id)
    try:
        config = get_config(current_user.id)

        if source == 'upload':
            if not sales_file:
                raise HTTPException(status_code=400, detail='Sales file is required for upload source.')
            sales_content = await sales_file.read()
            sales_df = read_upload_file(sales_file, sales_content)
            if not all(col in sales_df.columns for col in ['date', 'product', 'units_sold', 'revenue', 'profit']):
                raise HTTPException(status_code=400, detail='Uploaded sales file must include date, product, units_sold, revenue, and profit columns.')
            sales_path = os.path.join(user_dir, 'sales_data.csv')
            sales_df.to_csv(sales_path, index=False)
            config['mode'] = 'uploaded'
            config['sales_path'] = sales_path
            config['inventory_path'] = os.path.join(user_dir, 'inventory_data.csv')
            save_config(current_user.id, config)
        elif source == 'manual':
            if not manual_rows:
                raise HTTPException(status_code=400, detail='Manual rows are required for manual source.')
            rows = json.loads(manual_rows)
            if len(rows) < 5:
                raise HTTPException(status_code=400, detail='At least 5 manual rows are required.')
            sales_df = pd.DataFrame(rows)
            if not all(col in sales_df.columns for col in ['date', 'product', 'units_sold', 'revenue', 'profit']):
                raise HTTPException(status_code=400, detail='Manual rows must include date, product, units_sold, revenue, and profit.')
            sales_path = os.path.join(user_dir, 'sales_data.csv')
            sales_df.to_csv(sales_path, index=False)
            config['mode'] = 'uploaded'
            config['sales_path'] = sales_path
            config['inventory_path'] = os.path.join(user_dir, 'inventory_data.csv')
            save_config(current_user.id, config)
        else:
            config['mode'] = 'demo'
            config['sales_path'] = None
            config['inventory_path'] = None
            save_config(current_user.id, config)

        try:
            current_user.supabase.table('profiles').select('*').eq('id', current_user.id).maybe_single().execute()
            current_user.supabase.table('profiles').upsert({
                'id': current_user.id,
                'shop_name': shop_name,
                'business_type': business_type,
            }).execute()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f'Failed to save profile to Supabase: {exc}')

        sales, inventory = load_data(current_user.id)
        summary = compute_summary(sales, inventory)
        sales_path = config.get('sales_path')
        inventory_path = config.get('inventory_path')
        sales_mtime = os.path.getmtime(sales_path) if sales_path and os.path.exists(sales_path) else 0
        inventory_mtime = os.path.getmtime(inventory_path) if inventory_path and os.path.exists(inventory_path) else 0
        max_mtime = max(sales_mtime, inventory_mtime)
        last_modified = datetime.datetime.fromtimestamp(max_mtime, datetime.timezone.utc).isoformat() if max_mtime > 0 else None

        return {
            'status': 'success',
            'message': 'Onboarding complete. Your data is ready for diagnosis.',
            'summary': {
                'source': config['mode'],
                'sales_path': sales_path,
                'inventory_path': inventory_path,
                'last_modified': last_modified,
                'days': summary['days'],
                'products': summary['products'],
                'date_range': summary['date_range'],
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception('Failed to complete onboarding')
        raise HTTPException(status_code=500, detail=f'Failed to complete onboarding: {str(e)}')


@app.post("/connect-live-file", response_model=UploadSuccessResponse)
def connect_live_file(request: ConnectLiveRequest, current_user: auth.SupabaseUser = Depends(auth.get_current_user)):
    sales_path = request.sales_path.strip()
    inventory_path = request.inventory_path.strip()

    if not sales_path or not inventory_path:
        raise HTTPException(status_code=400, detail="Sales and inventory paths cannot be empty.")

    if not os.path.exists(sales_path):
        raise HTTPException(status_code=400, detail=f"Sales path does not exist on server: {sales_path}")
    if not os.path.exists(inventory_path):
        raise HTTPException(status_code=400, detail=f"Inventory path does not exist on server: {inventory_path}")

    try:
        sales_df = read_path_file(sales_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse Sales live file: {str(e)}")

    try:
        inventory_df = read_path_file(inventory_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse Inventory live file: {str(e)}")

    validate_dfs(sales_df, inventory_df, source_label="Live Excel/CSV File")

    config = get_config(current_user.id)
    config["mode"] = "live"
    config["sales_path"] = sales_path
    config["inventory_path"] = inventory_path
    save_config(current_user.id, config)

    sales, inventory = load_data(current_user.id)
    summary = compute_summary(sales, inventory)

    sales_mtime = os.path.getmtime(sales_path) if os.path.exists(sales_path) else 0
    inventory_mtime = os.path.getmtime(inventory_path) if os.path.exists(inventory_path) else 0
    max_mtime = max(sales_mtime, inventory_mtime)
    last_modified = datetime.datetime.fromtimestamp(max_mtime, datetime.timezone.utc).isoformat() if max_mtime > 0 else None

    return {
        "status": "success",
        "message": "Connected live files successfully.",
        "summary": {
            "source": "live",
            "sales_path": sales_path,
            "inventory_path": inventory_path,
            "last_modified": last_modified,
            "days": summary["days"],
            "products": summary["products"],
            "date_range": summary["date_range"]
        }
    }


@app.post("/disconnect-live-file", response_model=UploadSuccessResponse)
def disconnect_live_file(current_user: auth.SupabaseUser = Depends(auth.get_current_user)):
    try:
        user_dir = get_user_dir(current_user.id)
        config = get_config(current_user.id)
        uploaded_sales = config.get("uploaded_sales_path")
        uploaded_inventory = config.get("uploaded_inventory_path")

        if uploaded_sales and os.path.exists(uploaded_sales) and uploaded_inventory and os.path.exists(uploaded_inventory):
            config["mode"] = "uploaded"
            config["sales_path"] = uploaded_sales
            config["inventory_path"] = uploaded_inventory
            message = "Disconnected live file. Returned to uploaded dataset."
        else:
            config["mode"] = "demo"
            config["sales_path"] = None
            config["inventory_path"] = None
            message = "Disconnected live file. Restored default demo data."

        save_config(current_user.id, config)

        sales, inventory = load_data(current_user.id)
        summary = compute_summary(sales, inventory)

        active_sales = config.get("sales_path") or os.path.join(user_dir, "sales_data.csv")
        active_inv = config.get("inventory_path") or os.path.join(user_dir, "inventory_data.csv")
        
        if not os.path.exists(active_sales):
            active_sales = os.path.join(os.path.dirname(__file__), "demo_sales_data.csv")
        if not os.path.exists(active_inv):
            active_inv = os.path.join(os.path.dirname(__file__), "demo_inventory_data.csv")

        sales_mtime = os.path.getmtime(active_sales) if os.path.exists(active_sales) else 0
        inventory_mtime = os.path.getmtime(active_inv) if os.path.exists(active_inv) else 0
        max_mtime = max(sales_mtime, inventory_mtime)
        last_modified = datetime.datetime.fromtimestamp(max_mtime, datetime.timezone.utc).isoformat() if max_mtime > 0 else None

        return {
            "status": "success",
            "message": message,
            "summary": {
                "source": config["mode"],
                "sales_path": config["sales_path"],
                "inventory_path": config["inventory_path"],
                "last_modified": last_modified,
                "days": summary["days"],
                "products": summary["products"],
                "date_range": summary["date_range"]
            }
        }
    except Exception as e:
        logger.exception("Failed to disconnect live files")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to disconnect live files: {str(e)}"
        )


class UpdatePhoneRequest(BaseModel):
    phone_number: str


class UpdateBusinessGoalRequest(BaseModel):
    business_goal: str


class WhatsAppAlertRequest(BaseModel):
    user_id: str


class TranslationRequest(BaseModel):
    narrative: str
    language: str


@app.post("/api/translate-narrative")
def translate_narrative(request: TranslationRequest):
    """
    Translates the executive summary narrative to the specified language.
    Currently supports English, Telugu, and Hindi.
    """
    try:
        # For now, we'll use a simple translation approach
        # In production, this would use a proper translation service
        language_instructions = {
            'telugu': 'Write this business summary in Telugu, using simple everyday language a small shop owner would use, not formal business jargon.',
            'hindi': 'Write this business summary in Hindi, using simple everyday language a small shop owner would use, not formal business jargon.',
            'english': 'Keep this business summary in English.'
        }

        if request.language not in language_instructions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported language: {request.language}. Supported languages: english, telugu, hindi"
            )

        # If English, return as-is
        if request.language == 'english':
            return {
                "translated_narrative": request.narrative,
                "language": "english"
            }

        # For other languages, we would call Groq with translation instructions
        # For now, return placeholder (in production, this would call Groq)
        system_prompt = f"You are a business translator. {language_instructions[request.language]} Keep all numbers and currency figures as digits - only translate the narrative prose."

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
                        {"role": "user", "content": request.narrative},
                    ],
                    "temperature": 0.5,
                    "max_tokens": 350,
                },
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            translated = data["choices"][0]["message"]["content"].strip()

            return {
                "translated_narrative": translated,
                "language": request.language
            }
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            # Fallback to placeholder if translation fails
            placeholders = {
                'telugu': 'తెలుగు అనువాదం ఇక్కడ ఉంటుంది (Telugu translation would be here)',
                'hindi': 'हिंदी अनुवाद यहां होगा (Hindi translation would be here)'
            }
            return {
                "translated_narrative": placeholders.get(request.language, request.narrative),
                "language": request.language
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Translation error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Translation failed: {str(e)}"
        )


class WhatsAppAlertRequest(BaseModel):
    user_id: str


@app.get("/api/business-goal")
def get_business_goal_endpoint(current_user: auth.SupabaseUser = Depends(auth.get_current_user)):
    """
    Gets the current user's business goal from their profile.
    """
    try:
        response = current_user.supabase.table('profiles').select('business_goal').single().execute()
        return {
            "business_goal": response.data.get('business_goal')
        }
    except Exception as e:
        logger.exception(f"Failed to get business goal: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get business goal: {str(e)}"
        )


ALLOWED_BUSINESS_GOALS = {
    'increase_profit',
    'increase_revenue',
    'reduce_inventory',
    'improve_cash_flow',
    'reduce_waste',
    'prepare_expansion',
    'open_branch'
}


@app.post("/api/business-goal")
def update_business_goal(
    request: UpdateBusinessGoalRequest,
    current_user: auth.SupabaseUser = Depends(auth.get_current_user)
):
    """
    Updates or sets the user's business goal in their profile.
    """
    # Validate goal
    if request.business_goal not in ALLOWED_BUSINESS_GOALS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid business goal. Allowed values: {', '.join(sorted(ALLOWED_BUSINESS_GOALS))}"
        )

    try:
        current_user.supabase.table('profiles').upsert({
            'id': current_user.id,
            'business_goal': request.business_goal
        }).execute()

        return {
            "status": "success",
            "message": "Business goal updated successfully"
        }
    except Exception as e:
        logger.exception(f"Failed to update business goal: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update business goal: {str(e)}"
        )


@app.get("/api/root-cause-analysis", response_model=RootCauseAnalysisResponse)
def get_root_cause_analysis(current_user: auth.SupabaseUser = Depends(auth.get_current_user)):
    """
    Returns the AI root cause analysis: identifies performance issues,
    calculates financial impact, severity, confidence, and provides actionable recommendations.
    """
    try:
        result = calculate_root_causes(current_user.id, current_user.supabase)
        return to_native(result)
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Business data files not found. Run create_dataset.py before starting the API."
        )
    except Exception:
        logger.exception("Unexpected error while generating root cause analysis")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong generating the root cause analysis. Check server logs."
        )


# ── AI Action Planner endpoints ───────────────────────────────────────────────

@app.get("/api/action-plan", response_model=ActionPlanResponse)
def get_action_plan(current_user: auth.SupabaseUser = Depends(auth.get_current_user)):
    """
    Returns the current user's AI-generated action plan derived from the Root
    Cause Engine.  Tasks are split into pending / completed based on stored
    task_status, and total_potential_savings covers pending tasks only.
    """
    try:
        result = generate_action_plan(current_user.id, current_user.supabase)
        return to_native(result)
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Business data files not found. Upload your data before generating an action plan."
        )
    except Exception:
        logger.exception("Unexpected error generating action plan")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong generating the action plan. Check server logs."
        )


@app.post("/api/action-plan/{task_id}/complete")
def complete_action_task(
    task_id: str,
    current_user: auth.SupabaseUser = Depends(auth.get_current_user)
):
    """
    Marks a task as completed for the current user.
    Upserts into task_status (insert or update on conflict).
    """
    try:
        import datetime as _dt
        current_user.supabase.table("task_status").upsert({
            "user_id": str(current_user.id),
            "task_id": task_id,
            "status": "completed",
            "completed_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        }, on_conflict="user_id,task_id").execute()
        return {"status": "success", "task_id": task_id, "new_status": "completed"}
    except Exception:
        logger.exception(f"Failed to mark task {task_id} complete for user {current_user.id}")
        raise HTTPException(status_code=500, detail="Failed to mark task complete.")


@app.post("/api/action-plan/{task_id}/reopen")
def reopen_action_task(
    task_id: str,
    current_user: auth.SupabaseUser = Depends(auth.get_current_user)
):
    """
    Reverses a completed task back to pending — handles mis-clicks.
    Upserts the row with status='pending' and clears completed_at.
    """
    try:
        current_user.supabase.table("task_status").upsert({
            "user_id": str(current_user.id),
            "task_id": task_id,
            "status": "pending",
            "completed_at": None,
        }, on_conflict="user_id,task_id").execute()
        return {"status": "success", "task_id": task_id, "new_status": "pending"}
    except Exception:
        logger.exception(f"Failed to reopen task {task_id} for user {current_user.id}")
        raise HTTPException(status_code=500, detail="Failed to reopen task.")


# ── Cash Flow Predictor endpoint ──────────────────────────────────────────────

@app.get("/api/cash-flow-prediction", response_model=CashFlowResponse)
def get_cash_flow_prediction(current_user: auth.SupabaseUser = Depends(auth.get_current_user)):
    """
    Returns the AI Cash Flow Predictor result for the current user.

    Projects cash position at +7, +15, +30 days using a linear trend fit
    on trailing daily net cash (revenue - cost of goods). current_cash_position
    is always a cash-basis estimate derived from sales data — not a bank balance.
    See `position_basis` field for the exact derivation.
    """
    try:
        result = predict_cash_flow(current_user.id, current_user.supabase)
        return to_native(result)
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Business data files not found. Upload your data before generating a cash flow prediction."
        )
    except Exception:
        logger.exception("Unexpected error generating cash flow prediction")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong generating the cash flow prediction. Check server logs."
        )


# ── Inventory Optimizer endpoint ──────────────────────────────────────────────

@app.get("/api/inventory-optimizer", response_model=InventoryOptimizerResponse)
def get_inventory_optimizer_endpoint(
    current_user: auth.SupabaseUser = Depends(auth.get_current_user)
):
    """
    Returns per-product inventory optimization data: expected demand,
    safety stock (based on real demand variability), coverage days,
    recommended purchase quantity, estimated cost, and estimated savings
    from avoiding stockouts.

    Does NOT modify recommend_reorder() — that function and the /insights
    endpoint remain unchanged. This endpoint enriches the data with
    additional per-product calculations.
    """
    try:
        result = get_inventory_optimizer(current_user.id, current_user.supabase)
        return to_native(result)
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Business data files not found. Upload your data before running inventory optimization."
        )
    except Exception:
        logger.exception("Unexpected error running inventory optimizer")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong running the inventory optimizer. Check server logs."
        )


@app.post("/api/user/update-phone")
def update_phone_number(
    request: UpdatePhoneRequest,
    current_user: auth.SupabaseUser = Depends(auth.get_current_user)
):
    """
    Updates the user's phone number in their Supabase profile.
    """
    try:
        current_user.supabase.table('profiles').upsert({
            'id': current_user.id,
            'phone_number': request.phone_number
        }).execute()

        return {
            "status": "success",
            "message": "Phone number updated successfully"
        }
    except Exception as e:
        logger.exception(f"Failed to update phone number: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update phone number: {str(e)}"
        )


@app.post("/api/alerts/send-whatsapp")
def send_whatsapp_alert(
    request: WhatsAppAlertRequest,
    current_user: auth.SupabaseUser = Depends(auth.get_current_user)
):
    """
    Sends a WhatsApp message with current health score and top reorder items.
    Requires Twilio credentials to be configured.
    """
    if not twilio_client or not TWILIO_WHATSAPP_NUMBER:
        raise HTTPException(
            status_code=503,
            detail="WhatsApp service not configured. Please set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_WHATSAPP_NUMBER environment variables."
        )

    try:
        # Get user's phone number from Supabase profile
        profile_result = current_user.supabase.table('profiles').select('phone_number').eq('id', current_user.id).maybe_single().execute()
        user_phone = profile_result.data.get('phone_number') if profile_result.data else None

        if not user_phone:
            raise HTTPException(
                status_code=400,
                detail="No phone number found in your profile. Please add your phone number in settings."
            )

        # Get current insights
        insights = get_all_insights(current_user.id)
        health_score = insights.get('health_score', {})
        reorder_items = insights.get('reorder', [])

        # Format phone number for WhatsApp (ensure it has country code)
        if not user_phone.startswith('+'):
            user_phone = '+91' + user_phone  # Default to India country code

        # Build message
        score = health_score.get('score', 0)
        label = health_score.get('label', 'Unknown')
        
        # Get top 3 urgent reorder items
        urgent_reorders = sorted(reorder_items, key=lambda x: x.get('days_of_stock_left', 999))[:3]
        reorder_text = ', '.join([
            f"{item['product']} ({item['days_of_stock_left']:.1f} days left)" 
            for item in urgent_reorders
        ]) if urgent_reorders else 'No urgent reorders'

        # Get profit trend
        profit_analysis = insights.get('profit_analysis', {})
        profit_change = profit_analysis.get('total_profit_change', 0)
        profit_trend = "up" if profit_change >= 0 else "down"
        profit_pct = abs(profit_change)

        message = (
            f"📊 Business Health: {score}/100 ({label})\n"
            f"⚠️ Reorder soon: {reorder_text}\n"
            f"💰 This week's profit trend: {profit_trend} {profit_pct:.0f}% vs last week"
        )

        # Send WhatsApp message
        message_obj = twilio_client.messages.create(
            body=message,
            from_=f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
            to=f"whatsapp:{user_phone}"
        )

        logger.info(f"WhatsApp message sent to user {current_user.id}: {message_obj.sid}")

        return {
            "status": "success",
            "message": "WhatsApp alert sent successfully",
            "message_sid": message_obj.sid
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to send WhatsApp alert: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send WhatsApp alert: {str(e)}"
        )




@app.get("/insights", response_model=InsightsResponse)
def insights(current_user: auth.SupabaseUser = Depends(auth.get_current_user)):
    """
    Runs the full diagnostic: profit driver analysis, stop-selling
    candidates, urgent reorder recommendations, a merged priority action
    list ranked by real rupee impact, business health score, and the
    board-meeting-style executive summary.
    """
    try:
        result = get_all_insights(current_user.id)
        return result
    except FileNotFoundError as e:
        logger.error(f"Data file missing: {e}")
        raise HTTPException(
            status_code=503,
            detail="Business data files not found. Run create_dataset.py before starting the API."
        )
    except Exception:
        logger.exception("Unexpected error while generating insights")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong generating the diagnostic report. Check server logs."
        )


@app.get("/executive-summary", response_model=ExecutiveSummaryResponse)
def executive_summary(current_user: auth.SupabaseUser = Depends(auth.get_current_user)):
    """
    Returns the board-meeting opening narrative with structured fields —
    health score, forecast, top risk/opportunity, and LLM-written prose.
    """
    try:
        sales, inventory = load_data(current_user.id)
        config = get_config(current_user.id)
        result = get_executive_summary(sales, inventory, config.get("mode", "demo"))
        return to_native({
            "narrative": result["narrative"],
            "health_score": result["health_score"],
            "health_label": result["health_label"],
            "profit_forecast_next_15_days": result["profit_forecast_next_15_days"],
            "top_risk": result["top_risk"],
            "top_opportunity": result["top_opportunity"],
            "generated_by": result["generated_by"],
        })
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Business data files not found. Run create_dataset.py before starting the API."
        )
    except Exception:
        logger.exception("Unexpected error while generating executive summary")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong generating the executive summary. Check server logs."
        )


@app.get("/export-report")
def export_report(current_user: auth.SupabaseUser = Depends(auth.get_current_user)):
    """
    Generates a formatted PDF version of the current diagnostic report —
    vitals, priority actions, alerts, and full breakdown — so the owner
    can download, print, or share it with a partner or supplier.
    """
    try:
        insights = get_all_insights(current_user.id)
        pdf_buffer = build_pdf_report(insights)
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=business_diagnosis_report.pdf"}
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Business data files not found. Run create_dataset.py before starting the API."
        )
    except Exception:
        logger.exception("Unexpected error while generating PDF report")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong generating the PDF report. Check server logs."
        )


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest, current_user: auth.SupabaseUser = Depends(auth.get_current_user)):
    """
    Accepts a natural-language business question and routes it to the
    relevant diagnostic, returning a conversational answer backed by
    real computed data. If a session_id is provided, recent conversation
    history for that session is used to ground follow-up questions.
    """
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    session_id = request.session_id
    history = SESSION_HISTORY.get(session_id, []) if session_id else []

    try:
        result = ask_question(request.question, history=history, user_id=current_user.id)
        result = to_native(result)

        if session_id:
            history.append({"question": request.question, "answer": result["answer"]})
            SESSION_HISTORY[session_id] = history[-MAX_HISTORY_PER_SESSION:]

        return result
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Business data files not found. Run create_dataset.py before starting the API."
        )
    except Exception:
        logger.exception("Unexpected error while answering question")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong answering that question. Check server logs."
        )


@app.post("/simulate", response_model=SimulateResponse)
def simulate(request: SimulateRequest, current_user: auth.SupabaseUser = Depends(auth.get_current_user)):
    """
    What-if scenario: adjusts a product's demand by a percentage and
    returns recalculated stock runway and profit impact.
    """
    if not request.product or not request.product.strip():
        raise HTTPException(status_code=400, detail="Product name cannot be empty.")

    try:
        result = simulate_scenario(request.product.strip(), request.demand_change_pct, user_id=current_user.id)
        return to_native(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Business data files not found. Run create_dataset.py before starting the API."
        )
    except Exception:
        logger.exception("Unexpected error during simulation")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong running the simulation. Check server logs."
        )


@app.post("/advisor-panel", response_model=AdvisorPanelResponse)
def advisor_panel(current_user: auth.SupabaseUser = Depends(auth.get_current_user)):
    """
    Runs three concurrent Groq calls — Finance, Operations, and Marketing
    advisors — each giving a grounded take on the current business data.
    """
    try:
        sales, inventory = load_data(current_user.id)
        result = get_advisor_panel(sales, inventory)
        return to_native(result)
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Business data files not found. Run create_dataset.py before starting the API."
        )
    except Exception:
        logger.exception("Unexpected error while consulting advisor panel")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong consulting the advisor panel. Check server logs."
        )


# ---------- Manual Test Endpoint (TEMPORARY) ----------
# NOTE: This endpoint is for testing only!
# It should be removed or protected with authentication before production use!
@app.post("/api/test-daily-report")
def test_daily_report():
    """
    Manual test trigger for the daily report (temporary for testing only!)
    """
    try:
        run_daily_report()
        return {"status": "success", "message": "Daily report triggered successfully — check logs for details"}
    except Exception as e:
        logger.exception("Test daily report failed")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")
