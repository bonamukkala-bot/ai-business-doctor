import { useMemo, useRef, useState } from 'react'
import { ArrowUpRight, ArrowDownRight, TrendingUp, ShieldCheck, AlertTriangle, Package, Share2, MessageCircle, Globe, CheckCircle2, Circle, ChevronDown, ChevronUp, Clock, Zap, TrendingDown, Info } from 'lucide-react'
import { Link } from 'react-router-dom'
import html2canvas from 'html2canvas'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts'
import HealthGauge from '../components/HealthGauge.jsx'
import Skeleton from '../components/Skeleton.jsx'
import { API_BASE_URL } from '../config'
import axios from 'axios'

function getGreeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function formatCurrency(value) {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value)
}

function buildSparklinePath(points, width = 100, height = 28) {
  if (!points.length) return ''
  const values = points.map((point) => Number(point.profit ?? point.value ?? 0))
  const max = Math.max(...values)
  const min = Math.min(...values)
  const range = Math.max(max - min, 1)
  return values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * width
      const y = height - ((value - min) / range) * height
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
    })
    .join(' ')
}

export default function DashboardPage({ user, insights, execSummary, execLoading, execError, healthScore, healthLabel, healthReasons, isProfitDown, rootCauseAnalysis, rootCauseLoading, rootCauseError, actionPlan, actionPlanLoading, actionPlanError, onActionPlanChange, cashFlow, cashFlowLoading, cashFlowError }) {
  const shopName = user?.user_metadata?.shop_name || user?.email?.split('@')[0] || 'Business Doctor'
  const greeting = useMemo(() => `${getGreeting()}, ${shopName}`, [shopName])
  const boardSummaryRef = useRef(null)
  const [selectedLanguage, setSelectedLanguage] = useState('english')
  const [languageCache, setLanguageCache] = useState({})
  const [translating, setTranslating] = useState(false)

  // Action Planner local state
  const [completingTaskId, setCompletingTaskId] = useState(null)
  const [showCompleted, setShowCompleted] = useState(false)

  // Check if we have insufficient data or no data
  const hasInsufficientData = insights?.insufficient_data === true || !insights || !insights.profit_analysis
  const hasNoData = !insights || (insights.profit_analysis?.insufficient_data === true && insights.profit_analysis?.top_drivers?.length === 0)

  const handleShareSummary = async () => {
    if (!boardSummaryRef.current) return
    
    try {
      const canvas = await html2canvas(boardSummaryRef.current, {
        backgroundColor: '#121820',
        scale: 2,
        logging: false
      })
      
      const link = document.createElement('a')
      link.download = `business-summary-${new Date().toISOString().split('T')[0]}.png`
      link.href = canvas.toDataURL('image/png')
      link.click()
    } catch (error) {
      console.error('Failed to capture summary:', error)
      alert('Failed to share summary. Please try again.')
    }
  }

  const handleSendWhatsApp = async () => {
    try {
      await axios.post(`${API_BASE_URL}/api/alerts/send-whatsapp`, {
        user_id: user.id
      })
      alert('WhatsApp alert sent successfully!')
    } catch (error) {
      alert(error.response?.data?.detail || 'Failed to send WhatsApp alert. Please add your phone number in Settings.')
    }
  }

  // ── Action Planner handlers ──────────────────────────────────────────────
  const handleCompleteTask = async (taskId) => {
    setCompletingTaskId(taskId)
    try {
      await axios.post(`${API_BASE_URL}/api/action-plan/${taskId}/complete`)
      // Optimistic update: move the task from pending → completed locally
      if (onActionPlanChange && actionPlan) {
        const task = actionPlan.pending.find(t => t.task_id === taskId)
        if (task) {
          const completedTask = { ...task, completed_at: new Date().toISOString() }
          const newPending = actionPlan.pending.filter(t => t.task_id !== taskId)
          const newCompleted = [completedTask, ...actionPlan.completed]
          const newSavings = newPending.reduce((sum, t) => sum + t.expected_saving, 0)
          onActionPlanChange({
            ...actionPlan,
            pending: newPending,
            completed: newCompleted,
            total_potential_savings: Math.round(newSavings * 100) / 100,
          })
        }
      }
    } catch (err) {
      console.error('Failed to mark task complete', err)
    } finally {
      setCompletingTaskId(null)
    }
  }

  const handleReopenTask = async (taskId) => {
    setCompletingTaskId(taskId)
    try {
      await axios.post(`${API_BASE_URL}/api/action-plan/${taskId}/reopen`)
      // Optimistic update: move task from completed → pending locally
      if (onActionPlanChange && actionPlan) {
        const task = actionPlan.completed.find(t => t.task_id === taskId)
        if (task) {
          const { completed_at: _removed, ...reopenedTask } = task
          const newCompleted = actionPlan.completed.filter(t => t.task_id !== taskId)
          const newPending = [...actionPlan.pending, reopenedTask]
          // Re-sort pending by tier then profit_risk desc
          const tierOrder = { Urgent: 0, High: 1, Medium: 2, Low: 3 }
          newPending.sort((a, b) => (tierOrder[a.priority] ?? 99) - (tierOrder[b.priority] ?? 99) || b.profit_risk - a.profit_risk)
          const newSavings = newPending.reduce((sum, t) => sum + t.expected_saving, 0)
          onActionPlanChange({
            ...actionPlan,
            pending: newPending,
            completed: newCompleted,
            total_potential_savings: Math.round(newSavings * 100) / 100,
          })
        }
      }
    } catch (err) {
      console.error('Failed to reopen task', err)
    } finally {
      setCompletingTaskId(null)
    }
  }

  const handleLanguageChange = async (language) => {
    setSelectedLanguage(language)
    
    // Check cache first
    if (languageCache[language]) {
      return
    }

    // Only translate if we have a narrative to translate
    if (!execSummary?.narrative || language === 'english') {
      return
    }

    setTranslating(true)
    try {
      const response = await axios.post(`${API_BASE_URL}/api/translate-narrative`, {
        narrative: execSummary.narrative,
        language: language
      })
      
      setLanguageCache(prev => ({
        ...prev,
        [language]: response.data.translated_narrative
      }))
    } catch (error) {
      console.error('Translation failed:', error)
      // Fallback to original narrative if translation fails
      setLanguageCache(prev => ({
        ...prev,
        [language]: execSummary.narrative
      }))
    } finally {
      setTranslating(false)
    }
  }

  const getCurrentNarrative = () => {
    if (selectedLanguage === 'english' || !languageCache[selectedLanguage]) {
      return execSummary?.narrative
    }
    return languageCache[selectedLanguage]
  }

  const profitChange = insights?.profit_analysis?.total_profit_change ?? 0
  const stopCount = insights?.stop_selling?.length ?? 0
  const urgentReorderCount = (insights?.reorder ?? []).filter((item) => item.days_of_stock_left <= 3).length
  const alertCount = insights?.anomaly_alerts?.length ?? 0
  const trendData = insights?.profit_trend ?? []
  const topPriority = (insights?.priority_actions ?? []).slice(0, 3)

  const vitals = [
    {
      label: 'Profit (15 days)',
      value: formatCurrency(profitChange),
      trend: profitChange >= 0 ? 'up' : 'down',
      icon: TrendingUp,
      sparkline: trendData.slice(-10),
    },
    {
      label: 'Stop-Selling candidates',
      value: stopCount,
      trend: stopCount > 0 ? 'up' : 'down',
      icon: Package,
      sparkline: trendData.slice(-8),
    },
    {
      label: 'Urgent reorders',
      value: urgentReorderCount,
      trend: urgentReorderCount > 0 ? 'up' : 'down',
      icon: ShieldCheck,
      sparkline: trendData.slice(-8),
    },
    {
      label: 'Active alerts',
      value: alertCount,
      trend: alertCount > 0 ? 'up' : 'down',
      icon: AlertTriangle,
      sparkline: trendData.slice(-8),
    },
  ]

  const chartPath = buildSparklinePath(trendData, 720, 180)
  const sparklineTooltip = trendData.slice(-1)[0]?.profit ?? null

  return (
    <div className="dashboard-page">
      <section className="dashboard-greeting-row">
        <div>
          <span className="section-eyebrow">Welcome back</span>
          <h1 className="dashboard-greeting-title">{greeting}</h1>
          <p className="dashboard-greeting-copy">Here is the top-level health view for your shop in the last 15 days.</p>
        </div>
      </section>

      {hasNoData ? (
        <section className="empty-state-card card-interactive">
          <div className="empty-state-content">
            <div className="empty-state-icon">📊</div>
            <h2 className="empty-state-title">No Data Yet</h2>
            <p className="empty-state-description">
              Upload your first sales and inventory files to get started with AI-powered business insights.
            </p>
            <Link to="/settings" className="btn-primary">
              Upload Your Data →
            </Link>
          </div>
        </section>
      ) : hasInsufficientData ? (
        <section className="empty-state-card card-interactive warning">
          <div className="empty-state-content">
            <div className="empty-state-icon">⏳</div>
            <h2 className="empty-state-title">Building Your Business Profile</h2>
            <p className="empty-state-description">
              We need at least 15 days of sales data to generate accurate health scores and recommendations. 
              Keep uploading your daily sales data to unlock full AI diagnostics.
            </p>
            <div className="empty-state-stats">
              <div className="stat-item">
                <span className="stat-value">{insights?.profit_analysis?.insufficient_data ? '0' : 'Loading...'}</span>
                <span className="stat-label">Days of Data</span>
              </div>
              <div className="stat-item">
                <span className="stat-value">15</span>
                <span className="stat-label">Days Required</span>
              </div>
            </div>
            <Link to="/settings" className="btn-primary">
              Add More Data →
            </Link>
          </div>
        </section>
      ) : null}

      {!hasNoData && !hasInsufficientData && (
        <>
          <section className="dashboard-hero-grid">
            <div className="hero-card hero-gauge card-interactive">
              <div className="section-head section-head-spaced">
                <div>
                  <span className="section-eyebrow">Core health</span>
                  <h2 className="section-title">Health Score</h2>
                </div>
                <button 
                  className="btn-ghost btn-icon" 
                  onClick={handleSendWhatsApp}
                  title="Send WhatsApp Alert"
                >
                  <MessageCircle size={16} />
                </button>
              </div>
              <HealthGauge score={healthScore} label={healthLabel} colorClass={isProfitDown ? 'critical' : 'healthy'} />
              <div className="health-subtitle">This score reflects profit, stock risk, and alert urgency.</div>
            </div>

            <div className="hero-card board-summary card-interactive" ref={boardSummaryRef}>
              <div className="section-head section-head-spaced">
                <div>
                  <span className="section-eyebrow">Board Meeting</span>
                  <h2 className="section-title">Executive summary</h2>
                </div>
                <div className="board-summary-actions">
                  <span className="live-pill">Live</span>
                  {!execLoading && !execError && execSummary?.narrative && (
                    <>
                      <select 
                        className="language-selector"
                        value={selectedLanguage}
                        onChange={(e) => handleLanguageChange(e.target.value)}
                        disabled={translating}
                      >
                        <option value="english">English</option>
                        <option value="telugu">తెలుగు</option>
                        <option value="hindi">हिंदी</option>
                      </select>
                      <button 
                        className="btn-ghost btn-icon" 
                        onClick={handleShareSummary}
                        title="Share as PNG"
                      >
                        <Share2 size={16} />
                      </button>
                    </>
                  )}
                </div>
              </div>

              {execLoading ? (
                <div className="board-summary-loading">
                  <Skeleton lines={4} />
                  <p className="board-loading-text">Fetching the latest executive insight…</p>
                </div>
              ) : execError ? (
                <p className="board-narrative fallback">{execError}</p>
              ) : translating ? (
                <div className="board-summary-loading">
                  <Skeleton lines={4} />
                  <p className="board-loading-text">Translating summary…</p>
                </div>
              ) : (
                <p className="board-narrative">{getCurrentNarrative()}</p>
              )}
            </div>
          </section>

          <section className="vitals-row">
            {vitals.map((vital, index) => {
              const TrendIcon = vital.trend === 'up' ? ArrowUpRight : ArrowDownRight
              return (
                <article
                  key={vital.label}
                  className={`vital-card ${vital.trend === 'up' ? 'critical' : 'healthy'}`}
                  style={{ animationDelay: `${index * 80}ms` }}
                >
                  <div className="vital-row">
                    <div>
                      <span className="vital-label">{vital.label}</span>
                      <span className="vital-value">{vital.value}</span>
                    </div>
                    <TrendIcon size={18} className={`vital-icon ${vital.trend}`} />
                  </div>
                  <div className="vital-sparkline">
                    <svg viewBox="0 0 100 28" preserveAspectRatio="none">
                      <defs>
                        <linearGradient id="sparkline-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
                          <stop offset="0%" stopColor="rgba(61, 171, 168, 0.35)" />
                          <stop offset="100%" stopColor="transparent" />
                        </linearGradient>
                      </defs>
                      <path d={buildSparklinePath(vital.sparkline, 100, 28)} fill="none" stroke="rgba(61, 171, 168, 0.8)" strokeWidth="2" />
                    </svg>
                    <span className="vital-sparkline-note">{sparklineTooltip ? `Latest: ${formatCurrency(sparklineTooltip)}` : 'Recent trend'}</span>
                  </div>
                </article>
              )
            })}
          </section>

          <section className="profit-trend-card card-interactive">
            <div className="section-head section-head-row">
              <div>
                <span className="section-eyebrow">Trend</span>
                <h2 className="section-title">30-Day Profit</h2>
              </div>
              <span className="trend-range">Last 30 days</span>
            </div>
            <div className="trend-chart-visual">
              <svg viewBox="0 0 720 240" className="trend-svg" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="profit-gradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="rgba(61, 171, 168, 0.4)" />
                    <stop offset="100%" stopColor="rgba(61, 171, 168, 0.02)" />
                  </linearGradient>
                </defs>
                <path d={`${chartPath} L 720 240 L 0 240 Z`} fill="url(#profit-gradient)" opacity="0.9" />
                <path d={chartPath} fill="none" stroke="var(--accent)" strokeWidth="3" strokeLinecap="round" />
              </svg>
              <div className="chart-meta">Profit line with trend fill and cleaner axis styling.</div>
            </div>
          </section>

          <section className="priority-preview card-interactive">
            <div className="section-head section-head-row">
              <div>
                <span className="section-eyebrow">Focus</span>
                <h2 className="section-title">Top 3 Priority Actions</h2>
              </div>
              <Link to="/inventory" className="btn-ghost">View all in Inventory →</Link>
            </div>
            <div className="priority-list">
              {topPriority.length ? (
                topPriority.map((action, index) => (
                  <div key={action.product + index} className="priority-item">
                    <span className="priority-rank">#{index + 1}</span>
                    <div>
                      <p className="priority-label">{action.product}</p>
                      <p className="priority-copy">{action.recommended_action}</p>
                    </div>
                  </div>
                ))
              ) : (
                <p className="priority-empty">No priority actions available yet. Refresh when more data is ready.</p>
              )}
            </div>
          </section>

          <section className="root-cause-card card-interactive">
            <div className="section-head section-head-row">
              <div>
                <span className="section-eyebrow">Diagnosis</span>
                <h2 className="section-title">Root Cause Analysis</h2>
              </div>
            </div>
            {rootCauseLoading ? (
              <div className="root-cause-loading">
                <Skeleton lines={4} />
                <p className="loading-text">Analyzing root causes…</p>
              </div>
            ) : rootCauseError ? (
              <p className="root-cause-error">{rootCauseError}</p>
            ) : rootCauseAnalysis?.insufficient_data ? (
              <div className="root-cause-insufficient">
                <div className="empty-state-icon">📊</div>
                <h3 className="empty-state-title">Need More Data</h3>
                <p className="empty-state-description">{rootCauseAnalysis.data_sufficiency_note}</p>
              </div>
            ) : (
              <div className="root-cause-list">
                {rootCauseAnalysis?.causes?.length > 0 ? (
                  rootCauseAnalysis.causes.map((cause, index) => (
                    <div key={`${cause.product}-${cause.cause_type}-${index}`} className="root-cause-item">
                      <div className="root-cause-header">
                        <div className="root-cause-title-group">
                          <h3 className="root-cause-title">{cause.title}</h3>
                          <span className={`severity-tag severity-${cause.severity.toLowerCase()}`}>
                            {cause.severity}
                          </span>
                        </div>
                        <div className="root-cause-meta">
                          <span className="confidence-tag">Confidence: {Math.round(cause.confidence * 100)}%</span>
                        </div>
                      </div>
                      <p className="root-cause-explanation">{cause.explanation}</p>
                      <div className="root-cause-metrics">
                        <div className="metric-item">
                          <span className="metric-label">Financial Impact</span>
                          <span className="metric-value">{formatCurrency(cause.financial_impact)}</span>
                        </div>
                        <div className="metric-item">
                          <span className="metric-label">Expected Recovery</span>
                          <span className="metric-value recovery">{formatCurrency(cause.expected_recovery)}</span>
                        </div>
                      </div>
                      <div className="root-cause-recommendation">
                        <span className="rec-label">Recommended Action:</span>
                        <p className="rec-text">{cause.recommended_action}</p>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="root-cause-empty">No root causes detected. Your business is in good shape!</p>
                )}
              </div>
            )}
          </section>

          {/* ── AI Action Planner ─────────────────────────────────────── */}
          <section className="action-planner-card card-interactive">
            <div className="section-head section-head-row">
              <div>
                <span className="section-eyebrow">Action Planner</span>
                <h2 className="section-title">Today's Tasks</h2>
              </div>
              {!actionPlanLoading && !actionPlanError && !actionPlan?.insufficient_data && actionPlan?.total_potential_savings > 0 && (
                <div className="action-planner-savings-badge">
                  <Zap size={13} />
                  Complete today's tasks to save ~{formatCurrency(actionPlan.total_potential_savings)}
                </div>
              )}
            </div>

            {actionPlanLoading ? (
              <div className="root-cause-loading">
                <Skeleton lines={4} />
                <p className="loading-text">Building your action plan…</p>
              </div>
            ) : actionPlanError ? (
              <p className="root-cause-error">{actionPlanError}</p>
            ) : actionPlan?.insufficient_data ? (
              <div className="root-cause-insufficient">
                <div className="empty-state-icon">📋</div>
                <h3 className="empty-state-title">Need More Data</h3>
                <p className="empty-state-description">{actionPlan.data_sufficiency_note}</p>
              </div>
            ) : (
              <>
                {/* Pending tasks */}
                <div className="action-task-list">
                  {actionPlan?.pending?.length > 0 ? (
                    actionPlan.pending.map((task) => (
                      <div key={task.task_id} className={`action-task-item priority-${task.priority.toLowerCase()}`}>
                        <button
                          className="action-task-checkbox"
                          onClick={() => handleCompleteTask(task.task_id)}
                          disabled={completingTaskId === task.task_id}
                          title="Mark complete"
                          aria-label={`Mark "${task.title}" as complete`}
                        >
                          {completingTaskId === task.task_id
                            ? <span className="action-task-spinner" />
                            : <Circle size={20} />
                          }
                        </button>
                        <div className="action-task-body">
                          <div className="action-task-header">
                            <h3 className="action-task-title">{task.title}</h3>
                            <span className={`action-priority-badge priority-badge-${task.priority.toLowerCase()}`}>{task.priority}</span>
                          </div>
                          <p className="action-task-benefit">{task.expected_benefit}</p>
                          <div className="action-task-meta">
                            <div className="action-task-metrics">
                              <div className="metric-item">
                                <span className="metric-label">Profit at risk</span>
                                <span className="metric-value">{formatCurrency(task.profit_risk)}</span>
                              </div>
                              <div className="metric-item">
                                <span className="metric-label">Expected saving</span>
                                <span className="metric-value recovery">{formatCurrency(task.expected_saving)}</span>
                              </div>
                            </div>
                            <div className="action-task-tags">
                              <span className="action-task-tag">
                                <Clock size={11} />
                                {task.estimated_time}
                              </span>
                              <span className="action-task-tag">
                                {task.difficulty}
                              </span>
                              <span className="confidence-tag">
                                {Math.round(task.confidence * 100)}% confidence
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="action-planner-all-done">
                      <CheckCircle2 size={32} className="all-done-icon" />
                      <p>All tasks complete — great work today!</p>
                    </div>
                  )}
                </div>

                {/* Completed tasks — collapsible */}
                {actionPlan?.completed?.length > 0 && (
                  <div className="action-completed-section">
                    <button
                      className="action-completed-toggle"
                      onClick={() => setShowCompleted(v => !v)}
                    >
                      {showCompleted ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      {showCompleted ? 'Hide' : 'Show'} completed ({actionPlan.completed.length})
                    </button>
                    {showCompleted && (
                      <div className="action-task-list action-completed-list">
                        {actionPlan.completed.map((task) => (
                          <div key={task.task_id} className="action-task-item action-task-done">
                            <button
                              className="action-task-checkbox done"
                              onClick={() => handleReopenTask(task.task_id)}
                              disabled={completingTaskId === task.task_id}
                              title="Mark as not done"
                              aria-label={`Reopen "${task.title}"`}
                            >
                              {completingTaskId === task.task_id
                                ? <span className="action-task-spinner" />
                                : <CheckCircle2 size={20} />
                              }
                            </button>
                            <div className="action-task-body">
                              <div className="action-task-header">
                                <h3 className="action-task-title done">{task.title}</h3>
                                <span className={`action-priority-badge priority-badge-${task.priority.toLowerCase()} done`}>{task.priority}</span>
                              </div>
                              {task.completed_at && (
                                <p className="action-task-completed-at">
                                  Completed {new Date(task.completed_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
                                </p>
                              )}
                              <div className="action-task-tags">
                                <span className="action-task-tag">
                                  {formatCurrency(task.expected_saving)} saved
                                </span>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </section>

          {/* ── Cash Flow Predictor ───────────────────────────────────── */}
          <section className="cash-flow-card card-interactive">
            <div className="section-head section-head-row">
              <div>
                <span className="section-eyebrow">Predictor</span>
                <h2 className="section-title">Cash Flow Forecast</h2>
              </div>
              {!cashFlowLoading && !cashFlowError && !cashFlow?.insufficient_data && cashFlow?.confidence != null && (
                <span className="confidence-tag">
                  {Math.round(cashFlow.confidence * 100)}% confidence
                </span>
              )}
            </div>

            {cashFlowLoading ? (
              <div className="root-cause-loading">
                <Skeleton lines={5} />
                <p className="loading-text">Projecting cash flow…</p>
              </div>
            ) : cashFlowError ? (
              <p className="root-cause-error">{cashFlowError}</p>
            ) : cashFlow?.insufficient_data ? (
              <div className="root-cause-insufficient">
                <div className="empty-state-icon">💰</div>
                <h3 className="empty-state-title">Need More Data</h3>
                <p className="empty-state-description">{cashFlow.data_sufficiency_note}</p>
              </div>
            ) : (
              <>
                {/* Current position + estimate disclaimer */}
                <div className="cf-position-row">
                  <div className="cf-position-block">
                    <span className="metric-label">
                      Current Cash Position
                      {cashFlow.is_estimate && <span className="cf-estimate-badge">estimate</span>}
                    </span>
                    <span className={`cf-position-value ${cashFlow.current_cash_position >= 0 ? 'positive' : 'negative'}`}>
                      {formatCurrency(cashFlow.current_cash_position)}
                    </span>
                    <span className="cf-daily-avg">
                      Avg {formatCurrency(cashFlow.daily_avg_net_cash)}/day · {cashFlow.trend_direction} trend
                    </span>
                  </div>
                  <div className="cf-projection-badges">
                    {cashFlow.projections?.map((p) => (
                      <div key={p.day} className="cf-projection-badge">
                        <span className="cf-proj-label">{p.label}</span>
                        <span className={`cf-proj-value ${p.projected_cash >= 0 ? 'positive' : 'negative'}`}>
                          {formatCurrency(p.projected_cash)}
                        </span>
                        <span className={`severity-tag severity-${p.risk_level === 'Healthy' ? 'low' : p.risk_level === 'Medium Risk' ? 'medium' : 'critical'}`}>
                          {p.risk_level}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Estimate disclaimer */}
                {cashFlow.is_estimate && cashFlow.position_basis && (
                  <div className="cf-disclaimer">
                    <Info size={12} />
                    <span>{cashFlow.position_basis}</span>
                  </div>
                )}

                {/* Chart: area chart of 30-day projected cash */}
                {cashFlow.chart_series?.length > 1 && (
                  <div className="cf-chart-wrap">
                    <ResponsiveContainer width="100%" height={200}>
                      <AreaChart
                        data={cashFlow.chart_series}
                        margin={{ top: 8, right: 4, left: 0, bottom: 0 }}
                      >
                        <defs>
                          <linearGradient id="cf-gradient-pos" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="rgba(61,171,168,0.35)" />
                            <stop offset="100%" stopColor="rgba(61,171,168,0.02)" />
                          </linearGradient>
                          <linearGradient id="cf-gradient-neg" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="rgba(212,101,90,0.25)" />
                            <stop offset="100%" stopColor="rgba(212,101,90,0.02)" />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
                        <XAxis
                          dataKey="label"
                          tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
                          interval={4}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
                          axisLine={false}
                          tickLine={false}
                          tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
                          width={46}
                        />
                        <Tooltip
                          contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '12px' }}
                          labelStyle={{ color: 'var(--text-muted)' }}
                          formatter={(value) => [formatCurrency(value), 'Projected Cash']}
                        />
                        <ReferenceLine y={0} stroke="var(--border)" strokeDasharray="4 3" />
                        <Area
                          type="monotone"
                          dataKey="projected_cash"
                          stroke="var(--accent)"
                          strokeWidth={2}
                          fill={cashFlow.current_cash_position >= 0 ? 'url(#cf-gradient-pos)' : 'url(#cf-gradient-neg)'}
                          dot={false}
                          activeDot={{ r: 4, fill: 'var(--accent)' }}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                    <p className="chart-meta">Projected cumulative cash position over next 30 days · linear trend extrapolation from {cashFlow.trailing_days}-day window</p>
                  </div>
                )}

                {/* Recommendations */}
                {cashFlow.recommendations?.length > 0 && (
                  <div className="cf-recommendations">
                    <h3 className="cf-rec-heading">Recommendations</h3>
                    <div className="cf-rec-list">
                      {cashFlow.recommendations.map((rec, i) => (
                        <div key={i} className="cf-rec-item">
                          <div className="cf-rec-header">
                            <h4 className="cf-rec-title">{rec.title}</h4>
                            <span className="cf-rec-impact">{formatCurrency(rec.financial_impact)}</span>
                          </div>
                          <p className="cf-rec-explanation">{rec.explanation}</p>
                          <span className="cf-rec-basis">{rec.impact_basis}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </section>
        </>
      )}
    </div>
  )
}
