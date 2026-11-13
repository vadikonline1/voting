import { useState } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import { api } from "../api";

export default function AdminChangePassword() {
  const { mustChangePassword, onPasswordChanged } = useOutletContext();
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const navigate = useNavigate();

  function setField(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
    setError("");
    setMessage("");
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setMessage("");

    if (!form.current) {
      setError("Introduceți parola actuală.");
      return;
    }
    if (form.next.length < 8) {
      setError("Parola nouă trebuie să aibă cel puțin 8 caractere.");
      return;
    }
    if (form.next === form.current) {
      setError("Parola nouă trebuie să fie diferită de cea actuală.");
      return;
    }
    if (form.next !== form.confirm) {
      setError("Parolele noi nu coincid.");
      return;
    }

    setSaving(true);
    try {
      await api.changePassword(form.current, form.next);
      setMessage("Parola a fost schimbată cu succes.");
      setForm({ current: "", next: "", confirm: "" });
      if (onPasswordChanged) onPasswordChanged();
      setTimeout(() => navigate("/admin", { replace: true }), 700);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="card" onSubmit={handleSubmit} style={{ maxWidth: 520 }}>
      <h2>Schimbă parola</h2>

      {mustChangePassword && (
        <div className="info-box">
          Contul folosește încă parola inițială. Din motive de securitate, trebuie să o
          schimbați înainte de a putea administra voturile.
        </div>
      )}

      <label className="field">
        <span>Parola actuală</span>
        <input
          type="password"
          value={form.current}
          onChange={(e) => setField("current", e.target.value)}
          autoComplete="current-password"
          autoFocus
        />
      </label>

      <label className="field">
        <span>Parola nouă (minimum 8 caractere)</span>
        <input
          type="password"
          value={form.next}
          onChange={(e) => setField("next", e.target.value)}
          autoComplete="new-password"
        />
      </label>

      <label className="field">
        <span>Repetați parola nouă</span>
        <input
          type="password"
          value={form.confirm}
          onChange={(e) => setField("confirm", e.target.value)}
          autoComplete="new-password"
        />
      </label>

      {error && <p className="error">{error}</p>}
      {message && <p className="success">{message}</p>}

      <button className="btn btn-primary" type="submit" disabled={saving}>
        {saving ? "Se salvează..." : "Schimbă parola"}
      </button>
    </form>
  );
}
