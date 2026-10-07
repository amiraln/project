import { Link } from "react-router-dom";
import { useSite } from "../context.jsx";
import { useApi, useSiteName, useTitle } from "../hooks.js";
import { useLang } from "../i18n.jsx";
import SeasonScene from "../components/SeasonScene.jsx";
import { Async, telHref } from "../components/ui.jsx";
import Appeals from "./Appeals.jsx";
import { NewsItem } from "./News.jsx";
import { Parents } from "./Sections.jsx";

const QUICK_LINKS = [
  ["nutrition", "quickMenu"],
  ["education", "quickSchedule"],
];

/* Открыт ли детский сад сейчас — по времени Алматы, а не по часовому поясу посетителя */
function openStatus(s) {
  if (!s?.open_time || !s?.close_time) return null;
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", { timeZone: "Asia/Almaty", weekday: "short", hour: "numeric", minute: "numeric", hourCycle: "h23" })
      .formatToParts(new Date())
      .map((p) => [p.type, p.value])
  );
  const day = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].indexOf(parts.weekday) + 1;
  const minutes = (hhmm) => {
    const [h, m] = hhmm.split(":").map(Number);
    return h * 60 + m;
  };
  const now = Number(parts.hour) * 60 + Number(parts.minute);
  const open = s.open_weekdays.includes(String(day)) && now >= minutes(s.open_time) && now < minutes(s.close_time);
  return { open, until: s.close_time.slice(0, 5) };
}

function Today() {
  const { t, tr } = useLang();
  const site = useSite();
  const status = openStatus(site);
  const facts = [
    ["workHours", tr(site, "work_hours")],
    ["address", tr(site, "address")],
  ].filter(([, value]) => value);
  if (!status && !facts.length && !site?.phone) return null;
  return (
    <div className={`today${status?.open ? " is-open" : ""}`}>
      {status && (
        <p className="today-status">
          <span className="dot" aria-hidden="true" />
          {status.open ? t("openNow", { time: status.until }) : t("closedNow")}
        </p>
      )}
      <dl className="today-facts">
        {facts.map(([key, value]) => (
          <div key={key}>
            <dt>{t(key)}</dt>
            <dd>{value}</dd>
          </div>
        ))}
        {site.phone && (
          <div className="today-call">
            <dt>{t("phone")}</dt>
            <dd>
              <a className="today-phone" href={telHref(site.phone)}>
                {site.phone}
              </a>
            </dd>
          </div>
        )}
      </dl>
    </div>
  );
}

export default function Home() {
  const { t, tr, path } = useLang();
  const site = useSite();
  const name = useSiteName();
  const news = useApi("/news/?page_size=3");
  useTitle(null);

  return (
    <>
      <section className="hero" aria-labelledby="page-title">
        <div className="hero-text">
          <h1 id="page-title" className="hero-name">
            {name}
          </h1>
          {tr(site, "tagline") && <p className="hero-tagline">{tr(site, "tagline")}</p>}
          <Today />
        </div>
        {/* Картинка и анимация меняются по текущему времени года */}
        <SeasonScene className="hero-art" />
      </section>

      {/* «Родителям» и «Обращения» — не в меню, а здесь, целыми разделами (те же, что на /parents и /appeals) */}
      <Parents embedded>
        <ul className="quick-list" aria-label={t("forParentsQuick")}>
          {QUICK_LINKS.map(([to, key]) => (
            <li key={key}>
              <Link to={path(to)}>{t(key)}</Link>
            </li>
          ))}
        </ul>
      </Parents>
      <Appeals embedded />

      <section className="home-news" aria-labelledby="news-title">
        <div className="section-head">
          <h2 id="news-title">{t("latestNews")}</h2>
          <Link to={path("news")}>{t("allNews")}</Link>
        </div>
        <Async state={news}>
          {(d) =>
            d.results.length ? (
              <ul className="news-list">
                {d.results.map((n) => (
                  <NewsItem key={n.id} item={n} headingLevel={3} />
                ))}
              </ul>
            ) : (
              <p className="muted">{t("noNews")}</p>
            )
          }
        </Async>
      </section>
    </>
  );
}
