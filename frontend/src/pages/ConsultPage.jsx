import Skeleton from '../components/Skeleton.jsx'

export default function ConsultPage({ chatHistory, asking, question, setQuestion, handleAsk, suggestedQuestions }) {
  return (
    <div className="consult-page">
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
        <form className="chat-form" onSubmit={(e) => { e.preventDefault(); handleAsk(); }}>
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Type your question…"
            disabled={asking}
          />
          <button type="submit" className="btn-primary" disabled={asking || !question.trim()}>Ask</button>
        </form>
      </section>
    </div>
  )
}
