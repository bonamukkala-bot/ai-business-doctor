import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import * as XLSX from 'xlsx'
import { ShoppingBag, Coffee, Pill, Scissors, Truck, Box, UploadCloud, FileText, Database } from 'lucide-react'
import { supabase } from '../lib/supabaseClient.js'
import { API_BASE_URL } from '../config'

const BUSINESS_TYPES = [
  { value: 'Retail', label: 'Retail / Kirana', icon: ShoppingBag },
  { value: 'Restaurant', label: 'Restaurant', icon: Coffee },
  { value: 'Pharmacy', label: 'Pharmacy', icon: Pill },
  { value: 'Salon/Services', label: 'Salon / Services', icon: Scissors },
  { value: 'Wholesale', label: 'Wholesale', icon: Truck },
  { value: 'Other', label: 'Other', icon: Box },
]

const DATA_SOURCES = [
  {
    value: 'upload',
    title: 'Upload my sales file',
    description: 'Drag and drop a sales CSV or Excel file and map columns to your business fields.',
    icon: UploadCloud,
  },
  {
    value: 'manual',
    title: 'Enter my numbers manually',
    description: 'Type your daily sales rows into a simple form and start diagnostics fast.',
    icon: FileText,
  },
  {
    value: 'demo',
    title: 'Try with demo data',
    description: 'Use example business data to explore the dashboard instantly.',
    icon: Database,
  },
]

const FIELD_OPTIONS = ['skip', 'date', 'product', 'units_sold', 'revenue', 'profit']
const REQUIRED_FIELDS = ['date', 'product', 'units_sold', 'revenue', 'profit']

function guessMapping(header) {
  const text = String(header || '').toLowerCase()
  if (/date|day/.test(text)) return 'date'
  if (/product|item|sku|name/.test(text)) return 'product'
  if (/unit|qty|quantity|sold/.test(text)) return 'units_sold'
  if (/revenue|sales|amount|price/.test(text)) return 'revenue'
  if (/profit|margin/.test(text)) return 'profit'
  return 'skip'
}

function defaultColumnMap(headers) {
  return headers.reduce((map, header) => ({
    ...map,
    [header]: guessMapping(header),
  }), {})
}

