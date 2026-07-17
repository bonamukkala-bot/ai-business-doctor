import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

export default function SalesPage({ profitTrend, profitAnalysis, rawSummary, reportView, setReportView, stopSelling, reorder }) {
  return (
    <div className="sales-page">
      <section className="profit-chart-card card-interactive">
        <span className="section-eyebrow">Trend</span>
        <h2 className="section-title">30-Day Profit</h2>
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={profitTrend}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip formatter={(value) => [`Rs ${value}`, 'Profit']} />
              <Line type="monotone" dataKey="profit" stroke="#3DABA8" strokeWidth={2.5} dot={false} activeDot={{ r: 4, fill: '#3DABA8' }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>
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
            >Raw</button>
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
                {rawSummary.map((row, i) => (
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
              <p className="report-summary">{profitAnalysis.summary}</p>
              {profitAnalysis.top_drivers.map((d, i) => (
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
