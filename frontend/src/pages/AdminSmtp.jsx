import { useEffect, useState } from "react";
import { api } from "../api";

export default function AdminSmtp() {
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [testEmail, setTestEmail] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.getSmtp().then((data) => setForm({ ...data, password: "" })).catch((e) => setError(e.message));
  }, []);

  async function handleSave(e) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const payload = { ...form, password: form.password || null };
      const updated = await api.updateSmtp(payload);
      setForm({ ...updated, password: "" });
      setMessage("Setările SMTP au fost salvate.");
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setError("");
    setMessage("");
    try {
      await api.testSmtp(testEmail);
      setMessage(`Email de test trimis către ${testEmail}.`);
    } catch (e) {
      setError(e.message);
    }
  }

  if (!form) return <p>Se încarcă...</p>;

  return (
    <form className="card" onSubmit={handleSave}>
      <h2>Setări SMTP</h2>
      <p className="muted">
        Folosite pentru a trimite automat confirmarea votului pe email, atunci când votantul indică o
        adresă de email. Dacă trimiterea cu PDF este activată din setările votului, buletinul semnat este
        atașat; altfel emailul conține textul legal și linkul de descărcare. Copiile CC/BCC se configurează
        per vot.
      </p>

      <label className="checkbox-field">
        <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
        Activează trimiterea pe email
      </label>

      <div className="field-row">
        <label className="field">
          <span>Host SMTP</span>
          <input value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} placeholder="smtp.gmail.com" />
        </label>
        <label className="field">
          <span>Port</span>
          <input type="number" value={form.port} onChange={(e) => setForm({ ...form, port: Number(e.target.value) })} />
        </label>
      </div>

      <div className="field-row">
        <label className="field">
          <span>Utilizator</span>
          <input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
        </label>
        <label className="field">
          <span>Parolă {form.has_password && "(setată — lasă gol ca să o păstrezi)"}</span>
          <input
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
        </label>
      </div>

      <div className="field-row">
        <label className="field">
          <span>Email expeditor</span>
          <input value={form.from_email} onChange={(e) => setForm({ ...form, from_email: e.target.value })} />
        </label>
        <label className="field">
          <span>Nume expeditor</span>
          <input value={form.from_name} onChange={(e) => setForm({ ...form, from_name: e.target.value })} />
        </label>
      </div>

      <label className="checkbox-field">
        <input type="checkbox" checked={form.use_tls} onChange={(e) => setForm({ ...form, use_tls: e.target.checked })} />
        Folosește STARTTLS (recomandat pentru portul 587)
      </label>

      <label className="field">
        <span>Subiect email</span>
        <input value={form.subject_template} onChange={(e) => setForm({ ...form, subject_template: e.target.value })} />
      </label>
      <label className="field">
        <span>Conținut email</span>
        <textarea rows={6} value={form.body_template} onChange={(e) => setForm({ ...form, body_template: e.target.value })} />
      </label>
      <p className="muted">Variabile disponibile: {"{voter_name}"}, {"{election_title}"}, {"{submitted_at}"}</p>

      {error && <p className="error">{error}</p>}
      {message && <p className="success">{message}</p>}

      <div className="actions-row">
        <button className="btn btn-primary" type="submit" disabled={saving}>
          {saving ? "Se salvează..." : "Salvează setările"}
        </button>
      </div>

      <hr />
      <h3>Test trimitere</h3>
      <div className="field-row">
        <input placeholder="email@exemplu.com" value={testEmail} onChange={(e) => setTestEmail(e.target.value)} />
        <button className="btn" type="button" onClick={handleTest}>
          Trimite email de test
        </button>
      </div>
    </form>
  );
}
