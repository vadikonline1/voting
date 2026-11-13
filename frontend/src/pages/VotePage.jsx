import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import SignaturePad from "../components/SignaturePad";

const STATUS_MESSAGES = {
  voted: "Ați votat deja folosind acest link. Vă mulțumim pentru participare!",
  closed: "Perioada de votare s-a încheiat.",
};

const NAME_RE = /^[A-Za-zÀ-ÖØ-öø-ÿĀ-ž' .-]+$/;
const PHONE_RE = /^\+?[0-9][0-9 ()\-.]{5,19}$/;
const PROP_RE = /^[0-9A-Za-zÀ-ÖØ-öø-ÿĀ-ž/ .-]+$/;
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/;

const EMPTY_VOTER = {
  nume_prenume: "",
  phone: "",
  str_locatar: "",
  email: "",
  nr_proprietate: "",
};

function validateVoter(voter) {
  const errors = {};
  const name = (voter.nume_prenume || "").trim();
  const phone = (voter.phone || "").trim();
  const address = (voter.str_locatar || "").trim();
  const email = (voter.email || "").trim();
  const property = (voter.nr_proprietate || "").trim();

  if (name.length < 3 || name.length > 120) {
    errors.nume_prenume = "Introduceți numele și prenumele (3–120 caractere).";
  } else if (name.split(/\s+/).length < 2) {
    errors.nume_prenume = "Introduceți atât numele, cât și prenumele.";
  } else if (!NAME_RE.test(name)) {
    errors.nume_prenume = "Numele poate conține doar litere, spații, punct, apostrof și cratimă.";
  }

  const digits = phone.replace(/\D/g, "");
  if (!PHONE_RE.test(phone) || digits.length < 6 || digits.length > 15) {
    errors.phone = "Număr de telefon invalid (6–15 cifre; poate începe cu +).";
  }

  if (address.length < 5 || address.length > 250) {
    errors.str_locatar = "Adresa trebuie să aibă între 5 și 250 de caractere.";
  }

  if (!EMAIL_RE.test(email) || email.length > 160) {
    errors.email = "Adresa de email nu este validă.";
  }

  if (property.length < 1 || property.length > 30 || !PROP_RE.test(property)) {
    errors.nr_proprietate = "Numărul unității nu este valid.";
  }

  return errors;
}

function cleanVoter(voter) {
  return Object.fromEntries(
    Object.entries(EMPTY_VOTER).map(([key]) => [key, (voter[key] || "").trim()])
  );
}

/** Applies question dependencies: a triggered question is disabled and forced to `auto_answer`. */
function resolveAnswers(questions, answers) {
  const auto = {};
  const effective = {};
  for (const q of questions) {
    let triggered = false;
    if (q.depends_on && q.type !== "multiple") {
      const parentValue = effective[q.depends_on];
      triggered =
        parentValue !== undefined &&
        parentValue !== null &&
        parentValue !== "" &&
        String(parentValue) === String(q.depends_value);
    }
    if (triggered) {
      const options = q.options || [];
      const forced = q.auto_answer || options[options.length - 1] || "";
      auto[q.id] = forced;
      effective[q.id] = forced;
    } else {
      effective[q.id] = answers[q.id];
    }
  }
  return { auto, effective };
}

export default function VotePage() {
  const { uuid } = useParams();
  const [ballot, setBallot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [answers, setAnswers] = useState({});
  const [voter, setVoter] = useState(EMPTY_VOTER);
  const [voterErrors, setVoterErrors] = useState({});
  const [gdpr, setGdpr] = useState(false);
  const [gdprError, setGdprError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(null);
  const sigRef = useRef(null);

  useEffect(() => {
    api
      .getBallot(uuid)
      .then((data) => {
        setBallot(data);
        setVoter({ ...EMPTY_VOTER, ...(data.voter || {}) });
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [uuid]);

  const { auto, effective } = useMemo(
    () => resolveAnswers(ballot?.questions || [], answers),
    [ballot, answers]
  );

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

  function setVoterField(key, value) {
    setVoter((prev) => ({ ...prev, [key]: value }));
    setVoterErrors((prev) => ({ ...prev, [key]: undefined }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    const errors = validateVoter(voter);
    setVoterErrors(errors);
    if (Object.keys(errors).length > 0) {
      setError("Verificați datele introduse mai jos.");
      return;
    }
    if (!gdpr) {
      setGdprError("Trebuie să acceptați prelucrarea datelor personale (GDPR) pentru a vota.");
      setError("Confirmați acordul GDPR pentru a trimite votul.");
      return;
    }
    if (ballot.require_signature && (!sigRef.current || sigRef.current.isEmpty())) {
      setError("Vă rugăm să semnați olograf înainte de a trimite votul.");
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        answers: effective,
        voter: cleanVoter(voter),
        gdpr_consent: true,
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
          {done.email_sent && <p>O confirmare a fost trimisă pe adresa de email indicată.</p>}
          <a className="btn" href={api.receiptUrl(uuid)} target="_blank" rel="noreferrer">
            Descarcă confirmarea votului (PDF)
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="vote-page">
      <form className="card vote-card" onSubmit={handleSubmit} noValidate>
        <h1 className="ballot-title">{ballot.title}</h1>

        <div className="date-city-row">
          <span>{ballot.date_line}</span>
          <span>{ballot.city_line}</span>
        </div>

        <section className="voter-section">
          <h2 className="section-title">Datele proprietarului</h2>
          <p className="muted section-hint">
            Completați datele dumneavoastră. Acestea apar în buletinul de vot din PDF și în emailul de confirmare.
          </p>

          <div className="field-row">
            <label className={`field ${voterErrors.nume_prenume ? "field-invalid" : ""}`}>
              <span>
                Nume și prenume <span className="required">*</span>
              </span>
              <input
                value={voter.nume_prenume}
                onChange={(e) => setVoterField("nume_prenume", e.target.value)}
                placeholder="Ion Popescu"
                autoComplete="name"
                maxLength={120}
              />
              {voterErrors.nume_prenume && <span className="field-error">{voterErrors.nume_prenume}</span>}
            </label>
            <label className={`field ${voterErrors.phone ? "field-invalid" : ""}`}>
              <span>
                Telefon <span className="required">*</span>
              </span>
              <input
                value={voter.phone}
                onChange={(e) => setVoterField("phone", e.target.value)}
                placeholder="+373 69 123 456"
                autoComplete="tel"
                inputMode="tel"
                maxLength={20}
              />
              {voterErrors.phone && <span className="field-error">{voterErrors.phone}</span>}
            </label>
          </div>

          <label className={`field ${voterErrors.str_locatar ? "field-invalid" : ""}`}>
            <span>
              Adresa de corespondență poștală <span className="required">*</span>
            </span>
            <input
              value={voter.str_locatar}
              onChange={(e) => setVoterField("str_locatar", e.target.value)}
              placeholder="str. Exemplu 1, ap. 5, Chișinău"
              autoComplete="street-address"
              maxLength={250}
            />
            {voterErrors.str_locatar && <span className="field-error">{voterErrors.str_locatar}</span>}
          </label>

          <div className="field-row">
            <label className={`field ${voterErrors.email ? "field-invalid" : ""}`}>
              <span>
                Adresă electronică (email) <span className="required">*</span>
              </span>
              <input
                type="email"
                value={voter.email}
                onChange={(e) => setVoterField("email", e.target.value)}
                placeholder="ion.popescu@exemplu.com"
                autoComplete="email"
                inputMode="email"
                maxLength={160}
              />
              {voterErrors.email && <span className="field-error">{voterErrors.email}</span>}
            </label>
            <label className={`field ${voterErrors.nr_proprietate ? "field-invalid" : ""}`}>
              <span>
                Nr. unității (bunului imobil) <span className="required">*</span>
              </span>
              <input
                value={voter.nr_proprietate}
                onChange={(e) => setVoterField("nr_proprietate", e.target.value)}
                placeholder="12"
                maxLength={30}
              />
              {voterErrors.nr_proprietate && (
                <span className="field-error">{voterErrors.nr_proprietate}</span>
              )}
            </label>
          </div>
        </section>

        <section className="questions-section">
          <h2 className="section-title">Votul dumneavoastră</h2>
          {ballot.questions.map((q, idx) => {
            const label = String(q.number || "").trim() || String(idx + 1);
            const forced = auto[q.id];
            const isAuto = forced !== undefined;
            const parent = isAuto ? ballot.questions.find((p) => p.id === q.depends_on) : null;
            const parentLabel = parent
              ? `${String(parent.number || "").trim() || ballot.questions.indexOf(parent) + 1}. ${parent.text}`
              : "";
            return (
              <fieldset key={q.id} className={`question ${isAuto ? "question-auto" : ""}`}>
                <legend>
                  <span className="q-number">{label}.</span> {q.text}{" "}
                  {q.required && !isAuto && <span className="required">*</span>}
                </legend>
                {q.options.map((opt) => {
                  const checked = isAuto
                    ? opt === forced
                    : q.type === "multiple"
                      ? Array.isArray(answers[q.id]) && answers[q.id].includes(opt)
                      : answers[q.id] === opt;
                  return (
                    <label key={opt} className={`option ${isAuto ? "option-disabled" : ""}`}>
                      <input
                        type={q.type === "multiple" ? "checkbox" : "radio"}
                        name={q.id}
                        value={opt}
                        checked={checked}
                        disabled={isAuto}
                        onChange={() =>
                          q.type === "multiple" ? toggleMultiple(q.id, opt) : setAnswer(q.id, opt)
                        }
                      />
                      {opt}
                    </label>
                  );
                })}
                {isAuto && (
                  <p className="auto-note">
                    Răspuns setat automat la „{forced}”, deoarece la întrebarea „{parentLabel}” ați ales „
                    {q.depends_value}”.
                  </p>
                )}
              </fieldset>
            );
          })}
        </section>

        <label className={`checkbox-field gdpr-field ${gdprError ? "field-invalid" : ""}`}>
          <input
            type="checkbox"
            checked={gdpr}
            onChange={(e) => {
              setGdpr(e.target.checked);
              if (e.target.checked) setGdprError("");
            }}
          />
          <span>
            {ballot.gdpr_text} <span className="required">*</span>
          </span>
        </label>
        {gdprError && <p className="field-error">{gdprError}</p>}

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
