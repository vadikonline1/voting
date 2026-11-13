function optionKind(option) {
  const value = String(option || "").trim().toLowerCase();
  if (value.startsWith("pentru") || value === "da" || value === "pro") return "for";
  if (value.startsWith("împotriv") || value.startsWith("impotriv") || value === "nu" || value === "contra") {
    return "against";
  }
  return "neutral";
}

function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("ro-RO");
}

export default function ResultsView({ results, title = true }) {
  if (!results) return null;

  const isOpen = results.status === "open";

  return (
    <div className="results-view">
      {title && (
        <div className="results-heading">
          <h2>{results.title}</h2>
          <p className="muted">
            APC nr. {results.nr_apc || "—"} · {results.str_apc || "—"} · {results.oras || "—"}
          </p>
        </div>
      )}

      <div className="results-summary">
        <div className="stat-card">
          <span className="stat-value">{results.total_votes}</span>
          <span className="stat-label">voturi exprimate</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{results.participation_percent}%</span>
          <span className="stat-label">
            participare ({results.total_votes}/{results.total_tokens})
          </span>
        </div>
        <div className="stat-card">
          <span className={`status-pill ${isOpen ? "open" : "closed"}`}>
            {isOpen ? "Votare în curs" : "Votare încheiată"}
          </span>
          <span className="stat-label">
            actualizat {formatTime(results.generated_at)}
          </span>
        </div>
      </div>

      {(results.questions || []).length === 0 && (
        <p className="muted">Nu există întrebări configurate.</p>
      )}

      {(results.questions || []).map((question) => (
        <div key={question.id} className="results-question">
          <h4>
            {question.number}. {question.text}
          </h4>
          <div className="result-bars">
            {(question.options || []).map((option) => (
              <div key={option.option} className="result-bar-row">
                <span className="result-bar-label">{option.option}</span>
                <div className="result-bar-track">
                  <div
                    className={`result-bar-fill ${optionKind(option.option)}`}
                    style={{ width: `${Math.max(0, Math.min(100, option.percent))}%` }}
                  />
                </div>
                <span className="result-bar-value">
                  <strong>{option.percent}%</strong>{" "}
                  <span className="muted">({option.count})</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
