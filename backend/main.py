import logging
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from analysis_engine import get_all_insights, ask_question, to_native, generate_executive_summary, load_data
from pdf_report import build_pdf_report

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


class ExecutiveSummary(BaseModel):
    summary: str
    generated_by: str
    context: dict


class InsightsResponse(BaseModel):
    profit_analysis: ProfitAnalysis
    stop_selling: List[StopSellingItem]
    reorder: List[ReorderItem]
    profit_trend: List[ProfitTrendPoint]
    raw_summary: List[RawSummaryItem]
    priority_actions: List[PriorityAction]
    anomaly_alerts: List[AnomalyAlert]
    health_score: HealthScore
    executive_summary: ExecutiveSummary


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


SESSION_HISTORY: dict[str, list] = {}
MAX_HISTORY_PER_SESSION = 6


# ---------- Routes ----------

@app.get("/", response_model=HealthResponse)
def root():
    """Basic health check to confirm the API is up."""
    return {"status": "ok", "service": "AI Business Doctor API"}


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


@app.get("/executive-summary", response_model=ExecutiveSummary)
def executive_summary():
    """
    Returns just the board-meeting-opening executive summary on its own —
    useful for a dedicated "Board Meeting Mode" view in the frontend that
    doesn't need the full /insights payload.
    """
    try:
        sales, inventory = load_data()
        result = generate_executive_summary(sales, inventory)
        return to_native(result)
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