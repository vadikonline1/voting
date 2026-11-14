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
  const [newEnd, setNewEnd] = useState("");
  const [emailRows, setEmailRows] = useState(null);
  const [selectedEmail, setSelectedEmail] = useState(null); // email row shown in the details modal
  const [sendingLinks, setSendingLinks] = useState(false);
  const [linksStatus, setLinksStatus] = useState("");
  const [voteView, setVoteView] = useState(null); // { loading } | { data } | { error } for the vote window

  function openVote(tokenId) {
    setVoteView({ loading: true });
    api
      .voteDetail(id, tokenId)
      .then((data) => setVoteView({ data }))
      .catch((e) => setVoteView({ error: e.message }));
  }

  useEffect(() => {
    if (tab === "emails") {
      api.emailLog(id).then(setEmailRows).catch((e) => setError(e.message));
    }
  }, [tab, id]);

  // Esc closes the email details window
  useEffect(() => {
    if (!selectedEmail) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") setSelectedEmail(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedEmail]);

  const [extendStatus, setExtendStatus] = useState("");

  async function handleSendLinks() {
    setSendingLinks(true);
    setLinksStatus("");
    setError("");
    try {
      const res = await api.sendLinks(id);
      setLinksStatus(`Linkurile au fost trimise către ${res.sent_to}.`);
      loadChecklist();
    } catch (e) {
      setError(e.message);
    } finally {
      setSendingLinks(false);
    }
  }

  async function handleExtend(e) {
    e.preventDefault();
    setError("");
    setExtendStatus("");
    if (!newEnd) {
      setError("Alegeți noua dată de încheiere a votării.");
      return;
    }
    try {
      await api.extendElection(id, new Date(newEnd).toISOString());
      setExtendStatus("Termenul de votare a fost prelungit. Reamintirile către APC vor fi trimise din nou pentru noua dată.");
      setNewEnd("");
      loadResults();
    } catch (err) {
      setError(err.message);
    }
  }

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
        <button className={tab === "emails" ? "tab active" : "tab"} onClick={() => setTab("emails")}>
          Emailuri trimise
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {tab === "voters" && (
        <div>
          <form className="card extend-card" onSubmit={handleExtend}>
            <h3>Termenul de votare</h3>
            <p className="muted">
              Încheiere actuală:{" "}
              <strong>
                {resultsData?.end_date_vot
                  ? new Date(resultsData.end_date_vot).toLocaleString("ro-RO")
                  : "nesetat"}
              </strong>
            </p>
            <p className="muted section-hint">
              APC-ul primește emailuri cu 3, 2 și 1 zi înainte de încheiere. Dacă prelungiți votarea, alegeți o dată nouă.
            </p>
            {checklistData?.extend_url && (
              <p className="muted section-hint">
                Link-ul de prelungire trimis APC-ului în emailuri:{" "}
                <a href={checklistData.extend_url} target="_blank" rel="noreferrer">
                  {checklistData.extend_url}
                </a>
              </p>
            )}
            <div className="extend-row">
              <input
                type="datetime-local"
                value={newEnd}
                onChange={(e) => setNewEnd(e.target.value)}
                aria-label="Noua dată de încheiere"
              />
              <button className="btn btn-primary" type="submit" disabled={!newEnd}>
                Prelungește votarea
              </button>
            </div>
            {extendStatus && <p className="success">{extendStatus}</p>}
          </form>

          <div className="card">
            <h3>Trimite linkurile către APC</h3>
            <p className="muted">
              Trimiteți-le după ce ați adăugat toate întrebările. Emailul conține linkul de vot (pentru proprietari) și
              dashboard-ul cu rezultatele, cu avertizarea că informațiile sunt confidențiale.
            </p>
            <div className="actions-row">
              <button
                className="btn btn-primary"
                onClick={handleSendLinks}
                disabled={sendingLinks || !checklistData?.vote_url || !resultsData?.results_email}
                title={
                  resultsData && !resultsData.results_email
                    ? "Configurați adresa APC pentru rezultate în „Editează votul”."
                    : "Trimite linkul de vot și dashboard-ul pe emailul APC"
                }
              >
                {sendingLinks ? "Se trimite..." : "Trimite linkurile pe email"}
              </button>
              <span className="muted">
                {checklistData?.links_email_sent_at
                  ? `Ultima trimitere: ${new Date(checklistData.links_email_sent_at).toLocaleString("ro-RO")}`
                  : "Nu a fost trimis încă."}
              </span>
            </div>
            {linksStatus && <p className="success">{linksStatus}</p>}
          </div>

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
                  <th>Bloc / adresă</th>
                  <th>Imobile votate</th>
                  <th>Email</th>
                  <th>A votat?</th>
                  <th>Data votării</th>
                  <th>ID vot (UUID)</th>
                  <th>Votul</th>
                </tr>
              </thead>
              <tbody>
                {checklistData &&
                  checklistData.rows.map((r) => (
                    <tr key={r.token_id}>
                      <td>{r.nume_prenume || "—"}</td>
                      <td>{r.phone || "—"}</td>
                      <td>{r.adresa || "—"}</td>
                      <td>
                        {r.properties && r.properties.length
                          ? r.properties
                              .map((p) => `${TIP_LABELS[p.tip_proprietate] || p.tip_proprietate} ${p.nr_proprietate}${p.bloc ? ` (bl. ${p.bloc})` : ""}`)
                              .join(", ")
                          : "—"}
                      </td>
                      <td>{r.email || "—"}</td>
                      <td>{r.has_voted ? "✅ Da" : "❌ Nu"}</td>
                      <td>{r.voted_at ? new Date(r.voted_at).toLocaleString("ro-RO") : "—"}</td>
                      <td>
                        <code className="uuid-text" title={r.token_id}>
                          {r.token_id}
                        </code>
                      </td>
                      <td>
                        {r.has_voted ? (
                          <button type="button" className="btn-link" onClick={() => openVote(r.token_id)}>
                            Vezi votul
                          </button>
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "emails" && (
        <div className="card">
          <div className="actions-row">
            <h3>Emailuri trimise pentru acest vot</h3>
            <button className="btn" onClick={() => api.emailLog(id).then(setEmailRows).catch((e) => setError(e.message))}>
              Reîmprospătează
            </button>
          </div>
          <p className="muted">
            Fiecare email trimis de sistem: cine l-a trimis, către cine, subiectul și headerele complete.
          </p>
          {emailRows === null && <p className="muted">Se încarcă...</p>}
          {emailRows && emailRows.length === 0 && <p className="muted">Nu a fost trimis încă niciun email.</p>}
          {emailRows && emailRows.length > 0 && (
            <div className="table-wrap">
              <table className="admin-table email-table">
                <thead>
                  <tr>
                    <th>Data</th>
                    <th>Tip</th>
                    <th>Status</th>
                    <th>De la</th>
                    <th>Către</th>
                    <th>Cc / Bcc</th>
                    <th>Subiect</th>
                  </tr>
                </thead>
                <tbody>
                  {emailRows.map((r) => (
                    <tr key={r.id}>
                      <td data-label="Data">{r.created_at ? new Date(r.created_at).toLocaleString("ro-RO") : "—"}</td>
                      <td data-label="Tip">{r.kind || "—"}</td>
                      <td data-label="Status">
                        <span className={`status-pill ${r.status === "trimis" ? "status-on" : "status-off"}`}>
                          {r.status}
                        </span>
                        {r.status !== "trimis" && r.info && <div className="muted email-info">{r.info}</div>}
                      </td>
                      <td data-label="De la">{r.from || "—"}</td>
                      <td data-label="Către">{r.to || "—"}</td>
                      <td data-label="Cc / Bcc">
                        {[r.cc && `Cc: ${r.cc}`, r.bcc && `Bcc: ${r.bcc}`].filter(Boolean).join(" · ") || "—"}
                      </td>
                      <td data-label="Subiect">
                        {r.subject || "—"}
                        <div>
                          <button type="button" className="btn-link" onClick={() => setSelectedEmail(r)}>
                            Vezi detaliile
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {selectedEmail && (
            <div className="modal-backdrop" role="presentation" onClick={() => setSelectedEmail(null)}>
              <div
                className="modal"
                role="dialog"
                aria-modal="true"
                aria-label="Detaliile emailului"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="modal-head">
                  <h3>{selectedEmail.subject || "(fără subiect)"}</h3>
                  <button type="button" className="icon-btn" aria-label="Închide" onClick={() => setSelectedEmail(null)}>
                    ×
                  </button>
                </div>
                <dl className="modal-grid">
                  <dt>Data</dt>
                  <dd>{selectedEmail.created_at ? new Date(selectedEmail.created_at).toLocaleString("ro-RO") : "—"}</dd>
                  <dt>Tip</dt>
                  <dd>{selectedEmail.kind || "—"}</dd>
                  <dt>Status</dt>
                  <dd>
                    {selectedEmail.status || "—"}
                    {selectedEmail.status !== "trimis" && selectedEmail.info ? ` · ${selectedEmail.info}` : ""}
                  </dd>
                  <dt>De la</dt>
                  <dd>{selectedEmail.from || "—"}</dd>
                  <dt>Către</dt>
                  <dd>{selectedEmail.to || "—"}</dd>
                  {selectedEmail.cc && (
                    <>
                      <dt>Cc</dt>
                      <dd>{selectedEmail.cc}</dd>
                    </>
                  )}
                  {selectedEmail.bcc && (
                    <>
                      <dt>Bcc</dt>
                      <dd>{selectedEmail.bcc}</dd>
                    </>
                  )}
                  {selectedEmail.attachment && (
                    <>
                      <dt>Atașament</dt>
                      <dd>{selectedEmail.attachment}</dd>
                    </>
                  )}
                </dl>
                <h4>Headere</h4>
                <pre className="email-headers">{selectedEmail.headers || "—"}</pre>
                {selectedEmail.preview && (
                  <>
                    <h4>Previzualizare</h4>
                    <pre className="email-headers">{selectedEmail.preview}</pre>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {voteView && (
        <div className="modal-backdrop" role="presentation" onClick={() => setVoteView(null)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Votul" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h3>Votul persoanei</h3>
              <button type="button" className="icon-btn" aria-label="Închide" onClick={() => setVoteView(null)}>
                ×
              </button>
            </div>
            {voteView.loading && <p className="muted">Se încarcă votul...</p>}
            {voteView.error && <p className="error">{voteView.error}</p>}
            {voteView.data && (
              <>
                <dl className="modal-grid">
                  <dt>Nume</dt>
                  <dd>{voteView.data.nume_prenume || "—"}</dd>
                  <dt>ID vot (UUID)</dt>
                  <dd>
                    <code className="uuid-text">{voteView.data.token_id}</code>
                  </dd>
                  <dt>Bloc / adresă</dt>
                  <dd>{[voteView.data.adresa, voteView.data.bloc && `bl. ${voteView.data.bloc}`].filter(Boolean).join(", ") || "—"}</dd>
                  <dt>Imobile</dt>
                  <dd>
                    {voteView.data.properties
                      .map((p) => `${TIP_LABELS[p.tip_proprietate] || p.tip_proprietate} ${p.nr_proprietate}${p.bloc ? ` (bl. ${p.bloc})` : ""}`)
                      .join(", ") || "—"}
                  </dd>
                  <dt>Votat la</dt>
                  <dd>{voteView.data.voted_at ? new Date(voteView.data.voted_at).toLocaleString("ro-RO") : "—"}</dd>
                </dl>
                {voteView.data.items.map((item, idx) =>
                  item.type === "section" ? (
                    <h4 key={idx} className="vote-section">
                      {item.text}
                    </h4>
                  ) : (
                    <div key={idx} className="vote-item">
                      <div className="vote-q">
                        {item.label}. {item.text}
                      </div>
                      <div className="vote-a">
                        Vot: <strong>{item.answer}</strong>
                      </div>
                    </div>
                  )
                )}
                <p>
                  <a href={voteView.data.receipt_url} target="_blank" rel="noreferrer">
                    Deschide buletinul completat (PDF)
                  </a>
                </p>
              </>
            )}
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
