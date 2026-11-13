import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

function emptyQuestion() {
  return {
    id: `q${Date.now()}${Math.floor(Math.random() * 1000)}`,
    text: "",
    type: "single",
    options: ["Da/Pro", "Nu/Contra"],
    required: true,
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
      questions: e.questions.map((q) => ({ ...q })),
    });
  }

  function updateQuestion(idx, patch) {
    setEditing((prev) => {
      const questions = prev.questions.map((q, i) => (i === idx ? { ...q, ...patch } : q));
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
    setEditing((prev) => ({ ...prev, questions: [...prev.questions, emptyQuestion()] }));
  }

  function removeQuestion(idx) {
    setEditing((prev) => ({ ...prev, questions: prev.questions.filter((_, i) => i !== idx) }));
  }

  async function handleSave(e) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const payload = {
        ...editing,
        questions: editing.questions.map((q) => ({ ...q, options: q.options.filter((o) => o.trim() !== "") })),
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

        <h3>Hotărâri supuse votului</h3>
        {editing.questions.map((q, qIdx) => (
          <div key={q.id} className="question-editor">
            <div className="field-row">
              <label className="field" style={{ flex: 2 }}>
                <span>Textul hotărârii</span>
                <input value={q.text} onChange={(e) => updateQuestion(qIdx, { text: e.target.value })} required />
              </label>
              <label className="field">
                <span>Tip</span>
                <select value={q.type} onChange={(e) => updateQuestion(qIdx, { type: e.target.value })}>
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
            <button type="button" className="btn-link btn-danger" onClick={() => removeQuestion(qIdx)}>
              Șterge hotărârea
            </button>
            <hr />
          </div>
        ))}
        <button type="button" className="btn" onClick={addQuestion}>
          + Adaugă hotărâre
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
              {e.is_active ? "Activ" : "Inactiv"} · {e.questions.length} hotărâri
              {e.require_signature ? " · semnătură obligatorie" : ""}
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
