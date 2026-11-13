import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

function nextLetter(questions) {
  return String.fromCharCode(97 + (questions || []).length);
}

function emptyQuestion(questions = []) {
  return {
    id: `q${Date.now()}${Math.floor(Math.random() * 1000)}`,
    number: nextLetter(questions),
    text: "",
    type: "single",
    options: ["Pentru", "Împotriva"],
    required: true,
    depends_on: null,
    depends_value: null,
    auto_answer: null,
  };
}

function emptyElection() {
  return {
    title: "Vot nou",
    chestiune: "",
    description: "",
    nr_apc: "",
    str_apc: "",
    oras: "",
    start_date_vot: "",
    end_date_vot: "",
    tip_proprietate: "apartament",
    property_types: ["apartament", "debara", "parcare"],
    questions: [emptyQuestion()],
    is_active: true,
    require_signature: true,
    email_with_attachment: true,
    email_cc: "",
    email_bcc: "",
    results_email: "",
    notify_results_on_vote: true,
  };
}

function toInputDate(value) {
  if (!value) return "";
  return value.slice(0, 16);
}

export default function AdminElections() {
  const [elections, setElections] = useState([]);
  const [editing, setEditing] = useState(null); // election object being edited, or null
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [newPropType, setNewPropType] = useState("");
  function addPropType() {
    const t = newPropType.trim().toLowerCase();
    if (t) {
      setEditing((prev) => ({
        ...prev,
        property_types: (prev.property_types || []).includes(t) ? prev.property_types : [...(prev.property_types || []), t],
      }));
    }
    setNewPropType("");
  }

  function load() {
    api.listElections().then(setElections).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }

  useEffect(load, []);

  function startNew() {
    setEditing(emptyElection());
  }

  function startEdit(e) {
    setEditing({
      ...e,
      start_date_vot: toInputDate(e.start_date_vot),
      end_date_vot: toInputDate(e.end_date_vot),
      property_types: [...new Set((e.properties || []).map((p) => p.tip_proprietate))],
      questions: e.questions.map((q, i) => ({
        ...q,
        number: q.number || String.fromCharCode(97 + i),
        options: q.options && q.options.length ? q.options : ["Pentru", "Împotriva"],
        depends_on: q.depends_on || null,
        depends_value: q.depends_value || null,
        auto_answer: q.auto_answer || null,
      })),
    });
  }

  function updateQuestion(idx, patch) {
    setEditing((prev) => {
      const questions = prev.questions.map((q, i) => (i === idx ? { ...q, ...patch } : q));
      return { ...prev, questions };
    });
  }

  function setDependency(qIdx, parentId) {
    setEditing((prev) => {
      const questions = prev.questions.map((q, i) => {
        if (i !== qIdx) return q;
        if (!parentId) {
          return { ...q, depends_on: null, depends_value: null, auto_answer: null };
        }
        const parent = prev.questions.find((p) => p.id === parentId);
        const parentOptions = (parent && parent.options) || [];
        const fallbackAuto =
          q.options.find((o) => /^împotriva$/i.test(o)) ||
          q.options[q.options.length - 1] ||
          "";
        return {
          ...q,
          depends_on: parentId,
          depends_value: parentOptions[0] || "",
          auto_answer: fallbackAuto,
        };
      });
      return { ...prev, questions };
    });
  }

  function updateOption(qIdx, optIdx, value) {
    setEditing((prev) => {
      const questions = prev.questions.map((q, i) => {
        if (i !== qIdx) return q;
        const options = q.options.map((o, j) => (j === optIdx ? value : o));
        return { ...q, options };
      });
      return { ...prev, questions };
    });
  }

  function addOption(qIdx) {
    setEditing((prev) => {
      const questions = prev.questions.map((q, i) =>
        i === qIdx ? { ...q, options: [...q.options, ""] } : q
      );
      return { ...prev, questions };
    });
  }

  function removeOption(qIdx, optIdx) {
    setEditing((prev) => {
      const questions = prev.questions.map((q, i) =>
        i === qIdx ? { ...q, options: q.options.filter((_, j) => j !== optIdx) } : q
      );
      return { ...prev, questions };
    });
  }

  function addQuestion() {
    setEditing((prev) => ({ ...prev, questions: [...prev.questions, emptyQuestion(prev.questions)] }));
  }

  function removeQuestion(idx) {
    setEditing((prev) => {
      const removed = prev.questions[idx];
      const questions = prev.questions
        .filter((_, i) => i !== idx)
        .map((q) =>
          q.depends_on === removed.id ? { ...q, depends_on: null, depends_value: null, auto_answer: null } : q
        );
      return { ...prev, questions };
    });
  }

  async function handleSave(e) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const payload = {
        ...editing,
        questions: editing.questions.map((q) => ({
          ...q,
          number: String(q.number || "").trim(),
          options: q.options.filter((o) => o.trim() !== ""),
          depends_on: q.depends_on || null,
          depends_value: q.depends_on ? q.depends_value : null,
          auto_answer: q.depends_on ? q.auto_answer : null,
        })),
        properties: (editing.property_types || []).map((t) => ({ tip_proprietate: t, nr_proprietate: "" })),
        start_date_vot: editing.start_date_vot ? new Date(editing.start_date_vot).toISOString() : null,
        end_date_vot: editing.end_date_vot ? new Date(editing.end_date_vot).toISOString() : null,
      };
      if (editing.id) {
        await api.updateElection(editing.id, payload);
      } else {
        await api.createElection(payload);
      }
      setEditing(null);
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id) {
    if (!window.confirm("Ștergi definitiv acest vot, împreună cu toate link-urile și voturile?")) return;
    await api.deleteElection(id);
    load();
  }

  if (loading) return <p>Se încarcă...</p>;

  if (editing) {
    return (
      <form className="card" onSubmit={handleSave}>
        <h2>{editing.id ? "Editează votul" : "Vot nou"}</h2>
        {error && <p className="error">{error}</p>}

        <label className="field">
          <span>Titlu intern (vizibil doar în admin)</span>
          <input value={editing.title} onChange={(e) => setEditing({ ...editing, title: e.target.value })} required />
        </label>

        <label className="field">
          <span>Notă internă (opțional, nu apare pe buletin)</span>
          <textarea
            value={editing.description}
            onChange={(e) => setEditing({ ...editing, description: e.target.value })}
            rows={2}
          />
        </label>

        <h3>Variabile pentru textul fix al buletinului</h3>
        <div className="field-row">
          <label className="field">
            <span>Nr. APC</span>
            <input value={editing.nr_apc} onChange={(e) => setEditing({ ...editing, nr_apc: e.target.value })} placeholder="12" required />
          </label>
          <label className="field">
            <span>Adresa condominiului (str_apc)</span>
            <input value={editing.str_apc} onChange={(e) => setEditing({ ...editing, str_apc: e.target.value })} placeholder="str. Exemplu 1" required />
          </label>
          <label className="field">
            <span>Localitatea (oraș)</span>
            <input value={editing.oras} onChange={(e) => setEditing({ ...editing, oras: e.target.value })} placeholder="Chișinău" required />
          </label>
        </div>

        <div className="field-row">
          <label className="field">
            <span>Data Adunării Generale cu prezență</span>
            <input
              type="datetime-local"
              value={editing.start_date_vot}
              onChange={(e) => setEditing({ ...editing, start_date_vot: e.target.value })}
              required
            />
          </label>
          <label className="field">
            <span>Termen-limită remitere buletin (și închidere votare)</span>
            <input
              type="datetime-local"
              value={editing.end_date_vot}
              onChange={(e) => setEditing({ ...editing, end_date_vot: e.target.value })}
              required
            />
          </label>
        </div>

        <label className="checkbox-field">
          <input
            type="checkbox"
            checked={editing.allow_multiple_properties !== false}
            onChange={(e) => setEditing({ ...editing, allow_multiple_properties: e.target.checked })}
          />
          <span>Permite votarea mai multor imobile (dacă este bifat, proprietarul poate vota mai multe imobile într-un singur buletin; altfel, doar unul)</span>
        </label>

        <div className="prop-types">
          <span className="prop-types-title">Tipurile de imobile din acest APC</span>
          <p className="muted section-hint">
            Alegeți tipurile. Proprietarul va introduce singur numărul fiecărui imobil, pe buletinul de vot.
          </p>
          <div className="prop-type-chips">
            {["apartament", "debara", "parcare"].map((t) => {
              const on = (editing.property_types || []).includes(t);
              return (
                <label key={t} className={`prop-chip ${on ? "prop-chip-on" : ""}`}>
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() =>
                      setEditing((prev) => ({
                        ...prev,
                        property_types: on
                          ? prev.property_types.filter((x) => x !== t)
                          : [...(prev.property_types || []), t],
                      }))
                    }
                  />
                  <span>{t.charAt(0).toUpperCase() + t.slice(1)}</span>
                </label>
              );
            })}
            {(editing.property_types || [])
              .filter((t) => !["apartament", "debara", "parcare"].includes(t))
              .map((t) => (
                <span key={t} className="prop-chip prop-chip-on">
                  <span>{t.charAt(0).toUpperCase() + t.slice(1)}</span>
                  <button
                    type="button"
                    className="prop-chip-remove"
                    aria-label={`Șterge tipul ${t}`}
                    onClick={() =>
                      setEditing((prev) => ({
                        ...prev,
                        property_types: prev.property_types.filter((x) => x !== t),
                      }))
                    }
                  >
                    ×
                  </button>
                </span>
              ))}
          </div>
          <div className="prop-add-row">
            <input
              value={newPropType}
              onChange={(e) => setNewPropType(e.target.value)}
              placeholder="Alt tip de imobil (ex. boxă)"
              maxLength={30}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addPropType();
                }
              }}
            />
            <button type="button" className="btn" onClick={addPropType}>
              Adaugă tip
            </button>
          </div>
        </div>

        <h3>Expedierea confirmării pe email</h3>
        <div className="field-row">
          <label className="field">
            <span>Buletinul se expediază</span>
            <select
              value={editing.email_with_attachment ? "with" : "without"}
              onChange={(e) => setEditing({ ...editing, email_with_attachment: e.target.value === "with" })}
            >
              <option value="with">Cu atașament (PDF)</option>
              <option value="without">Fără atașament</option>
            </select>
          </label>
          <label className="field">
            <span>Copie CC (opțional, virgulă între adrese)</span>
            <input
              type="text"
              value={editing.email_cc}
              onChange={(e) => setEditing({ ...editing, email_cc: e.target.value })}
              placeholder="comisia@exemplu.com"
            />
          </label>
          <label className="field">
            <span>Copie BCC (opțional, ascunsă)</span>
            <input
              type="text"
              value={editing.email_bcc}
              onChange={(e) => setEditing({ ...editing, email_bcc: e.target.value })}
              placeholder="arhiva@exemplu.com"
            />
          </label>
        </div>
        <p className="muted">
          CC/BCC primesc automat o copie a fiecărei confirmări trimise pentru acest vot.
        </p>

        <h3>Raport de rezultate către APC</h3>
        <div className="field-row">
          <label className="field">
            <span>Email APC pentru rezultate (poate conține mai multe adrese, virgulă între ele)</span>
            <input
              type="text"
              value={editing.results_email || ""}
              onChange={(e) => setEditing({ ...editing, results_email: e.target.value })}
              placeholder="apc@exemplu.com"
            />
          </label>
        </div>
        <label className="checkbox-field">
          <input
            type="checkbox"
            checked={editing.notify_results_on_vote !== false}
            onChange={(e) => setEditing({ ...editing, notify_results_on_vote: e.target.checked })}
          />
          Trimite rezultatele actualizate pe email la fiecare vot nou
        </label>
        <p className="muted">
          Raportul conține rezultatele în procente, diagrame și link-ul dashboardului public. La
          încheierea votării se trimite automat un raport final. Trimiterea manuală se face din
          pagina „Link-uri &amp; rezultate”.
        </p>

        <label className="checkbox-field">
          <input
            type="checkbox"
            checked={editing.is_active}
            onChange={(e) => setEditing({ ...editing, is_active: e.target.checked })}
          />
          Vot activ (altfel linkurile arată "votare închisă")
        </label>

        <label className="checkbox-field">
          <input
            type="checkbox"
            checked={editing.require_signature}
            onChange={(e) => setEditing({ ...editing, require_signature: e.target.checked })}
          />
          Necesită semnătură olografă la final
        </label>

        <label className="field">
          <span>Chestiunea propusă spre vot (apare pe buletin, deasupra întrebărilor)</span>
          <textarea
            rows={3}
            value={editing.chestiune || ""}
            onChange={(e) => setEditing({ ...editing, chestiune: e.target.value })}
            placeholder="Alegerea președintelui și secretarului Adunării Generale Mixte"
          />
        </label>

        <h3>Întrebări supuse votului</h3>
        <p className="muted">
          Întrebările sunt numerotate cu litere: a, b, c… Dependențele se setează la fiecare întrebare. Opțiunile implicite sunt „Pentru” și „Împotriva”.
        </p>
        {editing.questions.map((q, qIdx) => {
          const parentOptions = (() => {
            const parent = editing.questions.find((p) => p.id === q.depends_on);
            return (parent && parent.options) || [];
          })();
          return (
            <div key={q.id} className="question-editor">
              <div className="field-row">
                <label className="field" style={{ maxWidth: 90 }}>
                  <span>Nr.</span>
                  <input
                    value={q.number}
                    onChange={(e) => updateQuestion(qIdx, { number: e.target.value })}
                    placeholder="3.a"
                    required
                  />
                </label>
                <label className="field" style={{ flex: 2 }}>
                  <span>Textul întrebării</span>
                  <textarea
                    rows={3}
                    value={q.text}
                    onChange={(e) => updateQuestion(qIdx, { text: e.target.value })}
                    required
                  />
                </label>
                <label className="field">
                  <span>Tip</span>
                  <select
                    value={q.type}
                    onChange={(e) => {
                      const type = e.target.value;
                      updateQuestion(qIdx, {
                        type,
                        ...(type !== "single"
                          ? { depends_on: null, depends_value: null, auto_answer: null }
                          : {}),
                      });
                    }}
                  >
                    <option value="single">O singură opțiune</option>
                    <option value="multiple">Opțiuni multiple</option>
                  </select>
                </label>
                <label className="checkbox-field" style={{ alignSelf: "center" }}>
                  <input
                    type="checkbox"
                    checked={q.required}
                    onChange={(e) => updateQuestion(qIdx, { required: e.target.checked })}
                  />
                  Obligatorie
                </label>
              </div>

              <div className="options-editor">
                {q.options.map((opt, optIdx) => (
                  <div key={optIdx} className="option-row">
                    <input
                      value={opt}
                      placeholder={`Opțiune ${optIdx + 1}`}
                      onChange={(e) => updateOption(qIdx, optIdx, e.target.value)}
                    />
                    <button type="button" className="btn-link" onClick={() => removeOption(qIdx, optIdx)}>
                      ×
                    </button>
                  </div>
                ))}
                <button type="button" className="btn-link" onClick={() => addOption(qIdx)}>
                  + opțiune
                </button>
              </div>

              {qIdx > 0 && q.type === "single" && (
                <div className="dependency-editor">
                  <span className="dependency-title">Logică condiționată (opțional)</span>
                  <div className="field-row">
                    <label className="field">
                      <span>Depinde de întrebarea</span>
                      <select value={q.depends_on || ""} onChange={(e) => setDependency(qIdx, e.target.value)}>
                        <option value="">— nu depinde —</option>
                        {editing.questions.slice(0, qIdx).map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.number || "?"}. {p.text ? p.text.slice(0, 60) : "(fără text)"}
                          </option>
                        ))}
                      </select>
                    </label>
                    {q.depends_on && (
                      <>
                        <label className="field">
                          <span>Dacă răspunsul este</span>
                          <select
                            value={q.depends_value || ""}
                            onChange={(e) => updateQuestion(qIdx, { depends_value: e.target.value })}
                          >
                            {parentOptions.map((opt) => (
                              <option key={opt} value={opt}>
                                {opt}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="field">
                          <span>Atunci setează automat</span>
                          <select
                            value={q.auto_answer || ""}
                            onChange={(e) => updateQuestion(qIdx, { auto_answer: e.target.value })}
                          >
                            {q.options.map((opt) => (
                              <option key={opt} value={opt}>
                                {opt}
                              </option>
                            ))}
                          </select>
                        </label>
                      </>
                    )}
                  </div>
                  {q.depends_on && (
                    <p className="muted dependency-hint">
                      Dacă răspunsul la întrebarea anterioară este „{q.depends_value}”, această întrebare devine
                      inactivă și primește automat răspunsul „{q.auto_answer}”. În caz contrar, votantul o poate
                      completa liber.
                    </p>
                  )}
                </div>
              )}

              <button type="button" className="btn-link btn-danger" onClick={() => removeQuestion(qIdx)}>
                Șterge întrebarea
              </button>
              <hr />
            </div>
          );
        })}
        <button type="button" className="btn" onClick={addQuestion}>
          + Adaugă întrebare
        </button>

        <div className="actions-row">
          <button className="btn btn-primary" type="submit" disabled={saving}>
            {saving ? "Se salvează..." : "Salvează"}
          </button>
          <button className="btn" type="button" onClick={() => setEditing(null)}>
            Anulează
          </button>
        </div>
      </form>
    );
  }

  return (
    <div>
      <div className="actions-row">
        <h2>Voturi APC</h2>
        <button className="btn btn-primary" onClick={startNew}>
          + Vot nou
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Titlu intern</th>
              <th>APC nr.</th>
              <th>Adresa și localitatea</th>
              <th>Link de vot</th>
              <th>Status</th>
              <th>Întrebări</th>
              <th>Email</th>
              <th className="col-actions">Acțiuni</th>
            </tr>
          </thead>
          <tbody>
            {elections.length === 0 && (
              <tr>
                <td colSpan={8} className="table-empty">Nu există voturi. Creați primul vot cu „+ Vot nou”.</td>
              </tr>
            )}
            {elections.map((e) => (
              <tr key={e.id}>
                <td data-label="Titlu intern">
                  <strong>{e.title}</strong>
                </td>
                <td data-label="APC nr.">{e.nr_apc || "—"}</td>
                <td data-label="Adresa și localitatea">
                  {[e.str_apc, e.oras].filter(Boolean).join(", ") || "—"}
                </td>
                <td data-label="Link de vot">
                  {e.vote_url ? (
                    <a href={e.vote_url} target="_blank" rel="noreferrer">
                      /{e.nr_apc}
                    </a>
                  ) : (
                    "—"
                  )}
                </td>
                <td data-label="Status">
                  <span className={`status-pill ${e.is_active ? "status-on" : "status-off"}`}>
                    {e.is_active ? "Activ" : "Inactiv"}
                  </span>
                </td>
                <td data-label="Întrebări">{e.questions.length}</td>
                <td data-label="Email">
                  <span className="muted">
                    {e.email_with_attachment ? "cu PDF" : "fără atașament"}
                    {e.results_email ? ` · rezultate: ${e.results_email}` : ""}
                  </span>
                </td>
                <td className="col-actions" data-label="Acțiuni">
                  <div className="row-actions">
                    <button className="btn" onClick={() => startEdit(e)}>
                      Editează
                    </button>
                    <Link className="btn" to={`/admin/elections/${e.id}`}>
                      Checklist
                    </Link>
                    <button className="btn btn-danger" onClick={() => handleDelete(e.id)}>
                      Șterge
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
