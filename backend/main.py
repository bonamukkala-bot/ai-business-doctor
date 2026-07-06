import logging
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from analysis_engine import get_all_insights

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_business_doctor")

app = FastAPI(
    title="AI Business Doctor API",
    description="Diagnostic engine that turns raw sales & inventory data into explained business recommendations.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to specific origins before any real production use
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Response Schemas ----------
# Defining these explicitly (instead of returning raw dicts) gives us automatic
# request/response validation and clean interactive docs at /docs.

class ProfitDriver(BaseModel):
    product: str
    profit_change: float
    pct_change: float
    reasoning: str


class ProfitAnalysis(BaseModel):
    total_profit_change: float
    summary: str
    top_drivers: List[ProfitDriver]


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


class InsightsResponse(BaseModel):
    profit_analysis: ProfitAnalysis
    stop_selling: List[StopSellingItem]
    reorder: List[ReorderItem]


class HealthResponse(BaseModel):
    status: str
    service: str


# ---------- Routes ----------

@app.get("/", response_model=HealthResponse)
def root():
    """Basic health check to confirm the API is up."""
    return {"status": "ok", "service": "AI Business Doctor API"}


@app.get("/insights", response_model=InsightsResponse)
def insights():
    """
    Runs the full diagnostic: profit driver analysis, stop-selling
    candidates, and urgent reorder recommendations.

    Failure modes handled:
    - Missing/corrupt CSV data files -> 503, not a raw stack trace
    - Any unexpected error in the analysis engine -> 500 with a clear message,
      logged server-side for debugging without leaking internals to the client
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
    except Exception as e:
        logger.exception("Unexpected error while generating insights")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong generating the diagnostic report. Check server logs."
        )