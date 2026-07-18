import { Link } from 'react-router-dom'
import Skeleton from '../components/Skeleton.jsx'

function formatCurrency(value) {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits:0 }).format(value)
}

function CoverageBadge({ days }) {
  if (days === null || days === undefined) return null
  if (days >= 14) return <span className="severity-tag severity-low">{days}d coverage</span>
  if (days >= 7)  return <span className="severity-tag severity-medium">{days}d coverage</span>
  return <span className="severity-tag severity-critical">{days}d coverage</span>
}

const STRATEGY_SEVERITY = {
  flash_sale:        'critical',
  discount_campaign: 'high',
  buy2get1:          'medium',
  bundle:            'medium',
  cross_sell:        'low',
}

function StrategyBadge({ strategy, label }) {
  const sev = STRATEGY_SEVERITY[strategy] ?? 'low'
  return <span className={`severity-tag severity-${sev}`}>{label}</span>
}

export default function InventoryPage({
  stopSelling, reorder,
  inventoryOptimizer, inventoryOptimizerLoading, inventoryOptimizerError,
  deadInventory, deadInventoryLoading, deadInventoryError,
}) {
  const hasNoData = !stopSelling && !reorder
  const hasEmptyLists = (!stopSelling || stopSelling.length === 0) && (!reorder || reorder.length === 0)

  const actionableItems = inventoryOptimizer?.items?.filter(
    item => item.recommended_purchase_qty > 0 || item.estimated_savings > 0
  ) ?? []

  const deadItems = deadInventory?.items ?? []

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
                  {item.safety_stock_note && (
                    <p className="inv-optimizer-note">{item.safety_stock_note}</p>
                  )}
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

      <section className="dead-inv-section card-interactive">
        <div className="section-head section-head-row">
          <div>
            <span className="section-eyebrow">Recovery</span>
            <h2 className="section-title">Smart Dead Inventory Recovery</h2>
          </div>
          {!deadInventoryLoading && !deadInventoryError && !deadInventory?.insufficient_data
            && deadInventory?.total_capital_blocked > 0 && (
            <div className="dead-inv-blocked-pill">
              <span className="dead-inv-blocked-label">Capital blocked</span>
              <span className="dead-inv-blocked-value">{formatCurrency(deadInventory.total_capital_blocked)}</span>
            </div>
          )}
        </div>

        {deadInventoryLoading ? (
          <div className="root-cause-loading">
            <Skeleton lines={4} />
            <p className="loading-text">Scanning for dead inventory…</p>
          </div>
        ) : deadInventoryError ? (
          <p className="root-cause-error">{deadInventoryError}</p>
        ) : deadInventory?.insufficient_data ? (
          <div className="root-cause-insufficient">
            <div className="empty-state-icon">📦</div>
            <h3 className="empty-state-title">Need More Data</h3>
            <p className="empty-state-description">{deadInventory.data_sufficiency_note}</p>
          </div>
        ) : deadItems.length === 0 ? (
          <p className="root-cause-empty">
            No dead inventory detected across {deadInventory?.products_analyzed ?? '—'} products —
            everything sold within the last {deadInventory?.threshold_days ?? 14} days.
          </p>
        ) : (
          <>
            <p className="inv-optimizer-meta">
              Products with no sale for ≥{deadInventory.threshold_days} days ·
              {deadItems.length} product{deadItems.length !== 1 ? 's' : ''} flagged out of {deadInventory.products_analyzed} ·
              Strategies based on real price, margin, and category data
            </p>
            <div className="dead-inv-list">
              {deadItems.map((item) => (
                <div key={item.product} className="dead-inv-item">
                  <div className="dead-inv-header">
                    <div className="dead-inv-title-group">
                      <h3 className="dead-inv-product">{item.product}</h3>
                      {item.category && (
                        <span className="action-task-tag">{item.category}</span>
                      )}
                      <span className={`severity-tag ${item.never_sold ? 'severity-critical' : item.days_without_sale >= 45 ? 'severity-critical' : 'severity-high'}`}>
                        {item.days_without_sale_label}{item.never_sold ? '' : ' days idle'}
                      </span>
                    </div>
                    <StrategyBadge strategy={item.strategy} label={item.strategy_label} />
                  </div>

                  <div className="dead-inv-metrics">
                    <div className="metric-item">
                      <span className="metric-label">Current Stock</span>
                      <span className="metric-value">{item.current_stock} units</span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-label">Capital Blocked</span>
                      <span className="metric-value">{formatCurrency(item.capital_blocked)}</span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-label">Unit Price / Cost</span>
                      <span className="metric-value">{formatCurrency(item.unit_price)} / {formatCurrency(item.unit_cost)}</span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-label">Margin</span>
                      <span className="metric-value">{(item.margin_ratio * 100).toFixed(1)}%</span>
                    </div>
                  </div>

                  <div className="dead-inv-strategy">
                    <span className="rec-label">Recommended Strategy:</span>
                    <p className="rec-text">{item.strategy_description}</p>
                    <p className="dead-inv-rule-basis">{item.strategy_rule_basis}</p>
                  </div>

                  <div className="dead-inv-estimates">
                    <div className="dead-inv-estimate-item">
                      <span className="metric-label">Expected Sales Increase</span>
                      <span className="dead-inv-estimate-value">{item.expected_sales_increase}</span>
                    </div>
                    <div className="dead-inv-estimate-item">
                      <span className="metric-label">Expected Profit Recovery</span>
                      <span className="dead-inv-estimate-value recovery">{item.expected_profit_recovery}</span>
                    </div>
                    <div className="dead-inv-estimate-item">
                      <span className="metric-label">Est. Time to Clear Stock</span>
                      <span className="dead-inv-estimate-value">{item.estimated_recovery_time}</span>
                    </div>
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