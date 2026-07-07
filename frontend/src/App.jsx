import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import './App.css'
import { API_BASE_URL } from './config'

function App() {
  const [insights, setInsights] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [question, setQuestion] = useState('')
  const [chatHistory, setChatHistory] = useState([])
  const [asking, setAsking] = useState(false)

  // Board Meeting Mode state
  const [showBoardMode, setShowBoardMode] = useState(false)
  const [execSummary, setExecSummary] = useState(null)
  const [execLoading, setExecLoading] = useState(false)
  const [execError, setExecError] = useState(null)

  // One session_id per page load, so follow-up questions ("what about last
  // month?") are understood in context of what was just asked. A fresh
  // refresh starts a clean conversation, which is the expected behavior.
  const sessionIdRef = useRef(crypto.randomUUID())

  const suggestedQuestions = [
    'Why are profits down?',
    'What should I stop selling?',
    'What should I reorder?'
  ]

  const handleAsk = async (q) => {
    const finalQuestion = q || question
    if (!finalQuestion.trim() || asking) return

    setAsking(true)
    setChatHistory(prev => [...prev, { type: 'question', text: finalQuestion }])
    setQuestion('')

    try {
      const res = await axios.post(`${API_BASE_URL}/ask`, {
        question: finalQuestion,
        session_id: sessionIdRef.current
      })
      setChatHistory(prev => [...prev, { type: 'answer', text: res.data.answer }])
    } catch (err) {
      setChatHistory(prev => [...prev, { type: 'answer', text: 'Could not reach the diagnostic engine. Please check the backend is running.' }])
    } finally {
      setAsking(false)
    }
  }

  const openBoardMeetingMode = async () => {
    setShowBoardMode(true)
    setExecLoading(true)
    setExecError(null)
    try {
      const res = await axios.get(`${API_BASE_URL}/executive-summary`)
      setExecSummary(res.data)
    } catch (err) {
      setExecError("Couldn't load the executive summary. Make sure the backend is running.")
    } finally {
      setExecLoading(false)
    }
  }

  useEffect(() => {
    axios.get(`${API_BASE_URL}/insights`)
      .then(res => {
        setInsights(res.data)
        setLoading(false)
      })
      .catch(err => {
        setError('Could not reach the backend. Make sure uvicorn is running on port 8000.')
        setLoading(false)
      })
  }, [])

  if (loading) {
    return (
      <div className="scan-screen">
        <div className="pulse-line"></div>
        <p>Running diagnostic scan on your business...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="scan-screen error-screen">
        <p>⚠ {error}</p>
      </div>
    )
  }

  const { profit_analysis, stop_selling, reorder, health_score, priority_actions, anomaly_alerts } = insights
  const isProfitDown = profit_analysis.total_profit_change < 0

  // --- Defensive helpers for Health Score (field names may vary) ---
  const hsScore = health_score?.score ?? health_score?.value ?? null
  const hsLabel = health_score?.label ?? health_score?.status ?? null
  const hsReasons = health_score?.reasons ?? health_score?.breakdown ?? health_score?.factors ?? []

  const hsColorClass = (() => {
    if (hsLabel) {
      const l = hsLabel.toLowerCase()
      if (l.includes('critical') || l.includes('poor') || l.includes('bad')) return 'critical'
      if (l.includes('warn') || l.includes('fair') || l.includes('moderate')) return 'warning'
      return 'healthy'
    }
    if (typeof hsScore === 'number') {
      if (hsScore < 40) return 'critical'
      if (hsScore < 70) return 'warning'
      return 'healthy'
    }
    return 'healthy'
  })()

  // --- Defensive helpers for Priority Actions (field names may vary) ---
  const priorityList = Array.isArray(priority_actions) ? priority_actions : []

  const getActionTitle = (a) => a.product ?? a.title ?? a.name ?? 'Action item'
  const getActionText = (a) => a.action ?? a.description ?? a.reasoning ?? a.recommendation ?? ''
  const getActionImpact = (a) => a.impact_rupees ?? a.impact ?? a.rupee_impact ?? null
  const getActionUrgency = (a) => (a.urgency_label ?? a.urgency ?? a.priority ?? '').toString()

  const urgencyClass = (urgency) => {
    const u = urgency.toLowerCase()
    if (u.includes('urgent') || u.includes('high') || u.includes('critical')) return 'critical-tag'
    if (u.includes('medium') || u.includes('moderate')) return 'warning-tag'
    return ''
  }

  // --- Defensive helpers for Anomaly Alerts (field names may vary) ---
  const anomalyList = Array.isArray(anomaly_alerts) ? anomaly_alerts : []

  const getAnomalyTitle = (a) => a.product ?? a.title ?? a.type ?? 'Alert'
  const getAnomalyText = (a) => a.message ?? a.description ?? a.reasoning ?? ''
  const getAnomalySeverity = (a) => (a.severity ?? a.urgency ?? a.level ?? '').toString()

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <div className="cross-icon">+</div>
          <div>
            <h1>AI Business Doctor</h1>
            <p className="subtitle">Diagnostic report for your business — generated just now</p>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={openBoardMeetingMode}
            style={{
              background: '#1a1a2e',
              color: '#fff',
              border: 'none',
              padding: '10px 18px',
              borderRadius: '8px',
              cursor: 'pointer',
              fontWeight: 600,
              fontFamily: 'inherit',
              fontSize: '13px',
              whiteSpace: 'nowrap'
            }}
          >
            🎤 Board Meeting Mode
          </button>
          <a
            href={`${API_BASE_URL}/export-report`}
            download="business_diagnosis_report.pdf"
            style={{
              padding: '10px 18px',
              borderRadius: '8px',
              border: '1px solid #3a5a52',
              background: 'transparent',
              color: '#8fd9c4',
              fontFamily: 'inherit',
              fontSize: '13px',
              cursor: 'pointer',
              textDecoration: 'none',
              whiteSpace: 'nowrap'
            }}
          >
            ⬇ Download Report
          </a>
          <div className={`vital-badge ${isProfitDown ? 'critical' : 'healthy'}`}>
            {isProfitDown ? 'Attention Needed' : 'Stable'}
          </div>
        </div>
      </header>

      {/* Health Score */}
      {(hsScore !== null || hsLabel) && (
        <section className={`health-score-card ${hsColorClass}`}>
          <div className="health-score-main">
            {hsScore !== null && <div className="health-score-number">{hsScore}</div>}
            <div className="health-score-text">
              <span className="health-score-title">Business Health Score</span>
              {hsLabel && <span className={`health-score-label ${hsColorClass}`}>{hsLabel}</span>}
            </div>
          </div>
          {Array.isArray(hsReasons) && hsReasons.length > 0 && (
            <ul className="health-score-reasons">
              {hsReasons.map((r, i) => (
                <li key={i}>{typeof r === 'string' ? r : (r.text ?? r.reason ?? JSON.stringify(r))}</li>
              ))}
            </ul>
          )}
        </section>
      )}

      {/* Vitals Summary */}
      <section className="vitals-row">
        <div className={`vital-card ${isProfitDown ? 'critical' : 'healthy'}`}>
          <span className="vital-label">Profit Trend (15 days)</span>
          <span className="vital-value">
            {isProfitDown ? '↓' : '↑'} Rs {Math.abs(profit_analysis.total_profit_change).toLocaleString()}
          </span>
        </div>
        <div className="vital-card warning">
          <span className="vital-label">Stop-Selling Candidates</span>
          <span className="vital-value">{stop_selling.length}</span>
        </div>
        <div className="vital-card critical">
          <span className="vital-label">Urgent Reorders</span>
          <span className="vital-value">{reorder.length}</span>
        </div>
      </section>

      {/* Priority Actions */}
      {priorityList.length > 0 && (
        <section className="priority-actions-card">
          <div className="report-header">
            <span className="report-icon">★</span>
            <h2>Priority Actions</h2>
          </div>
          <div className="findings-list">
            {priorityList.map((a, i) => {
              const urgency = getActionUrgency(a)
              return (
                <div className="finding priority-finding" key={i}>
                  <div className="finding-header">
                    <span className="finding-rank">#{i + 1}</span>
                    <span className="finding-name">{getActionTitle(a)}</span>
                    {urgency && (
                      <span className={`finding-tag ${urgencyClass(urgency)}`}>{urgency}</span>
                    )}
                  </div>
                  {getActionText(a) && <p className="finding-reasoning">{getActionText(a)}</p>}
                  {getActionImpact(a) !== null && (
                    <div className="reorder-qty">
                      Estimated impact: Rs {Math.abs(getActionImpact(a)).toLocaleString()}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* Anomaly Alerts */}
      {anomalyList.length > 0 && (
        <section className="anomaly-alerts-card">
          <div className="report-header">
            <span className="report-icon">!</span>
            <h2>Anomaly Alerts</h2>
          </div>
          <div className="findings-list">
            {anomalyList.map((a, i) => {
              const severity = getAnomalySeverity(a)
              return (
                <div className="finding" key={i}>
                  <div className="finding-header">
                    <span className="finding-name">{getAnomalyTitle(a)}</span>
                    {severity && (
                      <span className={`finding-tag ${urgencyClass(severity)}`}>{severity}</span>
                    )}
                  </div>
                  {getAnomalyText(a) && <p className="finding-reasoning">{getAnomalyText(a)}</p>}
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* Consult the Doctor - Q&A */}
      <section className="consult-card">
        <div className="report-header">
          <span className="report-icon">?</span>
          <h2>Consult the Doctor</h2>
        </div>

        <div className="chat-window">
          {chatHistory.length === 0 && (
            <p className="chat-placeholder">Ask a question about your business — try one of the suggestions below.</p>
          )}
          {chatHistory.map((msg, i) => (
            <div key={i} className={`chat-bubble ${msg.type}`}>
              {msg.type === 'question' ? <strong>You:</strong> : <strong>Doctor:</strong>} {msg.text}
            </div>
          ))}
          {asking && <div className="chat-bubble answer thinking">Doctor is analyzing...</div>}
        </div>

        <div className="suggested-questions">
          {suggestedQuestions.map((sq, i) => (
            <button key={i} className="suggestion-chip" onClick={() => handleAsk(sq)} disabled={asking}>
              {sq}
            </button>
          ))}
        </div>

        <form className="chat-input-row" onSubmit={(e) => { e.preventDefault(); handleAsk(); }}>
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Type your own question..."
            disabled={asking}
          />
          <button type="submit" disabled={asking || !question.trim()}>Ask</button>
        </form>
      </section>

      <main className="report-grid">
        {/* Diagnosis: Profit */}
        <div className="report-card">
          <div className="report-header">
            <span className="report-icon">◆</span>
            <h2>Diagnosis: Profit Movement</h2>
          </div>
          <p className="report-summary">{profit_analysis.summary}</p>
          <div className="findings-list">
            {profit_analysis.top_drivers.map((d, i) => (
              <div className="finding" key={i}>
                <div className="finding-header">
                  <span className="finding-name">{d.product}</span>
                  <span className="finding-change negative">{d.pct_change}%</span>
                </div>
                <p className="finding-reasoning">{d.reasoning}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Prescription: Stop Selling */}
        <div className="report-card">
          <div className="report-header">
            <span className="report-icon">Rx</span>
            <h2>Prescription: Consider Discontinuing</h2>
          </div>
          <div className="findings-list">
            {stop_selling.map((s, i) => (
              <div className="finding" key={i}>
                <div className="finding-header">
                  <span className="finding-name">{s.product}</span>
                  <span className="finding-tag">{s.avg_daily_units}/day</span>
                </div>
                <p className="finding-reasoning">{s.reasoning}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Prescription: Reorder */}
        <div className="report-card">
          <div className="report-header">
            <span className="report-icon">Rx</span>
            <h2>Prescription: Reorder Urgently</h2>
          </div>
          <div className="findings-list">
            {reorder.map((r, i) => (
              <div className="finding" key={i}>
                <div className="finding-header">
                  <span className="finding-name">{r.product}</span>
                  <span className="finding-tag critical-tag">{r.days_of_stock_left}d left</span>
                </div>
                <p className="finding-reasoning">{r.reasoning}</p>
                <div className="reorder-qty">Reorder: {r.recommended_reorder_qty} units</div>
              </div>
            ))}
          </div>
        </div>
      </main>

      {/* Board Meeting Mode modal */}
      {showBoardMode && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            background: 'rgba(10, 10, 20, 0.85)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '20px'
          }}
          onClick={() => setShowBoardMode(false)}
        >
          <div
            style={{
              background: '#fff',
              borderRadius: '12px',
              padding: '40px',
              maxWidth: '700px',
              width: '100%',
              maxHeight: '80vh',
              overflowY: 'auto',
              boxShadow: '0 20px 60px rgba(0,0,0,0.4)'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h2 style={{ margin: 0, fontSize: '22px', color: '#1a1a2e' }}>
                🎤 Board Meeting Opening
              </h2>
              <button
                onClick={() => setShowBoardMode(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '22px',
                  cursor: 'pointer',
                  color: '#888'
                }}
              >
                ✕
              </button>
            </div>

            {execLoading && (
              <p style={{ color: '#666', fontStyle: 'italic' }}>Generating summary…</p>
            )}

            {execError && (
              <p style={{ color: '#c0392b' }}>{execError}</p>
            )}

            {execSummary && !execLoading && (
              <>
                <p
                  style={{
                    fontSize: '17px',
                    lineHeight: '1.7',
                    color: '#2a2a3a',
                    whiteSpace: 'pre-wrap'
                  }}
                >
                  {execSummary.summary}
                </p>
                <div
                  style={{
                    marginTop: '24px',
                    paddingTop: '16px',
                    borderTop: '1px solid #eee',
                    fontSize: '12px',
                    color: '#999'
                  }}
                >
                  Generated by: {execSummary.generated_by === 'llm' ? 'AI (live)' : 'fallback template'}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default App