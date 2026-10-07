import { useState } from "react";
import { api } from "../api.js";
import { useSite } from "../context.jsx";
import { useLang } from "../i18n.jsx";
import { TextSection } from "../components/ui.jsx";
import { SectionPage } from "../components/content.jsx";

const EMPTY = { full_name: "", contact: "", subject: "", message: "", consent: false, website: "" };
const REQUIRED = ["full_name", "contact", "subject", "message"];

function AppealForm() {
  const { t, lang } = useLang();
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [state, setState] = useState("idle"); // idle | sending | sent | error | throttled

  // Общие свойства поля: значение, обработчик и связь с текстом ошибки для экранных дикторов
  const bind = (key) => ({
    id: `ap-${key}`,
    ...(key === "consent" ? { checked: form.consent } : { value: form[key] }),
    onChange: (e) => setForm((f) => ({ ...f, [key]: e.target.type === "checkbox" ? e.target.checked : e.target.value })),
    ...(errors[key] && { "aria-invalid": true, "aria-describedby": `ap-${key}-error` }),
  });

  const error = (key) =>
    errors[key] && (
      <p className="field-error" id={`ap-${key}-error`}>
        {errors[key]}
      </p>
    );

  const field = (key, label, control) => (
    <div className={`field${errors[key] ? " has-error" : ""}`}>
      <label htmlFor={`ap-${key}`}>{label}</label>
      {control}
      {error(key)}
    </div>
  );

  async function submit(e) {
    e.preventDefault();
    const local = {};
    for (const key of REQUIRED) if (!form[key].trim()) local[key] = t("required");
    if (!form.consent) local.consent = t("consentRequired");
    setErrors(local);
    if (Object.keys(local).length) {
      setState("error");
      document.getElementById(`ap-${Object.keys(local)[0]}`)?.focus();
      return;
    }
    setState("sending");
    try {
      await api("/appeals/", { method: "POST", body: { ...form, lang } });
      setForm(EMPTY);
      setState("sent");
    } catch (err) {
      if (err.status === 429) return setState("throttled");
      const server = {};
      for (const key of Object.keys(err.data || {})) server[key] = key === "consent" ? t("consentRequired") : t("required");
      setErrors(server);
      setState("error");
    }
  }

  return (
    <form className="form" onSubmit={submit} noValidate aria-labelledby="appeal-title">
      <h2 id="appeal-title">{t("writeAppeal")}</h2>
      <div aria-live="polite">
        {state === "sent" && <p className="notice notice-ok">{t("appealSent")}</p>}
        {state === "error" && <p className="notice notice-error">{t("appealError")}</p>}
        {state === "throttled" && <p className="notice notice-error">{t("tooMany")}</p>}
      </div>
      {field("full_name", t("fullName"), <input autoComplete="name" required {...bind("full_name")} />)}
      {field("contact", t("contact"), <input autoComplete="tel" required {...bind("contact")} />)}
      {field("subject", t("subject"), <input maxLength={255} required {...bind("subject")} />)}
      {field("message", t("message"), <textarea rows={6} maxLength={5000} required {...bind("message")} />)}
      {/* Поле-ловушка для ботов: скрыто от людей и экранных дикторов */}
      <div className="hp" aria-hidden="true">
        <label htmlFor="ap-website">Website</label>
        <input tabIndex={-1} autoComplete="off" {...bind("website")} />
      </div>
      <div className={`check${errors.consent ? " has-error" : ""}`}>
        <input type="checkbox" {...bind("consent")} />
        <label htmlFor="ap-consent">{t("consent")}</label>
        {error("consent")}
      </div>
      <button type="submit" className="btn btn-primary" disabled={state === "sending"}>
        {state === "sending" ? t("sending") : t("sendAppeal")}
      </button>
    </form>
  );
}

export default function Appeals() {
  const { t, tr } = useLang();
  const site = useSite();
  return (
    <SectionPage slug="appeals" faq="appeals">
      <TextSection id="reception" title={t("receptionSchedule")} html={tr(site, "reception")} />
      <AppealForm />
    </SectionPage>
  );
}