function buildCsvFromRows(rows) {
  const csvRows = [REQUIRED_FIELDS.join(',')]
  rows.forEach((row) => {
    const values = REQUIRED_FIELDS.map((field) => {
      const value = row[field]
      if (value === undefined || value === null) return ''
      return String(value).replace(/"/g, '""')
    })
    csvRows.push(values.map((value) => `"${value}"`).join(','))
  })
  return new Blob([csvRows.join('\n')], { type: 'text/csv;charset=UTF-8' })
}

async function parseFile(file) {
  const buffer = await file.arrayBuffer()
  const workbook = XLSX.read(buffer, { type: 'array' })
  const sheet = workbook.Sheets[workbook.SheetNames[0]]
  const rows = XLSX.utils.sheet_to_json(sheet, { header: 1, blankrows: false })
  const headers = (rows[0] || []).map((header) => String(header || '').trim())
  const dataRows = rows.slice(1).map((row) => {
    const record = {}
    headers.forEach((header, index) => {
      record[header] = row?.[index] ?? ''
    })
    return record
  })
  return { headers, dataRows }
}

async function buildStandardizedSalesFile(file, headers, columnMap) {
  const { dataRows } = await parseFile(file)
  const normalized = dataRows.map((row) => {
    const normalizedRow = {
      date: '',
      product: '',
      units_sold: 0,
      revenue: 0,
      profit: 0,
    }
    Object.entries(columnMap).forEach(([header, field]) => {
      if (!header || field === 'skip') return
      normalizedRow[field] = row[header] ?? ''
    })
    return normalizedRow
  })
  const csvBlob = buildCsvFromRows(normalized)
  return new File([csvBlob], 'sales_data.csv', { type: 'text/csv' })
}

export default function OnboardingWizard({ user, onComplete }) {
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  const [businessType, setBusinessType] = useState(user?.user_metadata?.business_type || 'Retail')
  const [source, setSource] = useState('demo')
  const [uploadedFile, setUploadedFile] = useState(null)
  const [fileHeaders, setFileHeaders] = useState([])
  const [parsedRows, setParsedRows] = useState([])
  const [columnMap, setColumnMap] = useState({})
  const [manualRows, setManualRows] = useState(
    Array.from({ length: 5 }, () => ({ date: '', product: '', units_sold: '', revenue: '', profit: '' }))
  )
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [activeDrag, setActiveDrag] = useState(false)

  const mappedFields = useMemo(
    () => Object.values(columnMap).filter((field) => field && field !== 'skip'),
    [columnMap]
  )

  const missingRequired = REQUIRED_FIELDS.filter((field) => !mappedFields.includes(field))

  const parsedSummary = useMemo(() => {
    if (source === 'upload' && parsedRows.length > 0) {
      const dateField = Object.entries(columnMap).find(([, field]) => field === 'date')?.[0]
      if (!dateField) return { rows: parsedRows.length, days: null }
      const uniqueDays = new Set(parsedRows.map((row) => String(row[dateField] || '').trim()).filter(Boolean))
      return { rows: parsedRows.length, days: uniqueDays.size }
    }
    if (source === 'manual') {
      const validRows = manualRows.filter((row) => row.date.trim() && row.product.trim())
      const uniqueDays = new Set(validRows.map((row) => row.date.trim()))
      return { rows: validRows.length, days: uniqueDays.size }
    }
    return { rows: 0, days: 0 }
  }, [source, parsedRows, columnMap, manualRows])

  const handleFileInput = async (file) => {
    if (!file) return
    try {
      setError(null)
      const { headers, dataRows } = await parseFile(file)
      setUploadedFile(file)
      setFileHeaders(headers)
      setParsedRows(dataRows)
      setColumnMap(defaultColumnMap(headers))
    } catch (e) {
      setError('Unable to parse the selected file. Please upload a valid CSV or Excel sales file.')
      setUploadedFile(null)
      setFileHeaders([])
      setParsedRows([])
      setColumnMap({})
    }
  }

  const handleDrop = async (event) => {
    event.preventDefault()
    setActiveDrag(false)
    const file = event.dataTransfer.files?.[0]
    if (file) {
      await handleFileInput(file)
    }
  }

  const handleSelectFile = async (event) => {
    const file = event.target.files?.[0]
    if (file) {
      await handleFileInput(file)
    }
  }

  const updateColumnMap = (header, value) => {
    setColumnMap((current) => ({ ...current, [header]: value }))
  }

  const handleManualChange = (index, field, value) => {
    setManualRows((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, [field]: value } : row))
  }

  const addManualRow = () => {
    setManualRows((rows) => [...rows, { date: '', product: '', units_sold: '', revenue: '', profit: '' }])
  }

  const hasManualValidRows = useMemo(() => {
    return manualRows.filter((row) => row.date.trim() && row.product.trim()).length >= 5
  }, [manualRows])

  const canAdvance = () => {
    if (step === 1) return Boolean(businessType)
    if (step === 2) return Boolean(source)
    if (step === 3) {
      if (source === 'upload') return Boolean(uploadedFile)
      if (source === 'manual') return hasManualValidRows
      return source === 'demo'
    }
    return true
  }

  const handleContinue = () => {
    if (!canAdvance()) {
      setError('Please complete this step before continuing.')
      return
    }
    setError(null)
    if (step === 2 && source === 'demo') {
      setStep(4)
      return
    }
    setStep((value) => Math.min(4, value + 1))
  }

  const handleBack = () => {
    setError(null)
    setStep((value) => Math.max(1, value - 1))
  }

  const buildUploadPayload = async () => {
    if (!uploadedFile) return null
    return await buildStandardizedSalesFile(uploadedFile, fileHeaders, columnMap)
  }

  const handleConfirm = async () => {
    setError(null)
    setSubmitting(true)

    try {
      const payload = new FormData()
      payload.append('business_type', businessType)
      payload.append('shop_name', user?.user_metadata?.shop_name || user?.email?.split('@')[0] || '')
      payload.append('source', source)

      if (source === 'upload') {
        if (!uploadedFile) throw new Error('Please upload a sales file before continuing.')
        const standardizedFile = await buildUploadPayload()
        if (!standardizedFile) throw new Error('Could not process the sales file.')
        payload.append('sales_file', standardizedFile)
      }

      if (source === 'manual') {
        const validRows = manualRows.filter((row) => row.date.trim() && row.product.trim())
        if (validRows.length < 5) {
          throw new Error('Please provide at least 5 valid manual rows.')
        }
        payload.append('manual_rows', JSON.stringify(validRows))
      }

      const response = await axios.post(`${API_BASE_URL}/onboarding/complete`, payload, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })

      await supabase.auth.updateUser({
        data: {
          business_type: businessType,
          onboarding_complete: true,
        },
      })

      if (onComplete) {
        await onComplete()
      }

      navigate('/dashboard')
    } catch (err) {
      const message = err?.response?.data?.detail || err.message || 'Failed to complete onboarding. Please try again.'
      setError(Array.isArray(message) ? message.join(', ') : String(message))
    } finally {
      setSubmitting(false)
    }
  }

  const stepTitles = [
    'Business type',
    'Data source',
    'Upload or enter sales',
    'Review and confirm',
  ]

  return (
    <div className="onboarding-screen">
      <div className="onboarding-card">
        <div className="onboarding-top">
          <div>
            <p className="section-eyebrow">Getting started</p>
            <h1>Tell us about your business</h1>
            <p className="onboarding-copy">Complete these 4 quick steps once to unlock your dashboard.</p>
          </div>
          <div className="step-pill">Step {step} of 4</div>
        </div>

        <div className="onboarding-step-label">{stepTitles[step - 1]}</div>

        {step === 1 && (
          <div className="onboarding-grid">
            {BUSINESS_TYPES.map((type) => {
              const Icon = type.icon
              return (
                <button
                  key={type.value}
                  type="button"
                  className={`business-card ${businessType === type.value ? 'selected' : ''}`}
                  onClick={() => setBusinessType(type.value)}
                >
                  <div className="business-card-icon"><Icon size={20} /></div>
                  <div>
                    <div className="business-card-title">{type.label}</div>
                    {type.description ? <p className="business-card-copy">{type.description}</p> : null}
                  </div>
                </button>
              )
            })}
          </div>
        )}

        {step === 2 && (
          <div className="onboarding-grid onboarding-source-grid">
            {DATA_SOURCES.map((option) => {
              const Icon = option.icon
              return (
                <button
                  key={option.value}
                  type="button"
                  className={`source-card ${source === option.value ? 'selected' : ''}`}
                  onClick={() => setSource(option.value)}
                >
                  <div className="source-icon"><Icon size={24} /></div>
                  <h3>{option.title}</h3>
                  <p>{option.description}</p>
                </button>
              )
            })}
          </div>
        )}

        {step === 3 && source === 'upload' && (
          <div className="upload-step-card">
            <div
              className={`upload-dropzone ${activeDrag ? 'active' : ''}`}
              onDrop={handleDrop}
              onDragOver={(e) => { e.preventDefault(); setActiveDrag(true) }}
              onDragLeave={() => setActiveDrag(false)}
            >
              <div className="upload-zone-icon"><UploadCloud size={32} /></div>
              <p>{uploadedFile ? uploadedFile.name : 'Drag & drop your sales CSV/XLSX file here'}</p>
              <p className="upload-zone-hint">Or click to browse for a file with sales rows.</p>
              <input type="file" accept=".csv,.xlsx,.xls" className="upload-input" onChange={handleSelectFile} />
            </div>

            {fileHeaders.length > 0 && (
              <div className="mapping-card">
                <h3>Map your column headers</h3>
                <p className="mapping-copy">Match your file columns to the fields we need for analysis.</p>
                <div className="mapping-list">
                  {fileHeaders.map((header) => (
                    <label key={header} className="mapping-row">
                      <span>{header}</span>
                      <select value={columnMap[header] || 'skip'} onChange={(e) => updateColumnMap(header, e.target.value)}>
                        {FIELD_OPTIONS.map((option) => (
                          <option key={option} value={option}>{option === 'skip' ? 'Skip' : option.replace('_', ' ')}</option>
                        ))}
                      </select>
                    </label>
                  ))}
                </div>
                {missingRequired.length > 0 && (
                  <p className="field-warning">For best insights, map all fields: {missingRequired.join(', ')}.</p>
                )}
              </div>
            )}
          </div>
        )}

        {step === 3 && source === 'manual' && (
          <div className="manual-step-card">
            <p className="manual-copy">Add at least 5 days of sales data to build a meaningful view.</p>
            <div className="manual-grid">
              <div className="manual-header">Date</div>
              <div className="manual-header">Product</div>
              <div className="manual-header">Units sold</div>
              <div className="manual-header">Revenue</div>
              <div className="manual-header">Profit</div>
            </div>
            {manualRows.map((row, index) => (
              <div key={index} className="manual-grid manual-row">
                <input type="date" value={row.date} onChange={(e) => handleManualChange(index, 'date', e.target.value)} />
                <input type="text" value={row.product} onChange={(e) => handleManualChange(index, 'product', e.target.value)} placeholder="Product name" />
                <input type="number" value={row.units_sold} onChange={(e) => handleManualChange(index, 'units_sold', e.target.value)} min="0" />
                <input type="number" value={row.revenue} onChange={(e) => handleManualChange(index, 'revenue', e.target.value)} min="0" step="0.01" />
                <input type="number" value={row.profit} onChange={(e) => handleManualChange(index, 'profit', e.target.value)} min="0" step="0.01" />
              </div>
            ))}
            <button type="button" className="btn-ghost" onClick={addManualRow}>Add another day</button>
            {!hasManualValidRows && <p className="field-warning">Please enter at least 5 valid rows with a date and product.</p>}
          </div>
        )}

        {step === 3 && source === 'demo' && (
          <div className="demo-step-card">
            <h3>Demo data selected</h3>
            <p>We will use curated example sales and inventory data so your dashboard is ready immediately.</p>
          </div>
        )}

        {step === 4 && (
          <div className="summary-card">
            <h3>Ready to start diagnosing your business</h3>
            <div className="summary-row">
              <span>Business type</span>
              <strong>{businessType}</strong>
            </div>
            <div className="summary-row">
              <span>Data source</span>
              <strong>{DATA_SOURCES.find((option) => option.value === source)?.title}</strong>
            </div>
            {source !== 'demo' ? (
              <>
                <div className="summary-row">
                  <span>Rows detected</span>
                  <strong>{parsedSummary.rows}</strong>
                </div>
                <div className="summary-row">
                  <span>Days of data</span>
                  <strong>{parsedSummary.days ?? 'Unknown'}</strong>
                </div>
              </>
            ) : (
              <div className="summary-row">
                <span>Data set</span>
                <strong>Demo sales sample</strong>
              </div>
            )}
            <p className="summary-copy">Once confirmed, we will save your business type and sales data, then take you to the dashboard.</p>
          </div>
        )}

        {error && <div className="auth-banner error-banner">{error}</div>}

        <div className="onboarding-actions">
          {step > 1 && (
            <button type="button" className="btn-ghost" onClick={handleBack} disabled={submitting}>Back</button>
          )}
          {step < 4 ? (
            <button type="button" className="btn-primary" onClick={handleContinue} disabled={!canAdvance() || submitting}>
              Continue
            </button>
          ) : (
            <button type="button" className="btn-primary" onClick={handleConfirm} disabled={submitting}>
              {submitting ? 'Saving…' : 'Confirm and Start'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
