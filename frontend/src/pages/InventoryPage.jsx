import { Link } from 'react-router-dom'
import Skeleton from '../components/Skeleton.jsx'

function formatCurrency(value) {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value)
}

function CoverageBadge({ days }) {
  // Mirror the severity-tag colour logic used throughout the app
  if (days === null || days === undefined) return null
  if (days >= 14) return <span className="severity-tag severity-low">{days}d coverage</span>
  if (days >= 7)  return <span className="severity-tag severity-medium">{days}d coverage</span>
  return <span className="severity-tag severity-critical">{days}d coverage</span>
}

export default function InventoryPage({ stopSelling, reorder, inventoryOptimizer, inventoryOptimizerLoading, inventoryOptimizerError }) {
  const hasNoData = !stopSelling && !reorder
  const hasEmptyLists = (!stopSelling || stopSelling.length === 0) && (!reorder || reorder.length === 0)

  // Only show items that actually need a purchase (buy > 0) or have a savings figure
  const actionableItems = inventoryOptimizer?.items?.filter(
    item => item.recommended_purchase_qty > 0 || item.estimated_savings > 0
  ) ?? []

  return (
    <div className="inventory-page">
      {/* ── Existing Stop-Selling & Reorder section — UNTOUCHED ── */}
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

      {/* ── NEW: AI Inventory Optimizer section ── */}
      <section className="inv-optimizer-section card-interactive">
        <div className="section-head section-head-row">
          <div>
            <span className="section-eyebrow">Optimizer</span>
            <h2 className="section-title">AI Purchase Planner</h2>
          </div>
          {!inventoryOptimizerLoading && !inventoryOptimizerError && !inventoryOptimizer?.insufficient_data
            && inventoryOptimizer?.total_recommended_spend > 0 && (
            <div className="inv-optimizer-totals">
              <div className="inv-total-pill">
                <span className="inv-total-label">Recommended spend</span>
                <span className="inv-total-value spend">{formatCurrency(inventoryOptimizer.total_recommended_spend)}</span>
              </div>
              {inventoryOptimizer.total_estimated_savings > 0 && (
                <div className="inv-total-pill">
                  <span className="inv-total-label">Savings protected</span>
                  <span className="inv-total-value savings">{formatCurrency(inventoryOptimizer.total_estimated_savings)}</span>
                </div>
              )}
            </div>
          )}
        </div>

        {inventoryOptimizerLoading ? (
          <div className="root-cause-loading">
            <Skeleton lines={5} />
            <p className="loading-text">Calculating optimal purchase quantities…</p>
          </div>
        ) : inventoryOptimizerError ? (
          <p className="root-cause-error">{inventoryOptimizerError}</p>
        ) : inventoryOptimizer?.insufficient_data ? (
          <div className="root-cause-insufficient">
            <div className="empty-state-icon">📊</div>
            <h3 className="empty-state-title">Need More Data</h3>
            <p className="empty-state-description">{inventoryOptimizer.data_sufficiency_note}</p>
          </div>
        ) : actionableItems.length === 0 ? (
          <p className="root-cause-empty">All products are well-stocked for the next {inventoryOptimizer?.coverage_target_days ?? 14} days — no purchases needed right now.</p>
        ) : (
          <>
            <p className="inv-optimizer-meta">
              Based on {inventoryOptimizer.trailing_days}-day demand history · {inventoryOptimizer.coverage_target_days}-day planning horizon ·
              Safety factor {inventoryOptimizer.safety_factor} (z-score for ~85% service level)
            </p>
            <div className="inv-optimizer-list">
              {actionableItems.map((item) => (
                <div key={item.product} className="inv-optimizer-item">
                  {/* Header row: product name + coverage badge */}
                  <div className="inv-optimizer-header">
                    <div className="inv-optimizer-title-group">
                      <h3 className="inv-optimizer-product">{item.product}</h3>
                      <CoverageBadge days={item.stock_coverage_days === 999 ? null : item.stock_coverage_days} />
                    </div>
                    {item.estimated_savings > 0 && (
                      <span className="inv-optimizer-savings-badge">
                        Saves {formatCurrency(item.estimated_savings)}
                      </span>
                    )}
                  </div>

                  {/* Key metrics grid — reuses .metric-item/.metric-label/.metric-value */}
                  <div className="inv-optimizer-metrics">
                    <div className="metric-item">
                      <span className="metric-label">Current Stock</span>
                      <span className="metric-value">{item.current_stock} units</span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-label">Daily Demand</span>
                      <span className="metric-value">{item.daily_avg_demand} units</span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-label">Expected Demand ({inventoryOptimizer.coverage_target_days}d)</span>
                      <span className="metric-value">{item.expected_demand} units</span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-label">Safety Stock</span>
                      <span className="metric-value">
                        {item.safety_stock != null ? `${item.safety_stock} units` : 'N/A'}
                      </span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-label">Buy Quantity</span>
                      <span className="metric-value recovery">{item.recommended_purchase_qty} units</span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-label">Est. Cost</span>
                      <span className="metric-value">{formatCurrency(item.estimated_cost)}</span>
                    </div>
                  </div>

                  {/* Safety stock note when variability data was insufficient */}
                  {item.safety_stock_note && (
                    <p className="inv-optimizer-note">{item.safety_stock_note}</p>
                  )}

                  {/* Plain-English explanation */}
                  <div className="root-cause-recommendation">
                    <span className="rec-label">Why:</span>
                    <p className="rec-text">{item.explanation}</p>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </section>
    </div>
  )
}
