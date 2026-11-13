import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import SignaturePad from "../components/SignaturePad";

const STATUS_MESSAGES = {
  closed: "Perioada de votare s-a încheiat sau votarea nu este activă.",
};

const TIP_LABELS = { apartament: "Apartament", debara: "Debara", parcare: "Parcare" };

/** Known types get their Romanian label; custom types from the admin are capitalised. */
function tipLabel(tip) {
  return TIP_LABELS[tip] || tip.charAt(0).toUpperCase() + tip.slice(1);
}

const NAME_RE = /^[A-Za-zÀ-ÖØ-öø-ÿĀ-ž' .-]+$/;
const PHONE_RE = /^\+?[0-9][0-9 ()\-.]{5,19}$/;
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/;

const FIELD_LABELS = {
  nume_prenume: "Nume și prenume",
  phone: "Telefon",
  str_locatar: "Adresa de corespondență",
  email: "Adresa de email",
  properties: "Imobile",
};

const EMPTY_VOTER = {
  nume_prenume: "",
  phone: "",
  str_locatar: "",
  email: "",
};

function validateVoter(voter, selectedProps) {
  const errors = {};
  const name = (voter.nume_prenume || "").trim();
  const phone = (voter.phone || "").trim();
  const address = (voter.str_locatar || "").trim();
  const email = (voter.email || "").trim();

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

  // Email is optional: without it the confirmation is sent to the APC address.
  if (email && (!EMAIL_RE.test(email) || email.length > 160)) {
    errors.email = "Adresa de email nu este validă.";
  }

  if (selectedProps.length === 0) {
    errors.properties = "Bifați cel puțin un imobil pe care îl dețineți.";
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

const propKey = (p) => `${p.tip_proprietate}|${p.nr_proprietate}`;

export default function VotePage() {
  const { nrApc } = useParams();
  const [ballot, setBallot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [answers, setAnswers] = useState({});
  const [voter, setVoter] = useState(EMPTY_VOTER);
  // property selection: types ticked by the owner, and the numbers typed for each type
  const [selectedTypes, setSelectedTypes] = useState([]);
  const [numbers, setNumbers] = useState({}); // { apartament: ["12", "14"], ... }
  const [voterErrors, setVoterErrors] = useState({});
  const [gdpr, setGdpr] = useState(false);
  const [gdprError, setGdprError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(null);
  const [summary, setSummary] = useState([]);
  const sigRef = useRef(null);

  useEffect(() => {
    api
      .getApcBallot(nrApc)
      .then(setBallot)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [nrApc]);

  const { auto, effective } = useMemo(
    () => resolveAnswers(ballot?.questions || [], answers),
    [ballot, answers]
  );

  // property types offered by the APC, in the order the admin listed them
  const propertyTypes = useMemo(() => {
    const seen = [];
    for (const p of ballot?.properties || []) {
      if (!seen.includes(p.tip_proprietate)) seen.push(p.tip_proprietate);
    }
    return seen;
  }, [ballot]);

  const allowMultiple = ballot?.allow_multiple_properties !== false;

  // the properties the owner declared: each ticked type with its typed numbers (non-empty, unique)
  const selectedProps = useMemo(() => {
    const out = [];
    for (const tip of selectedTypes) {
      const seen = new Set();
      for (const raw of numbers[tip] || []) {
        const nr = (raw || "").trim();
        if (nr && !seen.has(nr)) {
          seen.add(nr);
          out.push({ tip_proprietate: tip, nr_proprietate: nr });
        }
      }
    }
    return out;
  }, [selectedTypes, numbers]);

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

  function toggleType(tip) {
    setVoterErrors((prev) => ({ ...prev, properties: undefined }));
    if (selectedTypes.includes(tip)) {
      setSelectedTypes(selectedTypes.filter((t) => t !== tip));
      setNumbers((n) => ({ ...n, [tip]: [""] }));
      return;
    }
    // single-property ballots: ticking a type replaces the previous one
    setSelectedTypes(allowMultiple ? [...selectedTypes, tip] : [tip]);
    setNumbers((n) => ({ ...n, [tip]: n[tip]?.length ? n[tip] : [""] }));
  }

  function setNumber(tip, index, value) {
    setVoterErrors((prev) => ({ ...prev, properties: undefined }));
    setNumbers((prev) => ({
      ...prev,
      [tip]: (prev[tip] || []).map((v, i) => (i === index ? value : v)),
    }));
  }

  function addNumber(tip) {
    setNumbers((prev) => ({ ...prev, [tip]: [...(prev[tip] || []), ""] }));
  }

  function removeNumber(tip, index) {
    setNumbers((prev) => {
      const rest = (prev[tip] || []).filter((_, i) => i !== index);
      return { ...prev, [tip]: rest.length ? rest : [""] };
    });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    const errors = validateVoter(voter, selectedProps);
    const emptyRow = selectedTypes.find((tip) => (numbers[tip] || []).some((nr) => !(nr || "").trim()));
    if (!errors.properties && emptyRow) {
      errors.properties = `Introduceți numărul pentru fiecare imobil de tip ${tipLabel(emptyRow).toLowerCase()} bifat.`;
    }
    setVoterErrors(errors);

    // Collect every missing or invalid item, so the owner sees exactly what to complete.
    const missing = Object.entries(FIELD_LABELS)
      .filter(([key]) => errors[key])
      .map(([key]) => `${FIELD_LABELS[key]}: ${errors[key]}`);
    if (!gdpr) missing.push("Acordul GDPR: bifați căsuța de acceptare a prelucrării datelor.");
    if (ballot.require_signature && (!sigRef.current || sigRef.current.isEmpty())) {
      missing.push("Semnătura olografă: semnați în câmpul de mai jos.");
    }
    const unansweredQuestions = ballot.questions.filter((q, idx) => {
      if (!q.required || auto[q.id] !== undefined) return false;
      const value = effective[q.id];
      return value === undefined || value === null || value === "" || (Array.isArray(value) && value.length === 0);
    });
    unansweredQuestions.forEach((q) => {
      missing.push(`Hotărârea ${String(q.number || "").trim() || ballot.questions.indexOf(q) + 1}: alegeți un răspuns.`);
    });
    if (!gdpr) setGdprError("Trebuie să acceptați prelucrarea datelor personale (GDPR) pentru a vota.");

    if (missing.length > 0) {
      setSummary(missing);
      setError("");
      // scroll to the first field that needs attention
      setTimeout(() => {
        const target = document.querySelector(".field-invalid, .question-missing, .gdpr-field, .property-card-missing");
        if (target) target.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 0);
      return;
    }
    setSummary([]);

    setSubmitting(true);
    try {
      const payload = {
        answers: effective,
        voter: cleanVoter(voter),
        properties: selectedProps.map((p) => ({
          tip_proprietate: p.tip_proprietate,
          nr_proprietate: p.nr_proprietate,
        })),
        gdpr_consent: true,
        signature_png_base64: ballot.require_signature ? sigRef.current.toPngBase64() : null,
      };
      const result = await api.submitApcVote(nrApc, payload);
      setDone(result);
    } catch (e) {
      // e.g. "Imobilul ... a fost deja votat. Verificați emailul pu****im@gmail.com."
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
          <h2>Vot indisponibil</h2>
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
          <p className="status-message">{STATUS_MESSAGES.closed}</p>
        </div>
      </div>
    );
  }

  if (done) {
    return (
      <div className="center-page">
        <div className="card">
          <h1>Vot înregistrat ✓</h1>
          <p>Votul dumneavoastră a fost înregistrat pentru {done.properties.length} imobil(e).</p>
          {done.email_sent && done.email_recipient && (
            <p>Confirmarea cu buletinul semnat a fost trimisă la {done.email_recipient}.</p>
          )}
          <div className="actions-row success-actions">
            <a className="btn btn-primary" href={`${done.receipt_url}?inline=1`} target="_blank" rel="noreferrer">
              Deschide votul
            </a>
            <a className="btn" href={done.receipt_url} target="_blank" rel="noreferrer">
              Descarcă confirmarea votului (PDF)
            </a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="vote-page">
      <form className="card vote-card" onSubmit={handleSubmit} noValidate>
        <h1 className="ballot-title">{ballot.title}</h1>

        {summary.length > 0 && (
          <div className="error-summary" role="alert">
            <strong>Mai trebuie completate sau corectate:</strong>
            <ul>
              {summary.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="date-city-row">
          <span>{ballot.date_line}</span>
          <span>{ballot.city_line}</span>
        </div>

        <section className="voter-section">
          <h2 className="section-title">Datele proprietarului</h2>

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

          <label className={`field ${voterErrors.email ? "field-invalid" : ""}`}>
            <span>Adresă electronică (email)</span>
            <input
              type="email"
              value={voter.email}
              onChange={(e) => setVoterField("email", e.target.value)}
              placeholder="ion.popescu@exemplu.com"
              autoComplete="email"
              inputMode="email"
              maxLength={160}
            />
            <span className="muted section-hint">
              Dacă nu aveți email, confirmarea cu buletinul PDF va fi trimisă administratorului APC.
            </span>
            {voterErrors.email && <span className="field-error">{voterErrors.email}</span>}
          </label>
        </section>

        <section className="voter-section">
          <h2 className="section-title">Imobilele pe care le dețineți *</h2>
          <p className="muted section-hint">
            Bifați toate imobilele pentru care dați votul. Votul se aplică la fiecare imobil bifat;
            un imobil poate fi votat o singură dată.
          </p>
          <p className="muted section-hint">
            {allowMultiple
              ? "Puteți selecta mai multe imobile."
              : "Acest vot permite selectarea unui singur imobil."}
          </p>
          <div className="property-grid">
            {propertyTypes.map((tip) => {
              const ticked = selectedTypes.includes(tip);
              const disabled = !allowMultiple && selectedTypes.length > 0 && !ticked;
              const rows = numbers[tip] && numbers[tip].length ? numbers[tip] : [""];
              return (
                <div key={tip} className={`property-card ${ticked ? "property-card-on" : ""}`}>
                  <label className="checkbox-field">
                    <input
                      type="checkbox"
                      checked={ticked}
                      disabled={disabled}
                      onChange={() => toggleType(tip)}
                    />
                    <span className="property-title">{tipLabel(tip)}</span>
                  </label>
                  {ticked && (
                    <div className="property-numbers">
                      {rows.map((nr, idx) => (
                        <div key={idx} className="property-number-row">
                          <input
                            value={nr}
                            onChange={(e) => setNumber(tip, idx, e.target.value)}
                            placeholder="Introduceți numărul"
                            maxLength={30}
                          />
                          {rows.length > 1 && (
                            <button type="button" className="btn-link" onClick={() => removeNumber(tip, idx)}>
                              Șterge
                            </button>
                          )}
                        </div>
                      ))}
                      {allowMultiple && (
                        <button type="button" className="btn-link" onClick={() => addNumber(tip)}>
                          + Adaugă alt imobil de tip {(TIP_LABELS[tip] || tip).toLowerCase()}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          {voterErrors.properties && <span className="field-error">{voterErrors.properties}</span>}
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
