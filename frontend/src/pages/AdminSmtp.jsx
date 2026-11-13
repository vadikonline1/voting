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
      setMessage("Setările au fost salvate.");
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

  const locked = Boolean(form.env_managed);

  return (
    <form className="card smtp-card" onSubmit={handleSave}>
      <div className="page-head">
        <h2>Setări SMTP</h2>
        <span className={`status-pill ${form.enabled ? "status-on" : "status-off"}`}>
          {form.enabled ? "Activ" : "Dezactivat"}
        </span>
      </div>

      {locked ? (
        <div className="info-box env-notice">
          <strong>Conexiunea SMTP este setată din fișierul <code>.env</code>.</strong>
          <p>
            Host, port, utilizator, parolă, expeditor și STARTTLS nu se mai modifică din panou; le găsiți
            în variabilele <code>SMTP_*</code>. Din panou puteți modifica doar subiectul și conținutul emailului.
          </p>
        </div>
      ) : (
        <p className="muted">
          Folosite pentru a trimite automat confirmarea votului pe email, atunci când votantul indică o
          adresă de email. Dacă trimiterea cu PDF este activată din setările votului, buletinul semnat este
          atașat; altfel emailul conține textul legal și linkul de descărcare. Copiile CC/BCC se configurează
          per vot.
        </p>
      )}

      <fieldset className="smtp-fieldset" disabled={locked}>
        <label className="checkbox-field">
          <input
            type="checkbox"
            checked={form.enabled}
            onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
          />
          Activează trimiterea pe email
        </label>

        <div className="form-section-title">Server</div>
        <div className="field-row">
          <label className="field">
            <span>Host SMTP</span>
            <input value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} placeholder="smtp.gmail.com" />
          </label>
          <label className="field field-narrow">
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
            <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </label>
        </div>

        <div className="field-row">
          <label className="field">
            <span>Email expeditor</span>
            <input value={form.from_email} onChange={(e) => setForm({ ...form, from_email: e.target.value })} />
          </label>
          <p className="muted field-hint">
            Numele expeditorului este întotdeauna numărul APC al votului (ex. <code>12</code>).
          </p>
        </div>

        <label className="checkbox-field">
          <input type="checkbox" checked={form.use_tls} onChange={(e) => setForm({ ...form, use_tls: e.target.checked })} />
          Folosește STARTTLS (recomandat pentru portul 587)
        </label>
      </fieldset>

      <div className="form-section-title">Conținutul emailului</div>
      <label className="field">
        <span>Subiect email</span>
        <input value={form.subject_template} onChange={(e) => setForm({ ...form, subject_template: e.target.value })} />
      </label>
      <label className="field">
        <span>Conținut email</span>
        <textarea rows={6} value={form.body_template} onChange={(e) => setForm({ ...form, body_template: e.target.value })} />
      </label>
      <p className="muted">
        Variabile: <code>{"{voter_name}"}</code> <code>{"{election_title}"}</code> <code>{"{submitted_at}"}</code>{" "}
        <code>{"{nr_apc}"}</code> — expeditorul este întotdeauna numărul APC.
        <br />
        <code>{"{buletin}"}</code> — locul în care se inserează buletinul completat (în HTML, același conținut ca PDF-ul).
        Dacă lipsește, buletinul este adăugat după text.
      </p>

      {error && <p className="error">{error}</p>}
      {message && <p className="success">{message}</p>}

      <div className="actions-row">
        <button className="btn btn-primary" type="submit" disabled={saving}>
          {saving ? "Se salvează..." : "Salvează setările"}
        </button>
      </div>

      <div className="test-box">
        <div className="form-section-title">Test trimitere</div>
        <div className="test-row">
          <input
            placeholder="email@exemplu.com"
            value={testEmail}
            onChange={(e) => setTestEmail(e.target.value)}
            aria-label="Adresa pentru emailul de test"
          />
          <button className="btn" type="button" onClick={handleTest} disabled={!testEmail}>
            Trimite email de test
          </button>
        </div>
      </div>
    </form>
  );
}
