import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import SignaturePad from "../components/SignaturePad";

const STATUS_MESSAGES = {
  voted: "Ați votat deja folosind acest link. Vă mulțumim pentru participare!",
  closed: "Perioada de votare s-a încheiat.",
};

export default function VotePage() {
  const { uuid } = useParams();
  const [ballot, setBallot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [answers, setAnswers] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(null);
  const sigRef = useRef(null);

  useEffect(() => {
    api
      .getBallot(uuid)
      .then(setBallot)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [uuid]);

  function setAnswer(qid, value) {
    setAnswers((prev) => ({ ...prev, [qid]: value }));
  }

  function toggleMultiple(qid, option) {
    setAnswers((prev) => {
      const current = Array.isArray(prev[qid]) ? prev[qid] : [];
      const next = current.includes(option)
        ? current.filter((o) => o !== option)
        : [...current, option];
      return { ...prev, [qid]: next };
    });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    if (ballot.require_signature && (!sigRef.current || sigRef.current.isEmpty())) {
      setError("Vă rugăm să semnați olograf înainte de a trimite votul.");
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        answers,
        signature_png_base64: ballot.require_signature ? sigRef.current.toPngBase64() : null,
      };
      const result = await api.submitVote(uuid, payload);
      setDone(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <div className="center-page">Se încarcă buletinul de vot...</div>;

  if (error && !ballot) {
    return (
      <div className="center-page">
        <div className="card">
          <h2>Link indisponibil</h2>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  if (ballot && ballot.status !== "open" && !done) {
    return (
      <div className="center-page">
        <div className="card">
          <h1 className="ballot-title">{ballot.title}</h1>
          <p className="status-message">{STATUS_MESSAGES[ballot.status] || "Votarea nu este disponibilă."}</p>
          {ballot.already_voted && (
            <a className="btn" href={api.receiptUrl(uuid)} target="_blank" rel="noreferrer">
              Descarcă confirmarea votului (PDF)
            </a>
          )}
        </div>
      </div>
    );
  }

  if (done) {
    return (
      <div className="center-page">
        <div className="card">
          <h1>Vot înregistrat ✓</h1>
          <p>Votul dumneavoastră a fost înregistrat cu succes.</p>
          {done.email_sent && <p>O confirmare cu buletinul semnat a fost trimisă pe email.</p>}
          <a className="btn" href={api.receiptUrl(uuid)} target="_blank" rel="noreferrer">
            Descarcă confirmarea votului (PDF)
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="vote-page">
      <form className="card vote-card" onSubmit={handleSubmit}>
        <h1 className="ballot-title">{ballot.title}</h1>

        <div className="date-city-row">
          <span>{ballot.date_line}</span>
          <span>{ballot.city_line}</span>
        </div>

        <p className="ballot-paragraph">{ballot.paragraph1}</p>
        <p className="ballot-paragraph">{ballot.paragraph2}</p>

        {ballot.questions.map((q, idx) => (
          <fieldset key={q.id} className="question">
            <legend>
              Hotărârea nr. {idx + 1}: {q.text} {q.required && <span className="required">*</span>}
            </legend>
            {q.options.map((opt) => (
              <label key={opt} className="option">
                <input
                  type={q.type === "multiple" ? "checkbox" : "radio"}
                  name={q.id}
                  value={opt}
                  checked={
                    q.type === "multiple"
                      ? Array.isArray(answers[q.id]) && answers[q.id].includes(opt)
                      : answers[q.id] === opt
                  }
                  onChange={() =>
                    q.type === "multiple" ? toggleMultiple(q.id, opt) : setAnswer(q.id, opt)
                  }
                />
                {opt}
              </label>
            ))}
          </fieldset>
        ))}

        {ballot.require_signature && (
          <div className="field">
            <span>Semnătură olografă *</span>
            <SignaturePad ref={sigRef} />
            <button
              type="button"
              className="btn-link"
              onClick={() => sigRef.current && sigRef.current.clear()}
            >
              Șterge semnătura
            </button>
          </div>
        )}

        {error && <p className="error">{error}</p>}

        <button className="btn btn-primary" type="submit" disabled={submitting}>
          {submitting ? "Se trimite..." : "Trimite votul"}
        </button>
      </form>
    </div>
  );
}
