import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api";
import ResultsView from "../components/ResultsView";

const TIP_LABELS = { apartament: "Apartament", debara: "Debara", parcare: "Parcare" };

export default function AdminElectionDetail() {
  const { id } = useParams();
  const [tab, setTab] = useState("voters");
  const [checklistData, setChecklistData] = useState(null);
  const [resultsData, setResultsData] = useState(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [sendStatus, setSendStatus] = useState("");
  const [sending, setSending] = useState(false);

  function loadChecklist() {
    api.checklist(id).then(setChecklistData).catch((e) => setError(e.message));
  }

  function loadResults() {
    api.results(id).then(setResultsData).catch((e) => setError(e.message));
  }

  useEffect(() => {
    loadChecklist();
    loadResults();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleSendResults() {
    setSending(true);
    setSendStatus("");
    setError("");
    try {
      const res = await api.sendResults(id);
      setSendStatus(`Rezultatele au fost trimise către ${res.sent_to}.`);
      loadResults();
    } catch (e) {
      setSendStatus("");
      setError(e.message);
    } finally {
      setSending(false);
    }
  }

  function copyVoteLink() {
    if (!checklistData?.vote_url) return;
    navigator.clipboard.writeText(checklistData.vote_url);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div>
      <p>
        <Link to="/admin">← Înapoi la lista de voturi</Link>
      </p>
      <h2>{checklistData ? checklistData.election_title : "..."}</h2>

      <div className="tabs">
        <button className={tab === "voters" ? "tab active" : "tab"} onClick={() => setTab("voters")}>
          Link de vot &amp; checklist
        </button>
        <button className={tab === "results" ? "tab active" : "tab"} onClick={() => setTab("results")}>
          Rezultate
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {tab === "voters" && (
        <div>
          <div className="card">
            <h3>Link fix de vot pentru acest APC</h3>
            <p className="muted">
              Proprietarii completează singuri datele și bifează imobilele pe care le dețin. Linkul rămâne
              activ cât timp votul este activ.
            </p>
            <div className="actions-row">
              {checklistData?.vote_url ? (
                <a href={checklistData.vote_url} target="_blank" rel="noreferrer">
                  {checklistData.vote_url}
                </a>
              ) : (
                <span className="muted">Completați numărul APC în „Editează conținut”.</span>
              )}
              <button className="btn" onClick={copyVoteLink} disabled={!checklistData?.vote_url}>
                {copied ? "Copiat ✓" : "Copiază linkul"}
              </button>
            </div>
          </div>

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
                  <th>Imobile votate</th>
                  <th>Email</th>
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
                      <td>
                        {r.properties && r.properties.length
                          ? r.properties
                              .map((p) => `${TIP_LABELS[p.tip_proprietate] || p.tip_proprietate} ${p.nr_proprietate}`)
                              .join(", ")
                          : "—"}
                      </td>
                      <td>{r.email || "—"}</td>
                      <td>{r.has_voted ? "✅ Da" : "❌ Nu"}</td>
                      <td>{r.voted_at ? new Date(r.voted_at).toLocaleString("ro-RO") : "—"}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "results" && (
        <div className="card">
          <div className="actions-row">
            <h3>Rezultate</h3>
            <div className="actions-row">
              <button className="btn" onClick={loadResults}>
                Reîmprospătează
              </button>
              <button
                className="btn btn-primary"
                onClick={handleSendResults}
                disabled={sending || !resultsData || !resultsData.results_email}
                title={
                  resultsData && !resultsData.results_email
                    ? "Configurați adresa APC pentru rezultate în „Editează conținut”."
                    : "Trimite rezultatele pe emailul APC"
                }
              >
                {sending ? "Se trimite..." : "Trimite rezultatele pe email"}
              </button>
            </div>
          </div>

          {resultsData && (
            <>
              <p className="muted">
                Email rezultate: <strong>{resultsData.results_email || "neconfigurat"}</strong>
                {resultsData.notify_results_on_vote
                  ? " · se trimite automat la fiecare vot nou"
                  : " · notificarea automată la vot este dezactivată"}
              </p>

              {resultsData.dashboard_url && (
                <p className="muted">
                  Dashboard public (în timp real):{" "}
                  <a href={resultsData.dashboard_url} target="_blank" rel="noreferrer">
                    {resultsData.dashboard_url}
                  </a>
                </p>
              )}

              {resultsData.results_final_email_sent_at && (
                <p className="muted">
                  Raport final trimis la:{" "}
                  {new Date(resultsData.results_final_email_sent_at).toLocaleString("ro-RO")}
                </p>
              )}
            </>
          )}

          {sendStatus && <p className="success">{sendStatus}</p>}

          {resultsData ? (
            <ResultsView results={resultsData} title={false} />
          ) : (
            <p className="muted">Se încarcă rezultatele...</p>
          )}
        </div>
      )}
    </div>
  );
}
