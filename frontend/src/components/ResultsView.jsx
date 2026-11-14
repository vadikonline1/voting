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

function QuestionCard({ question }) {
  return (
    <div className="results-question">
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
  );
}

export default function ResultsView({ results, title = true }) {
  if (!results) return null;

  const isOpen = results.status === "open";
  // questions grouped by chestiune; falls back to the flat list
  const groups = results.chestiuni || [{ title: "", questions: results.questions || [] }];
  const hasQuestions = groups.some((g) => (g.questions || []).length > 0);

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

      {results.chestiune && (
        <section className="dashboard-chestiune">
          <span className="eyebrow">Chestiunea propusă spre vot</span>
          <p>{results.chestiune}</p>
        </section>
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

      {!hasQuestions && <p className="muted">Nu există întrebări configurate.</p>}

      {groups.map((group, index) => (
        <section key={index} className="results-group">
          {group.title && (
            <div className="results-group-title">
              <span className="results-group-label">Chestiunea</span>
              <span>{group.title}</span>
            </div>
          )}
          {(group.questions || []).map((question) => (
            <QuestionCard key={question.id} question={question} />
          ))}
        </section>
      ))}
    </div>
  );
}
