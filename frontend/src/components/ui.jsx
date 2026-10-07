import { useLang } from "../i18n.jsx";

export function Async({ state, children, empty }) {
  const { t } = useLang();
  if (state.loading) return <p className="muted" role="status">{t("loading")}</p>;
  if (state.error) return <p className="notice notice-error" role="alert">{t("loadError")}</p>;
  const data = state.data;
  const isEmpty = data == null || (Array.isArray(data) && data.length === 0);
  if (isEmpty && empty) return <p className="muted">{empty}</p>;
  return children(data);
}

/* HTML уже очищен на сервере (nh3), поэтому его безопасно вставлять */
export function RichText({ html }) {
  if (!html) return null;
  return <div className="prose" dangerouslySetInnerHTML={{ __html: html }} />;
}

/* Раздел страницы с заголовком и текстом из админки; пустой текст — раздел не показываем */
export function TextSection({ id, title, html }) {
  if (!html) return null;
  return (
    <section className="section-block" aria-labelledby={id}>
      <h2 id={id}>{title}</h2>
      <RichText html={html} />
    </section>
  );
}

export function PageHeader({ title, children }) {
  return (
    <header className="page-header">
      <h1 id="page-title">{title}</h1>
      {children}
    </header>
  );
}

export function telHref(phone) {
  return phone ? `tel:${phone.replace(/[^\d+]/g, "")}` : undefined;
}
