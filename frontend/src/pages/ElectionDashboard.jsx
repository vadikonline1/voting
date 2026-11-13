import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import ResultsView from "../components/ResultsView";

const REFRESH_MS = 5000;

export default function ElectionDashboard() {
  const { uuid } = useParams();
  const [results, setResults] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let timer = null;

    async function load() {
      try {
        const data = await api.publicResults(uuid);
        if (!cancelled) {
          setResults(data);
          setError("");
        }
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    timer = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [uuid]);

  if (loading) {
    return <div className="center-page">Se încarcă rezultatele...</div>;
  }

  if (error && !results) {
    return (
      <div className="center-page">
        <div className="card">
          <h2>Rezultate indisponibile</h2>
          <p className="error">{error}</p>
          <p className="muted">Verificați link-ul dashboardului primit de la comisia electorală.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="public-dashboard">
      <header className="public-dashboard-header">
        <div>
          <span className="eyebrow">Rezultate vot APC · în timp real</span>
          <h1>{results.title}</h1>
        </div>
        <span className="live-indicator">
          <span className="live-dot" /> actualizare automată la 5 secunde
        </span>
      </header>

      {error && <p className="error">{error}</p>}

      <ResultsView results={results} title={false} />

      <p className="muted dashboard-footer">
        Rezultatele se actualizează automat. Sunt afișate doar datele agregate, fără date
        personale ale votanților.
      </p>
    </div>
  );
}
