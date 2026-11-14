import { useEffect, useState } from "react";
import { api } from "../api";

const CONFIRM_WORDS = "STERGE TOT";

/** Admin card: delete the votes that ended more than 180 days ago, or clear everything when no vote is active. */
export default function RetentionCard({ onChanged }) {
  const [info, setInfo] = useState(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [open, setOpen] = useState(false); // collapsed by default

  function load() {
    api.retentionPreview().then(setInfo).catch((e) => setError(e.message));
  }

  useEffect(load, []);

  async function run(action, args) {
    setBusy(true);
    setError("");
    setStatus("");
    try {
      const res = await action(args);
      setStatus(`Au fost șterse ${res.votes} voturi și datele a ${res.owners} proprietari.`);
      setConfirmText("");
      load();
      if (onChanged) onChanged();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function purgeOld() {
    if (!info || info.old_votes === 0) return;
    const ok = window.confirm(
      `Se șterg definitiv ${info.old_votes} voturi încheiate mai demult de ${info.retention_days} zile, ` +
        `împreună cu datele proprietarilor, buletinele PDF și semnăturile. Nu se poate reveni. Continuați?`
    );
    if (ok) run(api.retentionPurgeOld);
  }

  function clearAll() {
    run(api.retentionClearAll, { confirm: confirmText });
  }

  if (!info) return null;

  const canClear = !info.has_active_vote && info.total_votes > 0;

  return (
    <div className="card retention-card">
      <button
        type="button"
        className="collapse-toggle"
        aria-expanded={open}
        aria-controls="retention-body"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="collapse-title">Păstrarea datelor votului</span>
        <span className="collapse-hint">
          {info.old_votes} mai vechi de {info.retention_days} zile
        </span>
        <span className={`collapse-arrow ${open ? "collapse-arrow-open" : ""}`} aria-hidden="true">
          ▾
        </span>
      </button>

      {open && (
      <div id="retention-body" className="collapse-body">
      <p className="muted">
        Voturile încheiate mai demult de {info.retention_days} zile pot fi șterse definitiv, împreună cu datele
        proprietarilor și cu buletinele PDF.
      </p>

      <div className="retention-row">
        <div>
          <strong>{info.old_votes}</strong> {info.old_votes === 1 ? "vot" : "voturi"} mai vechi de{" "}
          {info.retention_days} zile · <strong>{info.old_owners}</strong> proprietari
          {info.old_titles.length > 0 && (
            <details className="retention-list">
              <summary>Vezi voturile</summary>
              <ul>
                {info.old_titles.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
        <button className="btn btn-danger" onClick={purgeOld} disabled={busy || info.old_votes === 0}>
          Șterge voturile mai vechi de {info.retention_days} zile
        </button>
      </div>

      <div className="retention-row retention-clear">
        <div>
          <strong>Golire completă</strong>
          <p className="muted section-hint">
            Șterge toate voturile. Este disponibilă doar când nu există niciun vot activ.
            {info.has_active_vote && " Acum există un vot activ, deci opțiunea este blocată."}
          </p>
        </div>
        <div className="retention-confirm">
          <input name="RetentionCard-91"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder={`Scrieți ${CONFIRM_WORDS}`}
            disabled={!canClear || busy}
            aria-label="Text de confirmare"
          />
          <button
            className="btn btn-danger"
            onClick={clearAll}
            disabled={!canClear || busy || confirmText.trim() !== CONFIRM_WORDS}
          >
            Golește tot
          </button>
        </div>
      </div>

      {status && <p className="success">{status}</p>}
      {error && <p className="error">{error}</p>}
      </div>
      )}
    </div>
  );
}
