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
  adresa: "Adresa condominiului",
  bloc: "Blocul",
  email: "Adresa de email",
  properties: "Imobile",
};

/** One property of a type: its number and the block it is in. */
function emptyProperty() {
  return { nr: "", bloc: "", adresa: "" };
}

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
/** Items forced by an exclusive chestiune: if one question of the group is answered with its first
 * option ("Pentru"), the others of the same chestiune get their last option ("Împotriva"). */
function exclusiveForced(questions, answers) {
  const groups = [];
  let current = [];
  let exclusive = false;
  for (const q of questions) {
    if (q.type === "section") {
      if (current.length) groups.push({ exclusive, group: current });
      current = [];
      exclusive = Boolean(q.exclusive);
      continue;
    }
    current.push(q);
  }
  if (current.length) groups.push({ exclusive, group: current });

  const forced = {};
  for (const { exclusive: isExclusive, group } of groups) {
    if (!isExclusive || group.length < 2) continue;
    const winner = group.find((q) => (q.options || []).length && answers[q.id] === q.options[0]);
    if (!winner) continue;
    for (const q of group) {
      if (q.id !== winner.id && (q.options || []).length) {
        forced[q.id] = q.options[q.options.length - 1];
      }
    }
  }
  return forced;
}

/** Applies question dependencies and exclusive chestiuni. Returns the automatic answers, the effective
 * answers and a short reason for each automatic answer (shown under the question). */
function resolveAnswers(questions, answers) {
  const auto = {};
  const effective = {};
  const reasons = {};
  const forcedExclusive = exclusiveForced(questions, answers);

  for (const q of questions) {
    if (q.type === "section") continue;

    if (forcedExclusive[q.id] !== undefined) {
      auto[q.id] = forcedExclusive[q.id];
      effective[q.id] = forcedExclusive[q.id];
      reasons[q.id] = `Răspuns setat automat la „${forcedExclusive[q.id]}”, deoarece ați ales „${q.options[0]}” la altă întrebare din aceeași chestiune.`;
      continue;
    }

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
      const parent = questions.find((p) => p.id === q.depends_on);
      const parentText = parent ? `${labelFor(questions, parent)}. ${parent.text}` : "";
      reasons[q.id] = `Răspuns setat automat la „${forced}”, deoarece la întrebarea „${parentText}” ați ales „${q.depends_value}”.`;
    } else {
      effective[q.id] = answers[q.id];
    }
  }
  return { auto, effective, reasons };
}

const propKey = (p) => `${p.tip_proprietate}|${p.nr_proprietate}`;

/** The questions the owner sees: a chestiune with a property type is shown only when the owner
 * ticked that type (and so are its questions). */
function visibleQuestions(questions, selectedTypes) {
  const out = [];
  let show = true;
  for (const q of questions || []) {
    if (q.type === "section") {
      const wanted = String(q.property_type || "").trim().toLowerCase();
      show = !wanted || selectedTypes.includes(wanted);
    }
    if (show) out.push(q);
  }
  return out;
}

/** Items of the ballot in order: a chestiune (section, label null) or a question with its label.
 * Letters restart after each chestiune. */
function labelledItems(questions) {
  const out = [];
  let counter = 0;
  for (const q of questions || []) {
    if (q.type === "section") {
      counter = 0;
      out.push({ q, label: null });
      continue;
    }
    counter += 1;
    out.push({ q, label: String(q.number || "").trim() || String.fromCharCode(96 + counter) });
  }
  return out;
}

function labelFor(questions, target) {
  const hit = labelledItems(questions).find((it) => it.q.id === target.id);
  return hit && hit.label ? hit.label : "";
}

