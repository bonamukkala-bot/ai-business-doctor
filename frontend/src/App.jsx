import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import './App.css'
import { API_BASE_URL } from './config'

function HealthGauge({ score, label, colorClass }) {
  const radius = 54
  const circumference = 2 * Math.PI * radius
  const isPending = label === "Pending"
  const displayScore = isPending ? "--" : score
  const offset = isPending ? circumference : circumference - (Math.min(score, 100) / 100) * circumference

  return (
    <div className={`health-gauge ${colorClass} ${isPending ? 'gauge-pending' : ''}`}>
      <svg viewBox="0 0 140 140" className="gauge-svg">
        <circle cx="70" cy="70" r={radius} className="gauge-track" />
        <circle
          cx="70" cy="70" r={radius}
          className="gauge-fill"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="gauge-center">
        <span className="gauge-score">{displayScore}</span>
        <span className="gauge-label">{label}</span>
      </div>
    </div>
  )
}

function Skeleton({ className = '', lines = 1 }) {
  return (
    <div className={`skeleton-wrap ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="skeleton-line" style={{ width: i === lines - 1 && lines > 1 ? '70%' : '100%' }} />
      ))}
    </div>
  )
}

function App() {
  const [insights, setInsights] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [loaded, setLoaded] = useState(false)

  const [execSummary, setExecSummary] = useState(null)
  const [execLoading, setExecLoading] = useState(true)
  const [execError, setExecError] = useState(null)

  const [question, setQuestion] = useState('')
  const [chatHistory, setChatHistory] = useState([])
  const [asking, setAsking] = useState(false)

  const [reportView, setReportView] = useState('ai')

  const [simProduct, setSimProduct] = useState('')
  const [simDemand, setSimDemand] = useState(0)
  const [simResult, setSimResult] = useState(null)
  const [simLoading, setSimLoading] = useState(false)

  const [advisorPanel, setAdvisorPanel] = useState(null)
  const [advisorLoading, setAdvisorLoading] = useState(false)
  const [advisorError, setAdvisorError] = useState(null)

  const sessionIdRef = useRef(crypto.randomUUID())

  const suggestedQuestions = [
    'Why are profits down?',
    'What should I stop selling?',
    'What should I reorder?'
  ]

  const [dataStatus, setDataStatus] = useState(null)
  const [showUploadForm, setShowUploadForm] = useState(false)
  const [connectionType, setConnectionType] = useState('upload') // 'upload' | 'live'
  const [liveSalesPath, setLiveSalesPath] = useState('')
  const [liveInventoryPath, setLiveInventoryPath] = useState('')
  const [salesFile, setSalesFile] = useState(null)
  const [inventoryFile, setInventoryFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [uploadSuccess, setUploadSuccess] = useState(null)

  const lastModifiedRef = useRef(null)

  const refreshDashboard = async () => {
    setLoading(true)
    setExecLoading(true)
    setUploadSuccess(null)
    setUploadError(null)

    setSimResult(null)
    setSimProduct('')
    setSimDemand(0)
    setAdvisorPanel(null)
    setChatHistory([])

    try {
      const insightsRes = await axios.get(`${API_BASE_URL}/insights`)
      setInsights(insightsRes.data)
      setError(null)
      requestAnimationFrame(() => setLoaded(true))
    } catch (err) {
      setError('Could not reach the backend. Make sure uvicorn is running on port 8000.')
    } finally {
      setLoading(false)
    }

    try {
      const execRes = await axios.get(`${API_BASE_URL}/executive-summary`)
      setExecSummary(execRes.data)
      setExecError(null)
    } catch (err) {
      setExecError('Executive summary unavailable — diagnostic data is still live below.')
    } finally {
      setExecLoading(false)
    }

    try {
      const statusRes = await axios.get(`${API_BASE_URL}/data-status`)
      setDataStatus(statusRes.data)
    } catch (err) {
      console.error('Failed to fetch data status', err)
    }
  }

  useEffect(() => {
    refreshDashboard()
  }, [])

  const getRelativeTime = (timestamp) => {
    if (!timestamp) return 'unknown'
    const diffMs = new Date() - new Date(timestamp)
    const diffSecs = Math.max(0, Math.floor(diffMs / 1000))
    if (diffSecs < 60) return 'just now'
    const diffMins = Math.floor(diffSecs / 60)
    if (diffMins < 60) return `${diffMins}m ago`
    const diffHours = Math.floor(diffMins / 60)
    return `${diffHours}h ago`
  }

  const getFilename = (path) => {
    if (!path) return ''
    const parts = path.split(/[/\\]/)
    return parts[parts.length - 1]
  }

  useEffect(() => {
    if (dataStatus && dataStatus.last_modified) {
      lastModifiedRef.current = dataStatus.last_modified
    }
  }, [dataStatus])

  useEffect(() => {
    let interval = null
    if (dataStatus?.source === 'live') {
      interval = setInterval(async () => {
        try {
          const res = await axios.get(`${API_BASE_URL}/data-status`)
          if (res.data.last_modified && res.data.last_modified !== lastModifiedRef.current) {
            console.log('Detected live file modification, refreshing dashboard...')
            lastModifiedRef.current = res.data.last_modified
            await refreshDashboard()
          } else {
            setDataStatus(res.data)
          }
        } catch (err) {
          console.error('Error polling data status', err)
        }
      }, 15000)
    }
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [dataStatus?.source])

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
    } catch {
      setChatHistory(prev => [...prev, {
        type: 'answer',
        text: 'Could not reach the diagnostic engine. Please check the backend is running.'
      }])
    } finally {
      setAsking(false)
    }
  }

  const runSimulation = async () => {
    if (!simProduct || simLoading) return
    setSimLoading(true)
    setSimResult(null)
    try {
      const res = await axios.post(`${API_BASE_URL}/simulate`, {
        product: simProduct,
        demand_change_pct: simDemand
      })
      setSimResult(res.data)
    } catch {
      setSimResult({ error: 'Simulation failed. Check the backend is running.' })
    } finally {
      setSimLoading(false)
    }
  }

  const consultPanel = async () => {
    setAdvisorLoading(true)
    setAdvisorError(null)
    setAdvisorPanel(null)
    try {
      const res = await axios.post(`${API_BASE_URL}/advisor-panel`)
      setAdvisorPanel(res.data)
    } catch {
      setAdvisorError('Could not reach the advisor panel. Make sure the backend is running.')
    } finally {
      setAdvisorLoading(false)
    }
  }

  const handleUpload = async (e) => {
    e.preventDefault()
    if (!salesFile || !inventoryFile) {
      setUploadError('Please select both Sales and Inventory CSV files.')
      return
    }
    setUploading(true)
    setUploadError(null)
    setUploadSuccess(null)

    const formData = new FormData()
    formData.append('sales_file', salesFile)
    formData.append('inventory_file', inventoryFile)

    try {
      const res = await axios.post(`${API_BASE_URL}/upload-data`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
      setUploadSuccess(res.data.message || 'Files uploaded and validated successfully!')
      setSalesFile(null)
      setInventoryFile(null)
      setTimeout(() => {
        setShowUploadForm(false)
      }, 1500)
      await refreshDashboard()
    } catch (err) {
      console.error(err)
      if (err.response && err.response.data && err.response.data.detail) {
        const detail = err.response.data.detail
        if (typeof detail === 'string') {
          setUploadError(detail)
        } else if (detail.message) {
          let msg = detail.message
          if (detail.missing && detail.missing.length > 0) {
            msg += ` Missing columns: ${detail.missing.join(', ')}.`
          }
          if (detail.found && detail.found.length > 0) {
            msg += ` Found columns: ${detail.found.join(', ')}.`
          }
          setUploadError(msg)
        } else {
          setUploadError(JSON.stringify(detail))
        }
      } else {
        setUploadError('An error occurred during upload. Please verify the backend is running.')
      }
    } finally {
      setUploading(false)
    }
  }

  const handleResetDemo = async () => {
    if (!window.confirm('Are you sure you want to reset to the synthetic demo data? Any uploaded files will be overwritten.')) {
      return
    }
    setLoading(true)
    try {
      await axios.post(`${API_BASE_URL}/reset-demo-data`)
      await refreshDashboard()
    } catch (err) {
      console.error(err)
      alert('Failed to reset demo data. Check if backend is running.')
      setLoading(false)
    }
  }

  const handleConnectLive = async (e) => {
    e.preventDefault()
    if (!liveSalesPath.trim() || !liveInventoryPath.trim()) {
      setUploadError('Please provide both sales and inventory file paths.')
      return
    }
    setUploading(true)
    setUploadError(null)
    setUploadSuccess(null)

    try {
      const res = await axios.post(`${API_BASE_URL}/connect-live-file`, {
        sales_path: liveSalesPath.trim(),
        inventory_path: liveInventoryPath.trim()
      })
      setUploadSuccess(res.data.message || 'Connected live files successfully!')
      setTimeout(() => {
        setShowUploadForm(false)
      }, 1500)
      await refreshDashboard()
    } catch (err) {
      console.error(err)
      if (err.response && err.response.data && err.response.data.detail) {
        const detail = err.response.data.detail
        if (typeof detail === 'string') {
          setUploadError(detail)
        } else if (detail.message) {
          let msg = detail.message
          if (detail.missing && detail.missing.length > 0) {
            msg += ` Missing columns: ${detail.missing.join(', ')}.`
          }
          if (detail.found && detail.found.length > 0) {
            msg += ` Found columns: ${detail.found.join(', ')}.`
          }
          setUploadError(msg)
        } else {
          setUploadError(JSON.stringify(detail))
        }
      } else {
        setUploadError('An error occurred. Make sure the server can access these file paths.')
      }
    } finally {
      setUploading(false)
    }
  }

  const handleDisconnectLive = async () => {
    if (!window.confirm('Disconnect live files and return to demo/uploaded mode?')) {
      return
    }
    setLoading(true)
    try {
      await axios.post(`${API_BASE_URL}/disconnect-live-file`)
      await refreshDashboard()
    } catch (err) {
      console.error(err)
      alert('Failed to disconnect. Make sure the backend is running.')
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="scan-screen">
        <div className="scan-ring" />
        <p>Running diagnostic scan on your business…</p>
        <Skeleton lines={2} className="scan-skeleton" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="scan-screen error-screen">
        <div className="error-icon">!</div>
        <h2>Connection Lost</h2>
        <p>{error}</p>
        <p className="error-hint">Start the API with: <code>uvicorn main:app --reload</code> from the backend folder.</p>
      </div>
    )
  }

  const {
    profit_analysis, stop_selling, reorder, health_score,
    priority_actions, anomaly_alerts, profit_trend, raw_summary
  } = insights

  const isProfitDown = profit_analysis.total_profit_change < 0
  const hsScore = health_score?.score ?? 0
  const hsLabel = health_score?.label ?? 'Unknown'
  const hsReasons = health_score?.breakdown ?? []
  const priorityList = Array.isArray(priority_actions) ? priority_actions : []
  const anomalyList = Array.isArray(anomaly_alerts) ? anomaly_alerts : []

  const hsColorClass = (() => {
    const l = hsLabel.toLowerCase()
    if (l.includes('critical') || hsScore < 40) return 'critical'
    if (l.includes('attention') || l.includes('warn') || hsScore < 60) return 'warning'
    return 'healthy'
  })()

  const urgencyClass = (urgency) => {
    const u = (urgency || '').toLowerCase()
    if (u.includes('urgent') || u.includes('high') || u.includes('critical')) return 'critical-tag'
    if (u.includes('medium') || u.includes('moderate')) return 'warning-tag'
    return ''
  }

  const products = raw_summary?.map(r => r.product) ?? []

  return (
    <div className={`app ${loaded ? 'app-loaded' : ''}`}>
      <header className="header">
        <div className="header-brand">
          <div className="brand-mark">✚</div>
          <div>
            <h1>AI Business Doctor</h1>
            <p className="subtitle">Executive diagnostic · Live intelligence</p>
          </div>
        </div>
        <div className="header-actions">
          <a href={`${API_BASE_URL}/export-report`} className="btn-ghost" download="business_diagnosis_report.pdf">
            Download Report
          </a>
          <span className={`status-pill ${isProfitDown ? 'critical' : 'healthy'}`}>
            {isProfitDown ? 'Attention Needed' : 'Stable'}
          </span>
        </div>
      </header>

      {/* Data Source Panel */}
      <section className="data-source-card card-interactive">
        <div className="data-source-header">
          <div className="source-info">
            <span className="section-eyebrow">Data Connection</span>
            <div className="source-status-row">
              <span className={`badge-status ${dataStatus?.source === 'live' ? 'badge-live' : (dataStatus?.source === 'uploaded' ? 'badge-uploaded' : 'badge-demo')}`}>
                {dataStatus?.source === 'live' ? '🔴 Live Connected' : (dataStatus?.source === 'uploaded' ? 'Your Data' : 'Demo Data')}
              </span>
              {dataStatus?.source === 'live' && (
                <span className="live-indicator-dot"></span>
              )}
              {dataStatus && (
                <span className="source-meta">
                  {dataStatus.source === 'live' ? (
                    <>
                      Watching sales file: <strong>{getFilename(dataStatus.sales_path)}</strong> (updated {getRelativeTime(dataStatus.last_modified)})
                      <br />
                      <span className="history-captured-text">
                        {dataStatus.days_of_history_captured ?? 0} days of history captured — {
                          (dataStatus.days_of_history_captured ?? 0) < 15 
                            ? `full trends available from day 15` 
                            : `full trends available!`
                        }
                      </span>
                    </>
                  ) : (
                    <>
                      Coverage: <strong>{dataStatus.date_range}</strong> ({dataStatus.days} days, {dataStatus.products} products)
                    </>
                  )}
                </span>
              )}
            </div>
          </div>
          <div className="source-actions">
            <button className="btn-ghost" onClick={() => {
              setShowUploadForm(!showUploadForm);
              setUploadError(null);
              setUploadSuccess(null);
            }}>
              {showUploadForm ? 'Close Panel' : 'Manage Data'}
            </button>
            {dataStatus?.source === 'live' ? (
              <button className="btn-reset" onClick={handleDisconnectLive}>
                Disconnect Live
              </button>
            ) : (
              dataStatus?.source === 'uploaded' && (
                <button className="btn-reset" onClick={handleResetDemo}>
                  Reset to Demo Data
                </button>
              )
            )}
          </div>
        </div>

        {showUploadForm && (
          <div className="drawer-container">
            <div className="panel-tabs">
              <button 
                type="button" 
                className={`tab-btn ${connectionType === 'upload' ? 'active' : ''}`}
                onClick={() => { setConnectionType('upload'); setUploadError(null); setUploadSuccess(null); }}
              >
                CSV/Excel Upload
              </button>
              <button 
                type="button" 
                className={`tab-btn ${connectionType === 'live' ? 'active' : ''}`}
                onClick={() => { setConnectionType('live'); setUploadError(null); setUploadSuccess(null); }}
              >
                Connect Live File
              </button>
            </div>

            {connectionType === 'upload' ? (
              <form className="upload-drawer" onSubmit={handleUpload}>
                <h3>Upload Store Data</h3>
                <p className="upload-instructions">
                  Provide your sales and inventory records in CSV or Excel (XLSX) format. The system validates required column structures and values in real-time.
                </p>
                
                <div className="file-inputs-row">
                  <div className="file-input-group">
                    <label>Sales File <span className="req-cols">(Supports .csv, .xlsx; needs: date, product, units_sold, revenue, profit)</span></label>
                    <input 
                      type="file" 
                      accept=".csv,.xlsx,.xls" 
                      onChange={e => {
                        setSalesFile(e.target.files[0] || null)
                        setUploadError(null)
                        setUploadSuccess(null)
                      }}
                      required
                    />
                    {salesFile && <span className="selected-filename">✓ {salesFile.name}</span>}
                  </div>

                  <div className="file-input-group">
                    <label>Inventory File <span className="req-cols">(Supports .csv, .xlsx; needs: product, current_stock, unit_cost)</span></label>
                    <input 
                      type="file" 
                      accept=".csv,.xlsx,.xls" 
                      onChange={e => {
                        setInventoryFile(e.target.files[0] || null)
                        setUploadError(null)
                        setUploadSuccess(null)
                      }}
                      required
                    />
                    {inventoryFile && <span className="selected-filename">✓ {inventoryFile.name}</span>}
                  </div>
                </div>

                {uploadError && <div className="upload-message error-msg">{uploadError}</div>}
                {uploadSuccess && <div className="upload-message success-msg">{uploadSuccess}</div>}

                <div className="upload-submit-row">
                  <button type="submit" className="btn-primary" disabled={uploading || !salesFile || !inventoryFile}>
                    {uploading ? 'Validating & Uploading...' : 'Upload files'}
                  </button>
                </div>
              </form>
            ) : (
              <form className="upload-drawer" onSubmit={handleConnectLive}>
                <h3>Connect Local Live Files</h3>
                <p className="upload-instructions">
                  Enter the absolute paths to your sales and inventory spreadsheets on this machine. The system validates the files' format in real-time, and will automatically monitor them for updates.
                  <br />
                  <span className="help-note">Note: This only works when the backend engine runs on the same machine where these files reside (or a shared local directory).</span>
                </p>
                
                <div className="file-inputs-row">
                  <div className="file-input-group">
                    <label htmlFor="live-sales-path">Sales File Path <span className="req-cols">(Supports .csv, .xlsx, .xls; e.g. C:\Users\YourName\Documents\sales.xlsx)</span></label>
                    <input 
                      id="live-sales-path"
                      type="text"
                      className="text-input"
                      value={liveSalesPath}
                      onChange={e => {
                        setLiveSalesPath(e.target.value)
                        setUploadError(null)
                        setUploadSuccess(null)
                      }}
                      placeholder="e.g. C:\Users\YourName\Documents\sales_data.xlsx"
                      required
                    />
                  </div>

                  <div className="file-input-group">
                    <label htmlFor="live-inventory-path">Inventory File Path <span className="req-cols">(Supports .csv, .xlsx, .xls; e.g. C:\Users\YourName\Documents\inventory.xlsx)</span></label>
                    <input 
                      id="live-inventory-path"
                      type="text"
                      className="text-input"
                      value={liveInventoryPath}
                      onChange={e => {
                        setInventoryFile(null) // Reset standard upload file
                        setLiveInventoryPath(e.target.value)
                        setUploadError(null)
                        setUploadSuccess(null)
                      }}
                      placeholder="e.g. C:\Users\YourName\Documents\inventory_data.xlsx"
                      required
                    />
                  </div>
                </div>

                {uploadError && <div className="upload-message error-msg">{uploadError}</div>}
                {uploadSuccess && <div className="upload-message success-msg">{uploadSuccess}</div>}

                <div className="upload-submit-row">
                  <button type="submit" className="btn-primary" disabled={uploading || !liveSalesPath.trim() || !liveInventoryPath.trim()}>
                    {uploading ? 'Connecting...' : 'Connect Live Files'}
                  </button>
                </div>
              </form>
            )}
          </div>
        )}
      </section>

      {/* Board Meeting Hero */}
      <section className="board-hero card-interactive">
        <div className="board-hero-header">
          <span className="section-eyebrow">Board Meeting</span>
          <span className="live-dot">Live</span>
        </div>
        {execLoading ? (
          <div className="board-hero-body">
            <Skeleton lines={4} />
            <p className="board-loading-text">Composing executive briefing…</p>
          </div>
        ) : execError ? (
          <div className="board-hero-body">
            <p className="board-narrative fallback">{execError}</p>
          </div>
        ) : (
          <div className="board-hero-body">
            <p className="board-narrative">{execSummary?.narrative}</p>
            {execSummary && (
              <div className="board-meta">
                <div className="board-meta-item">
                  <span className="meta-label">Forecast (15d)</span>
                  <span className="meta-value">
                    {execSummary.insufficient_data 
                      ? 'Awaiting history' 
                      : `Rs ${execSummary.profit_forecast_next_15_days?.toLocaleString()}`}
                  </span>
                </div>
                <div className="board-meta-item">
                  <span className="meta-label">Top Risk</span>
                  <span className="meta-value risk">{execSummary.top_risk}</span>
                </div>
                <div className="board-meta-item">
                  <span className="meta-label">Opportunity</span>
                  <span className="meta-value opp">{execSummary.top_opportunity}</span>
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      {/* Health + Chart */}
      <section className="health-chart-row">
        <div className="health-centerpiece card-interactive">
          <span className="section-eyebrow">Vitals</span>
          <h2 className="section-title">Business Health</h2>
          <HealthGauge score={hsScore} label={hsLabel} colorClass={hsColorClass} />
          {hsReasons.length > 0 && (
            <ul className="health-breakdown">
              {hsReasons.slice(0, 4).map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          )}
        </div>

        <div className="profit-chart-card card-interactive">
          <span className="section-eyebrow">Trend</span>
          <h2 className="section-title">30-Day Profit</h2>
          {insights?.insufficient_data ? (
            <div className="chart-placeholder">
              <p className="placeholder-msg">
                Still learning your business — check back after a few more days of data (at least 15 days) to see profit trends.
              </p>
            </div>
          ) : (
            <div className="chart-container">
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={profit_trend} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(61,171,168,0.12)" />
                  <XAxis dataKey="date" tick={{ fill: '#7A8F9A', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#7A8F9A', fontSize: 11 }} axisLine={false} tickLine={false} width={50} />
                  <Tooltip
                    contentStyle={{ background: '#141C24', border: '1px solid #2A3A44', borderRadius: 8, fontSize: 12 }}
                    labelStyle={{ color: '#9BB0BC' }}
                    itemStyle={{ color: '#3DABA8' }}
                  />
                  <Line type="monotone" dataKey="profit" stroke="#3DABA8" strokeWidth={2.5} dot={false} activeDot={{ r: 4, fill: '#3DABA8' }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </section>

      {/* Vitals Row */}
      <section className="vitals-row">
        <div className={`vital-card card-interactive ${isProfitDown && !insights?.insufficient_data ? 'critical' : 'healthy'}`}>
          <span className="vital-label">Profit (15 days)</span>
          <span className="vital-value">
            {insights?.insufficient_data 
              ? 'Awaiting history' 
              : `${isProfitDown ? '↓' : '↑'} Rs ${Math.abs(profit_analysis.total_profit_change).toLocaleString()}`}
          </span>
        </div>
        <div className="vital-card card-interactive warning">
          <span className="vital-label">Stop-Selling</span>
          <span className="vital-value">{stop_selling.length}</span>
        </div>
        <div className="vital-card card-interactive critical">
          <span className="vital-label">Urgent Reorders</span>
          <span className="vital-value">{reorder.length}</span>
        </div>
        <div className="vital-card card-interactive">
          <span className="vital-label">Active Alerts</span>
          <span className="vital-value">{anomalyList.length}</span>
        </div>
      </section>

      {/* Priority Actions */}
      {priorityList.length > 0 && (
        <section className="priority-section">
          <div className="section-head">
            <span className="section-eyebrow">Action Plan</span>
            <h2 className="section-title">Priority Actions</h2>
          </div>
          <ol className="priority-list">
            {priorityList.map((a, i) => (
              <li className={`priority-item card-interactive urgency-${(a.urgency_label || '').toLowerCase()}`} key={i}>
                <span className="priority-rank">{a.rank ?? i + 1}</span>
                <div className="priority-content">
                  <div className="priority-top">
                    <span className="priority-product">{a.product}</span>
                    {a.urgency_label && (
                      <span className={`tag ${urgencyClass(a.urgency_label)}`}>{a.urgency_label}</span>
                    )}
                  </div>
                  <p className="priority-action">{a.recommended_action}</p>
                  <span className="priority-impact">Rs {a.impact_rupees?.toLocaleString()} impact</span>
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* Anomaly Alerts */}
      {anomalyList.length > 0 && (
        <section className="alerts-section">
          <div className="section-head">
            <span className="section-eyebrow">Proactive</span>
            <h2 className="section-title">Anomaly Alerts</h2>
          </div>
          <div className="alerts-grid">
            {anomalyList.map((a, i) => (
              <div
                className={`alert-card card-interactive ${a.severity === 'critical' ? 'pulse-critical' : ''}`}
                key={i}
              >
                <div className="alert-header">
                  <span className="alert-product">{a.product}</span>
                  <span className={`tag ${urgencyClass(a.severity)}`}>{a.severity}</span>
                </div>
                <p className="alert-message">{a.message}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* What-If Simulator */}
      <section className="simulator-section card-interactive">
        <div className="section-head">
          <span className="section-eyebrow">Scenario</span>
          <h2 className="section-title">What-If Simulator</h2>
        </div>
        <div className="simulator-controls">
          <div className="sim-field">
            <label htmlFor="sim-product">Product</label>
            <select
              id="sim-product"
              value={simProduct}
              onChange={e => { setSimProduct(e.target.value); setSimResult(null) }}
            >
              <option value="">Select a product…</option>
              {products.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div className="sim-field sim-slider-field">
            <label htmlFor="sim-demand">
              Demand change: <strong>{simDemand > 0 ? '+' : ''}{simDemand}%</strong>
            </label>
            <input
              id="sim-demand"
              type="range"
              min={-50}
              max={100}
              value={simDemand}
              onChange={e => { setSimDemand(Number(e.target.value)); setSimResult(null) }}
            />
            <div className="slider-labels"><span>-50%</span><span>+100%</span></div>
          </div>
          <button className="btn-primary" onClick={runSimulation} disabled={!simProduct || simLoading}>
            {simLoading ? 'Running…' : 'Run Simulation'}
          </button>
        </div>
        {simLoading && <Skeleton lines={2} className="sim-skeleton" />}
        {simResult && !simLoading && (
          <div className={`sim-result ${simResult.error ? 'sim-error' : ''}`}>
            {simResult.error ? (
              <p>{simResult.error}</p>
            ) : (
              <>
                <div className="sim-metrics">
                  <div><span>Stock runway</span><strong>{simResult.projected_days_of_stock_left} days</strong></div>
                  <div><span>Was</span><strong>{simResult.baseline_days_of_stock_left} days</strong></div>
                  <div><span>7-day profit impact</span><strong>Rs {simResult.projected_profit_impact?.toLocaleString()}</strong></div>
                </div>
                <p className="sim-action">{simResult.recommended_action}</p>
              </>
            )}
          </div>
        )}
      </section>

      {/* Panel of Advisors */}
      <section className="advisors-section">
        <div className="section-head section-head-row">
          <div>
            <span className="section-eyebrow">Expertise</span>
            <h2 className="section-title">Panel of Advisors</h2>
          </div>
          <button className="btn-primary" onClick={consultPanel} disabled={advisorLoading}>
            {advisorLoading ? 'Consulting…' : 'Consult Panel'}
          </button>
        </div>
        {advisorError && <p className="advisor-error">{advisorError}</p>}
        {advisorLoading && (
          <div className="advisors-grid">
            {[1, 2, 3].map(i => (
              <div className="advisor-card skeleton-advisor" key={i}><Skeleton lines={3} /></div>
            ))}
          </div>
        )}
        {advisorPanel && !advisorLoading && (
          <div className="advisors-grid">
            <div className="advisor-card finance card-interactive">
              <div className="advisor-icon">₹</div>
              <h3>Finance</h3>
              <p>{advisorPanel.finance_take}</p>
            </div>
            <div className="advisor-card operations card-interactive">
              <div className="advisor-icon">⚙</div>
              <h3>Operations</h3>
              <p>{advisorPanel.operations_take}</p>
            </div>
            <div className="advisor-card marketing card-interactive">
              <div className="advisor-icon">◎</div>
              <h3>Marketing</h3>
              <p>{advisorPanel.marketing_take}</p>
            </div>
          </div>
        )}
        {!advisorPanel && !advisorLoading && !advisorError && (
          <p className="advisor-placeholder">Three specialist advisors ready — each grounded in your live business data.</p>
        )}
      </section>

      {/* Consult the Doctor */}
      <section className="consult-section card-interactive">
        <div className="section-head">
          <span className="section-eyebrow">Interactive</span>
          <h2 className="section-title">Consult the Doctor</h2>
        </div>
        <div className="chat-window">
          {chatHistory.length === 0 && (
            <p className="chat-placeholder">Ask anything about your sales, profit, or inventory.</p>
          )}
          {chatHistory.map((msg, i) => (
            <div key={i} className={`chat-bubble ${msg.type}`}>
              <span className="chat-role">{msg.type === 'question' ? 'You' : 'Doctor'}</span>
              {msg.text}
            </div>
          ))}
          {asking && (
            <div className="chat-bubble answer thinking">
              <span className="chat-role">Doctor</span>
              <Skeleton lines={1} />
            </div>
          )}
        </div>
        <div className="suggested-questions">
          {suggestedQuestions.map((sq, i) => (
            <button key={i} className="chip" onClick={() => handleAsk(sq)} disabled={asking}>{sq}</button>
          ))}
        </div>
        <form className="chat-form" onSubmit={e => { e.preventDefault(); handleAsk() }}>
          <input
            type="text"
            value={question}
            onChange={e => setQuestion(e.target.value)}
            placeholder="Type your question…"
            disabled={asking}
          />
          <button type="submit" className="btn-primary" disabled={asking || !question.trim()}>Ask</button>
        </form>
      </section>

      {/* Report Toggle + Grid */}
      <section className="report-section">
        <div className="section-head section-head-row">
          <div>
            <span className="section-eyebrow">Deep Dive</span>
            <h2 className="section-title">Full Report</h2>
          </div>
          <div className="view-toggle">
            <button
              className={reportView === 'raw' ? 'active' : ''}
              onClick={() => setReportView('raw')}
            >Raw Report</button>
            <button
              className={reportView === 'ai' ? 'active' : ''}
              onClick={() => setReportView('ai')}
            >AI Diagnosis</button>
          </div>
        </div>

        {reportView === 'raw' ? (
          <div className="raw-table-wrap card-interactive">
            <table className="raw-table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Units</th>
                  <th>Revenue (Rs)</th>
                  <th>Profit (Rs)</th>
                  <th>Stock</th>
                </tr>
              </thead>
              <tbody>
                {raw_summary.map((row, i) => (
                  <tr key={i}>
                    <td>{row.product}</td>
                    <td>{row.total_units}</td>
                    <td>{row.total_revenue.toLocaleString()}</td>
                    <td>{row.total_profit.toLocaleString()}</td>
                    <td>{row.current_stock}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="raw-caption">Raw numbers only — no interpretation. Toggle to AI Diagnosis to see explained recommendations.</p>
          </div>
        ) : (
          <div className="report-grid">
            <div className="report-card card-interactive">
              <h3>Profit Movement</h3>
              <p className="report-summary">{profit_analysis.summary}</p>
              {profit_analysis.top_drivers.map((d, i) => (
                <div className="finding" key={i}>
                  <div className="finding-head">
                    <span>{d.product}</span>
                    <span className="negative">{d.pct_change}%</span>
                  </div>
                  <p>{d.reasoning}</p>
                </div>
              ))}
            </div>
            <div className="report-card card-interactive">
              <h3>Consider Discontinuing</h3>
              {stop_selling.map((s, i) => (
                <div className="finding" key={i}>
                  <div className="finding-head">
                    <span>{s.product}</span>
                    <span className="tag">{s.avg_daily_units}/day</span>
                  </div>
                  <p>{s.reasoning}</p>
                </div>
              ))}
            </div>
            <div className="report-card card-interactive">
              <h3>Reorder Urgently</h3>
              {reorder.map((r, i) => (
                <div className="finding" key={i}>
                  <div className="finding-head">
                    <span>{r.product}</span>
                    <span className="tag critical-tag">{r.days_of_stock_left}d left</span>
                  </div>
                  <p>{r.reasoning}</p>
                  <span className="reorder-qty">Reorder: {r.recommended_reorder_qty} units</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  )
}

export default App
