import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

function nextNumber(questions) {
  let max = 0;
  for (const q of questions || []) {
    const match = String(q.number || "").match(/^(\d+)/);
    if (match) max = Math.max(max, Number(match[1]));
  }
  return String(max + 1);
}

function emptyQuestion(questions = []) {
  return {
    id: `q${Date.now()}${Math.floor(Math.random() * 1000)}`,
    number: nextNumber(questions),
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
    description: "",
    nr_apc: "",
    str_apc: "",
    oras: "",
    start_date_vot: "",
    end_date_vot: "",
    tip_proprietate: "apartament",
    questions: [emptyQuestion()],
    is_active: true,
    require_signature: true,
    email_with_attachment: true,
    email_cc: "",
    email_bcc: "",
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
      questions: e.questions.map((q, i) => ({
        ...q,
        number: q.number || String(i + 1),
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
          <label className="field">
            <span>Tip proprietate</span>
            <input
              value={editing.tip_proprietate}
              onChange={(e) => setEditing({ ...editing, tip_proprietate: e.target.value })}
              placeholder="apartament"
            />
          </label>
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

        <h3>Întrebări supuse votului</h3>
        <p className="muted">
          Numerotarea este liberă: 1, 2, 3, 3.a, 3.b etc. Opțiunile implicite sunt „Pentru” și „Împotriva”.
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
                  <input value={q.text} onChange={(e) => updateQuestion(qIdx, { text: e.target.value })} required />
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
      <div className="elections-grid">
        {elections.map((e) => (
          <div key={e.id} className="card election-card">
            <h3>{e.title}</h3>
            <p className="muted">
              APC nr. {e.nr_apc || "—"} · {e.str_apc || "—"} · {e.oras || "—"}
            </p>
            <p className="muted">
              {e.is_active ? "Activ" : "Inactiv"} · {e.questions.length} întrebări
              {e.require_signature ? " · semnătură obligatorie" : ""}
              {e.email_with_attachment ? " · email cu PDF" : " · email fără atașament"}
            </p>
            <div className="actions-row">
              <button className="btn" onClick={() => startEdit(e)}>
                Editează conținut
              </button>
              <Link className="btn" to={`/admin/elections/${e.id}`}>
                Link-uri &amp; rezultate
              </Link>
              <button className="btn btn-danger" onClick={() => handleDelete(e.id)}>
                Șterge
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
