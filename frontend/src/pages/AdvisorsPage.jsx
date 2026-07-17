import Skeleton from '../components/Skeleton.jsx'

export default function AdvisorsPage({ advisorPanel, advisorLoading, advisorError, consultPanel, simProduct, simDemand, simResult, simLoading, products, setSimProduct, setSimDemand, runSimulation }) {
  return (
    <div className="advisors-page">
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
            {[1, 2, 3].map((i) => (
              <div key={i} className="advisor-card skeleton-advisor"><Skeleton lines={3} /></div>
            ))}
          </div>
        )}
        {advisorPanel && !advisorLoading && !advisorError && (
          <div className="advisors-grid">
            <div className="advisor-card finance card-interactive">
              <div className="advisor-icon">💳</div>
              <h3>Finance</h3>
              <p>{advisorPanel.finance_take}</p>
            </div>
            <div className="advisor-card operations card-interactive">
              <div className="advisor-icon">📦</div>
              <h3>Operations</h3>
              <p>{advisorPanel.operations_take}</p>
            </div>
            <div className="advisor-card marketing card-interactive">
              <div className="advisor-icon">📣</div>
              <h3>Marketing</h3>
              <p>{advisorPanel.marketing_take}</p>
            </div>
          </div>
        )}
        {!advisorPanel && !advisorLoading && !advisorError && (
          <p className="advisor-placeholder">Three specialist advisors ready — each grounded in your live business data.</p>
        )}
      </section>
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
              onChange={(e) => { setSimProduct(e.target.value); }}
            >
              <option value="">Select a product…</option>
              {products.map((p) => <option key={p} value={p}>{p}</option>)}
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
              onChange={(e) => { setSimDemand(Number(e.target.value)); }}
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
    </div>
  )
}
