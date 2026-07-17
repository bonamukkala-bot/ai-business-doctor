import logging
import os
import io
import json
import shutil
import datetime
from typing import List
import pandas as pd


from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


from analysis_engine import (
    get_all_insights,
    ask_question,
    to_native,
    get_executive_summary,
    get_advisor_panel,
    simulate_scenario,
    load_data,
)
from pdf_report import build_pdf_report

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_business_doctor")

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


CONFIG_FILE = "data_source_config.json"

def get_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
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

def save_config(config: dict):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save config: {e}")

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

@app.get("/", response_model=HealthResponse)
def root():
    """Basic health check to confirm the API is up."""
    return {"status": "ok", "service": "AI Business Doctor API"}


@app.get("/data-status", response_model=DataStatusResponse)
def data_status():
    try:
        config = get_config()
        mode = config.get("mode", "demo")
        sales_path = "demo_sales_data.csv"
        inventory_path = "demo_inventory_data.csv"
        
        if mode == "uploaded":
            sales_path = config.get("sales_path") or "sales_data.csv"
            inventory_path = config.get("inventory_path") or "inventory_data.csv"
        elif mode == "live":
            sales_path = config.get("sales_path")
            inventory_path = config.get("inventory_path")

        # Fallbacks if files don't exist
        if not sales_path or not os.path.exists(sales_path):
            sales_path = "demo_sales_data.csv"
        if not inventory_path or not os.path.exists(inventory_path):
            inventory_path = "demo_inventory_data.csv"

        sales, inventory = load_data()
        summary = compute_summary(sales, inventory)

        sales_mtime = os.path.getmtime(sales_path) if os.path.exists(sales_path) else 0
        inventory_mtime = os.path.getmtime(inventory_path) if os.path.exists(inventory_path) else 0
        max_mtime = max(sales_mtime, inventory_mtime)
        last_modified = datetime.datetime.fromtimestamp(max_mtime, datetime.timezone.utc).isoformat() if max_mtime > 0 else None

        days_of_history_captured = None
        if mode == "live":
            acc_path = os.path.join(os.path.dirname(__file__), "accumulated_sales_data.csv")
            if os.path.exists(acc_path):
                try:
                    df = pd.read_csv(acc_path)
                    days_of_history_captured = int(df["date"].nunique())
                except Exception as e:
                    logger.error(f"Failed to read accumulated_sales_data.csv for data-status: {e}")
                    days_of_history_captured = 0
            else:
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
    inventory_file: UploadFile = File(...)
):
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
    
    sales_path = f"sales_data{sales_ext}"
    inventory_path = f"inventory_data{inventory_ext}"

    for ext in [".csv", ".xlsx"]:
        other_sales = f"sales_data{ext}"
        other_inv = f"inventory_data{ext}"
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

    config = get_config()
    config["mode"] = "uploaded"
    config["sales_path"] = sales_path
    config["inventory_path"] = inventory_path
    config["uploaded_sales_path"] = sales_path
    config["uploaded_inventory_path"] = inventory_path
    save_config(config)

    sales, inventory = load_data()
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
def reset_demo_data():
    try:
        config = {
            "mode": "demo",
            "sales_path": None,
            "inventory_path": None,
            "uploaded_sales_path": None,
            "uploaded_inventory_path": None
        }
        for path in ["sales_data.csv", "sales_data.xlsx", "inventory_data.csv", "inventory_data.xlsx"]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

        save_config(config)
        sales, inventory = load_data()
        summary = compute_summary(sales, inventory)
        
        sales_path = "demo_sales_data.csv"
        inventory_path = "demo_inventory_data.csv"
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


@app.post("/connect-live-file", response_model=UploadSuccessResponse)
def connect_live_file(request: ConnectLiveRequest):
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

    config = get_config()
    config["mode"] = "live"
    config["sales_path"] = sales_path
    config["inventory_path"] = inventory_path
    save_config(config)

    sales, inventory = load_data()
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
def disconnect_live_file():
    try:
        config = get_config()
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

        save_config(config)

        sales, inventory = load_data()
        summary = compute_summary(sales, inventory)

        active_sales = config.get("sales_path") or "demo_sales_data.csv"
        active_inv = config.get("inventory_path") or "demo_inventory_data.csv"
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




@app.get("/insights", response_model=InsightsResponse)
def insights():
    """
    Runs the full diagnostic: profit driver analysis, stop-selling
    candidates, urgent reorder recommendations, a merged priority action
    list ranked by real rupee impact, business health score, and the
    board-meeting-style executive summary.
    """
    try:
        result = get_all_insights()
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
def executive_summary():
    """
    Returns the board-meeting opening narrative with structured fields —
    health score, forecast, top risk/opportunity, and LLM-written prose.
    """
    try:
        sales, inventory = load_data()
        result = get_executive_summary(sales, inventory)
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
def export_report():
    """
    Generates a formatted PDF version of the current diagnostic report —
    vitals, priority actions, alerts, and full breakdown — so the owner
    can download, print, or share it with a partner or supplier.
    """
    try:
        insights = get_all_insights()
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
def ask(request: AskRequest):
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
        result = ask_question(request.question, history=history)
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
def simulate(request: SimulateRequest):
    """
    What-if scenario: adjusts a product's demand by a percentage and
    returns recalculated stock runway and profit impact.
    """
    if not request.product or not request.product.strip():
        raise HTTPException(status_code=400, detail="Product name cannot be empty.")

    try:
        result = simulate_scenario(request.product.strip(), request.demand_change_pct)
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
def advisor_panel():
    """
    Runs three concurrent Groq calls — Finance, Operations, and Marketing
    advisors — each giving a grounded take on the current business data.
    """
    try:
        sales, inventory = load_data()
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