export default function VotePage() {
  const { nrApc } = useParams();
  const [ballot, setBallot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [answers, setAnswers] = useState({});
  const [voter, setVoter] = useState(EMPTY_VOTER);
  // block / address of the APC the owner belongs to (asked only when the APC has several)
  // property selection: types ticked by the owner, and the numbers typed for each type
  const [selectedTypes, setSelectedTypes] = useState([]);
  // each property of a type: its number and its block, e.g. { apartament: [{ nr: "12", bloc: "E" }] }
  const [numbers, setNumbers] = useState({});
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

  const visibleQs = useMemo(
    () => visibleQuestions(ballot?.questions || [], selectedTypes),
    [ballot, selectedTypes]
  );

  const { auto, effective, reasons } = useMemo(
    () => resolveAnswers(visibleQs, answers),
    [visibleQs, answers]
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
  const addresses = ballot?.adrese || [];
  const blocks = ballot?.blocuri || [];

  // the properties the owner declared: each ticked type with its typed numbers (non-empty, unique)
  const selectedProps = useMemo(() => {
    const out = [];
    for (const tip of selectedTypes) {
      const seen = new Set();
      for (const item of numbers[tip] || []) {
        const nr = (item.nr || "").trim();
        const bloc = (item.bloc || "").trim();
        const adresa = item.adresa || "";
        const key = `${nr}|${bloc}|${adresa}`;
        if (nr && !seen.has(key)) {
          seen.add(key);
          out.push({ tip_proprietate: tip, nr_proprietate: nr, bloc, adresa });
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
      setNumbers((n) => ({ ...n, [tip]: [emptyProperty()] }));
      return;
    }
    // single-property ballots: ticking a type replaces the previous one
    setSelectedTypes(allowMultiple ? [...selectedTypes, tip] : [tip]);
    setNumbers((n) => ({ ...n, [tip]: n[tip]?.length ? n[tip] : [emptyProperty()] }));
  }

  function updateProperty(tip, index, changes) {
    setVoterErrors((prev) => ({ ...prev, properties: undefined }));
    setNumbers((prev) => ({
      ...prev,
      [tip]: (prev[tip] || []).map((item, i) => (i === index ? { ...item, ...changes } : item)),
    }));
  }

  function addNumber(tip) {
    setNumbers((prev) => ({ ...prev, [tip]: [...(prev[tip] || []), emptyProperty()] }));
  }

  function removeNumber(tip, index) {
    setNumbers((prev) => {
      const rest = (prev[tip] || []).filter((_, i) => i !== index);
      return { ...prev, [tip]: rest.length ? rest : [emptyProperty()] };
    });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    const errors = validateVoter(voter, selectedProps);
    const emptyRow = selectedTypes.find((tip) => (numbers[tip] || []).some((item) => !(item.nr || "").trim()));
    if (!errors.properties && emptyRow) {
      errors.properties = `Introduceți numărul pentru fiecare imobil de tip ${tipLabel(emptyRow).toLowerCase()} bifat.`;
    }
    setVoterErrors(errors);

    // Collect every missing or invalid item, so the owner sees exactly what to complete.
    const missing = Object.entries(FIELD_LABELS)
      .filter(([key]) => errors[key])
      .map(([key]) => `${FIELD_LABELS[key]}: ${errors[key]}`);
    // with several addresses, every property says which building it is in
    if (addresses.length > 1) {
      selectedProps
        .filter((p) => !p.adresa)
        .forEach((p) => missing.push(`Adresa condominiului pentru imobilul ${tipLabel(p.tip_proprietate).toLowerCase()} ${p.nr_proprietate}: alegeți adresa.`));
    }
    // the block is mandatory for every property
    selectedProps
      .filter((p) => !p.bloc)
      .forEach((p) => missing.push(`Blocul imobilului ${tipLabel(p.tip_proprietate).toLowerCase()} ${p.nr_proprietate}: completați blocul.`));
    if (!gdpr) missing.push("Acordul GDPR: bifați căsuța de acceptare a prelucrării datelor.");
    if (ballot.require_signature && (!sigRef.current || sigRef.current.isEmpty())) {
      missing.push("Semnătura olografă: semnați în câmpul de mai jos.");
    }
    const unansweredQuestions = visibleQs.filter((q, idx) => {
      if (!q.required || auto[q.id] !== undefined) return false;
      const value = effective[q.id];
      return value === undefined || value === null || value === "" || (Array.isArray(value) && value.length === 0);
    });
    unansweredQuestions.forEach((q) => {
      missing.push(`Întrebarea ${labelFor(visibleQs, q)}: alegeți un răspuns.`);
    });
    if (!gdpr) setGdprError("Trebuie să acceptați prelucrarea datelor personale (GDPR) pentru a vota.");

    if (missing.length > 0) {
      setSummary(missing);
      setError("");
      // scroll to the first field that needs attention
      setTimeout(() => {
        const target = document.querySelector(".field-invalid, .question-missing, .gdpr-field, .property-card-missing, .address-choice-missing");
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
          bloc: p.bloc,
          adresa: addresses.length > 1 ? p.adresa : addresses[0] || "",
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

        <section className="voter-section property-section">
          <h2 className="section-title">Imobilele pe care le dețineți *</h2>
          <p className="property-help">
            Apăsați pe tipul imobilului pe care îl dețineți, apoi scrieți numărul lui.
            {allowMultiple
              ? " Dacă aveți mai multe imobile de același tip, apăsați butonul „Adaugă”."
              : " Puteți alege un singur imobil."}
          </p>
          <div className="property-rows">
            {propertyTypes.map((tip) => {
              const ticked = selectedTypes.includes(tip);
              const disabled = !allowMultiple && selectedTypes.length > 0 && !ticked;
              const rows = numbers[tip] && numbers[tip].length ? numbers[tip] : [emptyProperty()];
              const name = tipLabel(tip);
              return (
                <div key={tip} className={`property-row ${ticked ? "property-row-on" : ""}`}>
                  <button
                    type="button"
                    className="property-toggle"
                    aria-pressed={ticked}
                    disabled={disabled}
                    onClick={() => toggleType(tip)}
                  >
                    <span className="property-box" aria-hidden="true">{ticked ? "✓" : ""}</span>
                    <span className="property-name">{name}</span>
                  </button>
                  {ticked && (
                    <div className="property-fields">
                      {rows.map((item, idx) => (
                        <div key={idx} className="property-field">
                          <div className="property-pair">
                          {addresses.length > 1 && (
                            <div className="property-col property-col-address">
                              <label className="property-field-label" htmlFor={`prop-${tip}-${idx}-adresa`}>
                                Adresa condominiului *
                              </label>
                              <select
                                id={`prop-${tip}-${idx}-adresa`}
                                className="property-input"
                                value={item.adresa || ""}
                                onChange={(e) => updateProperty(tip, idx, { adresa: e.target.value })}
                              >
                                <option value="">— alegeți adresa —</option>
                                {addresses.map((a) => (
                                  <option key={a} value={a}>
                                    {a}
                                  </option>
                                ))}
                              </select>
                            </div>
                          )}
                          <div className="property-col property-col-number">
                          <label className="property-field-label" htmlFor={`prop-${tip}-${idx}`}>
                            Numărul imobilului *{rows.length > 1 ? ` ${idx + 1}` : ""}
                          </label>
                          <div className="property-input-row">
                            <input
                              id={`prop-${tip}-${idx}`}
                              className="property-input"
                              value={item.nr}
                              onChange={(e) => updateProperty(tip, idx, { nr: e.target.value })}
                              placeholder="Scrieți numărul aici"
                              inputMode="text"
                              autoComplete="off"
                              maxLength={30}
                            />
                            {rows.length > 1 && (
                              <button type="button" className="property-remove" onClick={() => removeNumber(tip, idx)}>
                                Șterge
                              </button>
                            )}
                          </div>
                          </div>
                          <div className="property-col property-col-block">
                          <label className="property-field-label" htmlFor={`prop-${tip}-${idx}-bloc`}>
                            Blocul *
                          </label>
                          {blocks.length > 0 ? (
                            <select
                              id={`prop-${tip}-${idx}-bloc`}
                              className="property-input"
                              value={item.bloc || ""}
                              onChange={(e) => updateProperty(tip, idx, { bloc: e.target.value })}
                            >
                              <option value="">— alegeți blocul —</option>
                              {blocks.map((b) => (
                                <option key={b} value={b}>
                                  {b}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <input
                              id={`prop-${tip}-${idx}-bloc`}
                              className="property-input"
                              value={item.bloc || ""}
                              onChange={(e) => updateProperty(tip, idx, { bloc: e.target.value })}
                              maxLength={60}
                              placeholder="ex. Bl. E"
                              autoComplete="off"
                            />
                          )}
                          </div>
                          </div>
                        </div>
                      ))}
                      {allowMultiple && (
                        <button type="button" className="property-add" onClick={() => addNumber(tip)}>
                          + Adaugă alt imobil de tip {name.toLowerCase()}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          {voterErrors.properties && <p className="property-error">{voterErrors.properties}</p>}
        </section>

        <section className="questions-section">
          <h2 className="section-title">Votul dumneavoastră</h2>
          {labelledItems(visibleQs).map(({ q, label }) => {
            if (label === null) {
              return (
                <div key={q.id} className="chestiune-box chestiune-box-vote">
                  <div className="chestiune-label">Chestiunea propusă spre vot</div>
                  <div className="chestiune-text">{q.text}</div>
                  {q.exclusive && (
                    <p className="chestiune-hint">
                      Alegere unică: dacă la o întrebare alegeți „Pentru”, celelalte din această chestiune se completează automat cu „Împotriva”.
                    </p>
                  )}
                </div>
              );
            }
            const forced = auto[q.id];
            const isAuto = forced !== undefined;
            const parent = isAuto ? ballot.questions.find((p) => p.id === q.depends_on) : null;
            const parentLabel = parent
              ? `${labelFor(ballot.questions, parent)}. ${parent.text}`
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
                  <p className="auto-note">{reasons[q.id]}</p>
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
