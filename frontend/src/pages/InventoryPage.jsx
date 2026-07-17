import { Link } from 'react-router-dom'

export default function InventoryPage({ stopSelling, reorder }) {
  const hasNoData = !stopSelling && !reorder
  const hasEmptyLists = (!stopSelling || stopSelling.length === 0) && (!reorder || reorder.length === 0)

  return (
    <div className="inventory-page">
      <section className="priority-section">
        <div className="section-head">
          <span className="section-eyebrow">Inventory</span>
          <h2 className="section-title">Stop-Selling & Reorder</h2>
        </div>

        {hasNoData || hasEmptyLists ? (
          <div className="empty-state-card card-interactive">
            <div className="empty-state-content">
              <div className="empty-state-icon">📦</div>
              <h2 className="empty-state-title">No Inventory Data Yet</h2>
              <p className="empty-state-description">
                Upload your sales and inventory files to see which products need reordering and which ones you should consider discontinuing.
              </p>
              <Link to="/settings" className="btn-primary">
                Upload Your Data →
              </Link>
            </div>
          </div>
        ) : (
          <div className="report-grid">
            <div className="report-card card-interactive">
              <h3>Consider Discontinuing</h3>
              {stopSelling.map((s, i) => (
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
