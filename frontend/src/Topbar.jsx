import { Download } from 'lucide-react'

export default function Topbar({ title, healthStatus, reportLink }) {
  return (
    <div className="topbar">
      <div>
        <p className="topbar-label">{title}</p>
        <h2 className="topbar-title">{title}</h2>
      </div>
      <div className="topbar-actions">
        <span className={`status-pill ${healthStatus?.className ?? ''}`}>{healthStatus?.label ?? 'Unknown'}</span>
        <a href={reportLink} className="btn-ghost" download="business_diagnosis_report.pdf">
          <Download size={16} />
          Download Report
        </a>
      </div>
    </div>
  )
}
