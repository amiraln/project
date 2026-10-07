import { useSite } from "../context.jsx";
import { useTitle } from "../hooks.js";
import { useLang } from "../i18n.jsx";
import { PageHeader, TextSection, telHref } from "../components/ui.jsx";

export default function Contacts() {
  const { t, tr } = useLang();
  const site = useSite();
  useTitle(t("contacts"));
  if (!site) return <p className="muted" role="status">{t("loading")}</p>;

  const facts = [
    ["address", tr(site, "address")],
    ["phone", site.phone && <a href={telHref(site.phone)}>{site.phone}</a>],
    ["email", site.email && <a href={`mailto:${site.email}`}>{site.email}</a>],
    ["workHours", tr(site, "work_hours")],
  ].filter(([, value]) => value);

  return (
    <article aria-labelledby="page-title">
      <PageHeader title={t("contacts")} />
      <dl className="contact-facts">
        {facts.map(([key, value]) => (
          <div key={key}>
            <dt>{t(key)}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <TextSection id="reception" title={t("receptionSchedule")} html={tr(site, "reception")} />
      {site.map_embed_url && (
        <section className="section-block" aria-labelledby="map">
          <h2 id="map">{t("map")}</h2>
          <iframe
            className="map"
            src={site.map_embed_url}
            title={`${t("map")}: ${tr(site, "address")}`}
            loading="lazy"
            referrerPolicy="no-referrer-when-downgrade"
          />
        </section>
      )}
    </article>
  );
}
