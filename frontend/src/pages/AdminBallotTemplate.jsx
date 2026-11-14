import { useEffect, useRef, useState } from "react";
import { api } from "../api";

const FIELDS = [
  { key: "title", label: "Titlul buletinului" },
  { key: "paragraph1", label: "Primul paragraf (text legal)" },
  { key: "paragraph2", label: "Paragraful votantului" },
  { key: "note", label: "Nota de la final" },
];

/** Admin page: the text of the buletin de vot (PDF and email) with the variables filled automatically. */
export default function AdminBallotTemplate() {
  const [tpl, setTpl] = useState(null); // { title, paragraph1, paragraph2, note }
  const [defaults, setDefaults] = useState(null);
  const [variables, setVariables] = useState([]);
  const [elections, setElections] = useState([]);
  const [electionId, setElectionId] = useState("");
  const [preview, setPreview] = useState(null); // { rendered, values, election_title }
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);
  const refs = useRef({});
  const [activeField, setActiveField] = useState("paragraph1");

  useEffect(() => {
    api
      .getBallotTemplate()
      .then((data) => {
        setTpl(data.template);
        setDefaults(data.defaults);
        setVariables(data.variables);
      })
      .catch((e) => setError(e.message));
    api.listElections().then(setElections).catch(() => {});
  }, []);

  // live preview: re-render 400 ms after the last change
  useEffect(() => {
    if (!tpl) return undefined;
    const timer = setTimeout(() => {
      api
        .previewBallotTemplate({ ...tpl, election_id: electionId ? Number(electionId) : null })
        .then(setPreview)
        .catch((e) => setError(e.message));
    }, 400);
    return () => clearTimeout(timer);
  }, [tpl, electionId]);

  function update(key, value) {
    setTpl((prev) => ({ ...prev, [key]: value }));
    setStatus("");
  }

  /** Puts {variable} where the cursor is in the active field. */
  function insertVariable(key) {
    const token = `{${key}}`;
    const el = refs.current[activeField];
    const current = tpl[activeField] || "";
    if (!el) {
      update(activeField, current + token);
      return;
    }
    const start = el.selectionStart ?? current.length;
    const end = el.selectionEnd ?? current.length;
    const next = current.slice(0, start) + token + current.slice(end);
    update(activeField, next);
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(start + token.length, start + token.length);
    });
  }

  async function handleSave() {
    setSaving(true);
    setError("");
    setStatus("");
    try {
      const saved = await api.saveBallotTemplate(tpl);
      setTpl(saved);
      setStatus("Textul buletinului a fost salvat. Se aplică la voturile noi și la emailurile următoare.");
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  function handleReset() {
    if (!defaults) return;
    setTpl({ ...defaults });
    setStatus("Textul implicit este încărcat. Apăsați „Salvează” ca să-l folosiți.");
  }

  if (!tpl) {
    return <div className="center-page">{error || "Se încarcă..."}</div>;
  }

  const values = preview?.values || {};
  const rendered = preview?.rendered;

  return (
    <div>
      <div className="actions-row">
        <h2>Șablon buletin de vot</h2>
        <div className="actions-row">
          <label className="field inline-field">
            <span>Exemplu cu votul</span>
            <select value={electionId} onChange={(e) => setElectionId(e.target.value)}>
              <option value="">— ultimul vot —</option>
              {elections.map((e) => (
                <option key={e.id} value={e.id}>
                  APC nr. {e.nr_apc || "—"} · {e.title}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <p className="muted">
        Scrieți textul buletinului. Variabilele din acolade (de exemplu <code>{"{nr_apc}"}</code>) se completează
        automat cu datele votului și ale votantului. Apăsați o variabilă ca s-o adăugați în câmpul selectat.
      </p>
      {error && <p className="error">{error}</p>}
      {status && <p className="success">{status}</p>}

      <div className="ballot-tpl-grid">
        <div className="card">
          {FIELDS.map((f) => (
            <label key={f.key} className="field">
              <span>{f.label}</span>
              <textarea
                rows={f.key === "title" ? 2 : 5}
                value={tpl[f.key] || ""}
                ref={(el) => {
                  refs.current[f.key] = el;
                }}
                onFocus={() => setActiveField(f.key)}
                onChange={(e) => update(f.key, e.target.value)}
              />
            </label>
          ))}
          <div className="actions-row">
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? "Se salvează..." : "Salvează textul"}
            </button>
            <button className="btn" type="button" onClick={handleReset}>
              Revino la textul implicit
            </button>
          </div>
        </div>

        <div className="card">
          <h3>Variabile</h3>
          <p className="muted section-hint">
            Câmpul activ: <strong>{FIELDS.find((f) => f.key === activeField)?.label}</strong>
          </p>
          <div className="var-chips">
            {variables.map((v) => (
              <button key={v.key} type="button" className="var-chip" title={v.label} onClick={() => insertVariable(v.key)}>
                {`{${v.key}}`}
              </button>
            ))}
          </div>
          <div className="table-wrap">
            <table className="admin-table var-table">
              <thead>
                <tr>
                  <th>Variabilă</th>
                  <th>Ce conține</th>
                  <th>Valoare acum</th>
                </tr>
              </thead>
              <tbody>
                {variables.map((v) => (
                  <tr key={v.key}>
                    <td data-label="Variabilă"><code>{`{${v.key}}`}</code></td>
                    <td data-label="Ce conține">{v.label}</td>
                    <td data-label="Valoare acum">{values[v.key] ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="card ballot-preview">
        <div className="actions-row">
          <h3>Previzualizare</h3>
          <span className="muted">
            {preview ? `Vot: ${preview.election_title}` : ""} · votant exemplu: Ion Popescu
          </span>
        </div>
        {rendered ? (
          <div className="paper">
            <h2 className="paper-title">{rendered.title}</h2>
            <p className="paper-indent">{rendered.paragraph1}</p>
            <p className="paper-indent">{rendered.paragraph2}</p>
            <p className="paper-decisions muted">[ aici apar întrebările și variantele de vot ]</p>
            {rendered.note && <p className="paper-note">{rendered.note}</p>}
          </div>
        ) : (
          <p className="muted">Se generează previzualizarea...</p>
        )}
      </div>
    </div>
  );
}
