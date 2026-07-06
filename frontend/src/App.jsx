import { useState, useEffect } from 'react'
import axios from 'axios'
import './App.css'

function App() {
  const [insights, setInsights] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    axios.get('http://127.0.0.1:8000/insights')
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

  const { profit_analysis, stop_selling, reorder } = insights
  const isProfitDown = profit_analysis.total_profit_change < 0

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
        <div className={`vital-badge ${isProfitDown ? 'critical' : 'healthy'}`}>
          {isProfitDown ? 'Attention Needed' : 'Stable'}
        </div>
      </header>

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
    </div>
  )
}

export default App