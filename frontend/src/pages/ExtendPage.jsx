import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { formatDay } from "../dates";

const PERIOD_LABELS = {
  1: "1 zi",
  3: "3 zile",
  7: "1 săptămână",
  14: "2 săptămâni",
  30: "1 lună",
};

function formatDate(iso) {
  // the deadline day, in Chisinau time
  return formatDay(iso);
}

/** Public page behind the secret link sent to the APC: the APC chooses how long to prolong the vote. */
export default function ExtendPage() {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [days, setDays] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(null);

  useEffect(() => {
    api
      .getExtension(token)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [token]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!days) {
      setError("Alegeți perioada de prelungire.");
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      const result = await api.extendVote(token, days);
      setDone(result);
      setData((prev) => ({ ...prev, end_date_vot: result.end_date_vot }));
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <div className="center-page">Se încarcă...</div>;

  if (!data) {
    return (
      <div className="center-page">
        <div className="card">
          <h2>Link indisponibil</h2>
          <p>{error || "Linkul de prelungire nu este valid."}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="center-page">
      <div className="card" style={{ maxWidth: 520, width: "100%" }}>
        <h2>Prelungirea votării</h2>
        <p>
          <strong>APC nr. {data.nr_apc}</strong> · {data.title}
        </p>
        <p>
          Votarea se încheie în prezent la: <strong>{formatDate(data.end_date_vot)}</strong>
        </p>

        {done ? (
          <div className="success-box">
            <p>
              Votarea a fost prelungită. Noua dată de încheiere este <strong>{formatDate(done.end_date_vot)}</strong>.
            </p>
          </div>
        ) : !data.is_active ? (
          <p>Votul nu este activ, prelungirea nu este posibilă. Contactați administratorul.</p>
        ) : (
          <form onSubmit={handleSubmit}>
            <fieldset className="address-choice">
              <legend>Cu cât doriți să prelungiți votarea?</legend>
              {data.options.map((d) => (
                <label key={d} className={`address-option ${days === d ? "address-option-on" : ""}`}>
                  <input type="radio" name="days" value={d} checked={days === d} onChange={() => setDays(d)} />
                  <span>{PERIOD_LABELS[d] || `${d} zile`}</span>
                </label>
              ))}
            </fieldset>
            <p className="muted">
              Perioada se adaugă la data de încheiere actuală (sau de la data curentă, dacă votarea s-a încheiat deja).
            </p>
            {error && <p className="property-error">{error}</p>}
            <button className="btn" type="submit" disabled={submitting}>
              {submitting ? "Se salvează..." : "Prelungește votarea"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
