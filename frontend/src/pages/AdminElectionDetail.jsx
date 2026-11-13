import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api";

function parseBulkRows(text) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const parts = line.split(";").map((p) => p.trim());
      const [nume_prenume = "", phone = "", str_locatar = "", email = "", nr_proprietate = ""] = parts;
      return { nume_prenume, phone, str_locatar, email, nr_proprietate };
    });
}

export default function AdminElectionDetail() {
  const { id } = useParams();
  const [tab, setTab] = useState("voters");
  const [checklistData, setChecklistData] = useState(null);
  const [resultsData, setResultsData] = useState(null);
  const [bulkText, setBulkText] = useState("");
  const [blankCount, setBlankCount] = useState(5);
  const [generated, setGenerated] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function loadChecklist() {
    api.checklist(id).then(setChecklistData).catch((e) => setError(e.message));
  }

  useEffect(() => {
    loadChecklist();
    api.results(id).then(setResultsData).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleGenerateRows(e) {
    e.preventDefault();
    const rows = parseBulkRows(bulkText);
    if (rows.length === 0) {
      setError("Introdu cel puțin un rând cu datele unui proprietar.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const res = await api.generateTokens({ election_id: Number(id), rows });
      setGenerated(res.tokens);
      setBulkText("");
      loadChecklist();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleGenerateBlank(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api.generateTokens({ election_id: Number(id), count: Number(blankCount) });
      setGenerated(res.tokens);
      loadChecklist();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function copyAllLinks() {
    if (!generated) return;
    const text = generated.map((t) => `${t.nume_prenume || t.id}: ${t.url}`).join("\n");
    navigator.clipboard.writeText(text);
  }

  return (
    <div>
      <p>
        <Link to="/admin">← Înapoi la lista de voturi</Link>
      </p>
      <h2>{checklistData ? checklistData.election_title : "..."}</h2>

      <div className="tabs">
        <button className={tab === "voters" ? "tab active" : "tab"} onClick={() => setTab("voters")}>
          Link-uri de vot &amp; checklist
        </button>
        <button className={tab === "results" ? "tab active" : "tab"} onClick={() => setTab("results")}>
          Rezultate
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {tab === "voters" && (
        <div>
          <form className="card" onSubmit={handleGenerateRows}>
            <h3>Generează link-uri cu datele proprietarilor</h3>
            <p className="muted">
              Un proprietar pe rând, câmpuri separate prin punct și virgulă (;):<br />
              <code>Nume Prenume; telefon; adresa de corespondență; email; nr. proprietate</code>
            </p>
            <label className="field">
              <textarea
                rows={6}
                value={bulkText}
                onChange={(e) => setBulkText(e.target.value)}
                placeholder={"Ion Popescu; 069111222; str. Exemplu 1 ap. 5; ion@exemplu.com; 5\nMaria Ionescu; 069333444; str. Exemplu 1 ap. 7; ; 7"}
              />
            </label>
            <button className="btn btn-primary" type="submit" disabled={busy}>
              {busy ? "Se generează..." : "Generează link-uri personalizate"}
            </button>
          </form>

          <form className="card" onSubmit={handleGenerateBlank}>
            <h3>Sau: generează link-uri goale (completezi datele mai târziu)</h3>
            <label className="field">
              <span>Număr de link-uri goale</span>
              <input type="number" min="1" max="5000" value={blankCount} onChange={(e) => setBlankCount(e.target.value)} />
            </label>
            <button className="btn" type="submit" disabled={busy}>
              Generează goale
            </button>
          </form>

          {generated && (
            <div className="card">
              <div className="actions-row">
                <h3>{generated.length} link-uri generate</h3>
                <button className="btn" onClick={copyAllLinks}>
                  Copiază toate link-urile
                </button>
              </div>
              <ul className="link-list">
                {generated.map((t) => (
                  <li key={t.id}>
                    <strong>{t.nume_prenume || "(fără nume)"}</strong>{" "}
                    <a href={t.url} target="_blank" rel="noreferrer">
                      {t.url}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="card">
            <div className="actions-row">
              <h3>
                Checklist votare {checklistData && `(${checklistData.voted}/${checklistData.total} au votat)`}
              </h3>
              <div className="actions-row">
                <a className="btn" href={api.tokensCsvUrl(id)}>
                  Export CSV
                </a>
                <button className="btn" onClick={loadChecklist}>
                  Reîmprospătează
                </button>
              </div>
            </div>
            <table className="checklist-table">
              <thead>
                <tr>
                  <th>Nume</th>
                  <th>Telefon</th>
                  <th>Nr. proprietate</th>
                  <th>Email</th>
                  <th>Link</th>
                  <th>A votat?</th>
                  <th>Data votării</th>
                </tr>
              </thead>
              <tbody>
                {checklistData &&
                  checklistData.rows.map((r) => (
                    <tr key={r.token_id}>
                      <td>{r.nume_prenume || "—"}</td>
                      <td>{r.phone || "—"}</td>
                      <td>{r.nr_proprietate || "—"}</td>
                      <td>{r.email || "—"}</td>
                      <td>
                        <a href={r.url} target="_blank" rel="noreferrer">
                          {r.token_id.slice(0, 8)}…
                        </a>
                      </td>
                      <td>{r.has_voted ? "✅ Da" : "❌ Nu"}</td>
                      <td>{r.voted_at ? new Date(r.voted_at).toLocaleString("ro-RO") : "—"}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "results" && resultsData && (
        <div className="card">
          <h3>Total voturi: {resultsData.total_votes}</h3>
          {resultsData.questions.map((q, idx) => (
            <div key={q.id} className="results-question">
              <h4>
                {String(q.number || "").trim() || String(idx + 1)}. {q.text}
              </h4>
              <ul>
                {Object.entries(resultsData.tally[q.id] || {}).map(([option, cnt]) => (
                  <li key={option}>
                    {option}: <strong>{cnt}</strong>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
