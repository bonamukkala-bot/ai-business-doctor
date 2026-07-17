import { useState, useEffect, useRef } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import axios from 'axios'
import { useAuth } from './AuthContext.jsx'
import SignupLogin from './SignupLogin.jsx'
import DashboardLayout from './DashboardLayout.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import SalesPage from './pages/SalesPage.jsx'
import InventoryPage from './pages/InventoryPage.jsx'
import AdvisorsPage from './pages/AdvisorsPage.jsx'
import ConsultPage from './pages/ConsultPage.jsx'
import SettingsPage from './pages/SettingsPage.jsx'
import OnboardingWizard from './pages/OnboardingWizard.jsx'
import Skeleton from './components/Skeleton.jsx'
import './App.css'
import './styles/auth.css'
import { API_BASE_URL } from './config'

function App() {
  const [insights, setInsights] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [loaded, setLoaded] = useState(false)

  const [execSummary, setExecSummary] = useState(null)
  const [execLoading, setExecLoading] = useState(true)
  const [execError, setExecError] = useState(null)
  
  const [rootCauseAnalysis, setRootCauseAnalysis] = useState(null)
  const [rootCauseLoading, setRootCauseLoading] = useState(true)
  const [rootCauseError, setRootCauseError] = useState(null)

  const [actionPlan, setActionPlan] = useState(null)
  const [actionPlanLoading, setActionPlanLoading] = useState(true)
  const [actionPlanError, setActionPlanError] = useState(null)

  const [cashFlow, setCashFlow] = useState(null)
  const [cashFlowLoading, setCashFlowLoading] = useState(true)
  const [cashFlowError, setCashFlowError] = useState(null)

  const [inventoryOptimizer, setInventoryOptimizer] = useState(null)
  const [inventoryOptimizerLoading, setInventoryOptimizerLoading] = useState(true)
  const [inventoryOptimizerError, setInventoryOptimizerError] = useState(null)

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

  const { session, user, loading: authLoading, signOut } = useAuth()
  const onboardingComplete = user?.user_metadata?.onboarding_complete === true
  const lastModifiedRef = useRef(null)

  useEffect(() => {
    if (session?.access_token) {
      axios.defaults.headers.common.Authorization = `Bearer ${session.access_token}`
    } else {
      delete axios.defaults.headers.common.Authorization
    }
  }, [session])

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

    setRootCauseLoading(true)
    try {
      const rootCauseRes = await axios.get(`${API_BASE_URL}/api/root-cause-analysis`)
      setRootCauseAnalysis(rootCauseRes.data)
      setRootCauseError(null)
    } catch (err) {
      setRootCauseError('Root cause analysis unavailable — check backend logs.')
    } finally {
      setRootCauseLoading(false)
    }

    setActionPlanLoading(true)
    try {
      const actionPlanRes = await axios.get(`${API_BASE_URL}/api/action-plan`)
      setActionPlan(actionPlanRes.data)
      setActionPlanError(null)
    } catch (err) {
      setActionPlanError('Action plan unavailable — check backend logs.')
    } finally {
      setActionPlanLoading(false)
    }

    setCashFlowLoading(true)
    try {
      const cashFlowRes = await axios.get(`${API_BASE_URL}/api/cash-flow-prediction`)
      setCashFlow(cashFlowRes.data)
      setCashFlowError(null)
    } catch (err) {
      setCashFlowError('Cash flow prediction unavailable — check backend logs.')
    } finally {
      setCashFlowLoading(false)
    }

    setInventoryOptimizerLoading(true)
    try {
      const invOptRes = await axios.get(`${API_BASE_URL}/api/inventory-optimizer`)
      setInventoryOptimizer(invOptRes.data)
      setInventoryOptimizerError(null)
    } catch (err) {
      setInventoryOptimizerError('Inventory optimizer unavailable — check backend logs.')
    } finally {
      setInventoryOptimizerLoading(false)
    }
  }

  useEffect(() => {
    if (session) {
      refreshDashboard()
    }
  }, [session])

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

  if (authLoading) {
    return (
      <div className="scan-screen">
        <div className="scan-ring" />
        <p>Checking authentication…</p>
        <Skeleton lines={2} className="scan-skeleton" />
      </div>
    )
  }

  if (!session) {
    return <SignupLogin />
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
    <BrowserRouter>
      <div className={`app ${loaded ? 'app-loaded' : ''}`}>
        <Routes>
          <Route
            path="/"
            element={
              <DashboardLayout
                user={user}
                healthStatus={{
                  label: isProfitDown ? 'Attention Needed' : 'Stable',
                  className: isProfitDown ? 'critical' : 'healthy'
                }}
                reportLink={`${API_BASE_URL}/export-report`}
              />
            }
          >
            <Route index element={<Navigate to={onboardingComplete ? '/dashboard' : '/onboarding'} replace />} />
            <Route
              path="dashboard"
              element={
                onboardingComplete ? (
                  <DashboardPage
                    user={user}
                    insights={insights}
                    execSummary={execSummary}
                    execLoading={execLoading}
                    execError={execError}
                    healthScore={hsScore}
                    healthLabel={hsLabel}
                    healthReasons={hsReasons}
                    isProfitDown={isProfitDown}
                    rootCauseAnalysis={rootCauseAnalysis}
                    rootCauseLoading={rootCauseLoading}
                    rootCauseError={rootCauseError}
                    actionPlan={actionPlan}
                    actionPlanLoading={actionPlanLoading}
                    actionPlanError={actionPlanError}
                    onActionPlanChange={setActionPlan}
                    cashFlow={cashFlow}
                    cashFlowLoading={cashFlowLoading}
                    cashFlowError={cashFlowError}
                  />
                ) : (
                  <Navigate to="/onboarding" replace />
                )
              }
            />
            <Route
              path="sales"
              element={
                onboardingComplete ? (
                  <SalesPage
                    profitTrend={profit_trend}
                    profitAnalysis={profit_analysis}
                    rawSummary={raw_summary}
                    reportView={reportView}
                    setReportView={setReportView}
                    stopSelling={stop_selling}
                    reorder={reorder}
                  />
                ) : (
                  <Navigate to="/onboarding" replace />
                )
              }
            />
            <Route
              path="inventory"
              element={
                onboardingComplete ? (
                  <InventoryPage
                    stopSelling={stop_selling}
                    reorder={reorder}
                    inventoryOptimizer={inventoryOptimizer}
                    inventoryOptimizerLoading={inventoryOptimizerLoading}
                    inventoryOptimizerError={inventoryOptimizerError}
                  />
                ) : (
                  <Navigate to="/onboarding" replace />
                )
              }
            />
            <Route
              path="advisors"
              element={
                onboardingComplete ? (
                  <AdvisorsPage
                    advisorPanel={advisorPanel}
                    advisorLoading={advisorLoading}
                    advisorError={advisorError}
                    consultPanel={consultPanel}
                    simProduct={simProduct}
                    simDemand={simDemand}
                    simResult={simResult}
                    simLoading={simLoading}
                    products={products}
                    setSimProduct={setSimProduct}
                    setSimDemand={setSimDemand}
                    runSimulation={runSimulation}
                  />
                ) : (
                  <Navigate to="/onboarding" replace />
                )
              }
            />
            <Route
              path="consult"
              element={
                onboardingComplete ? (
                  <ConsultPage
                    chatHistory={chatHistory}
                    asking={asking}
                    question={question}
                    setQuestion={setQuestion}
                    handleAsk={handleAsk}
                    suggestedQuestions={suggestedQuestions}
                  />
                ) : (
                  <Navigate to="/onboarding" replace />
                )
              }
            />
            <Route
              path="settings"
              element={
                onboardingComplete ? (
                  <SettingsPage
                    dataStatus={dataStatus}
                    showUploadForm={showUploadForm}
                    connectionType={connectionType}
                    liveSalesPath={liveSalesPath}
                    liveInventoryPath={liveInventoryPath}
                    salesFile={salesFile}
                    inventoryFile={inventoryFile}
                    uploading={uploading}
                    uploadError={uploadError}
                    uploadSuccess={uploadSuccess}
                    handleUpload={handleUpload}
                    handleConnectLive={handleConnectLive}
                    handleDisconnectLive={handleDisconnectLive}
                    handleResetDemo={handleResetDemo}
                    setShowUploadForm={setShowUploadForm}
                    setConnectionType={setConnectionType}
                    setLiveSalesPath={setLiveSalesPath}
                    setLiveInventoryPath={setLiveInventoryPath}
                    setSalesFile={setSalesFile}
                    setInventoryFile={setInventoryFile}
                    user={user}
                    signOut={signOut}
                    getFilename={getFilename}
                    getRelativeTime={getRelativeTime}
                  />
                ) : (
                  <Navigate to="/onboarding" replace />
                )
              }
            />
          </Route>
          <Route path="onboarding" element={<OnboardingWizard user={user} onComplete={refreshDashboard} />} />
          <Route path="*" element={<Navigate to={onboardingComplete ? '/dashboard' : '/onboarding'} replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

export default App
