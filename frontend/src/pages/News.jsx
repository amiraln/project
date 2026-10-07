import { Link, useParams, useSearchParams } from "react-router-dom";
import { useApi, useTitle } from "../hooks.js";
import { useLang } from "../i18n.jsx";
import { Async, PageHeader, RichText } from "../components/ui.jsx";
import NotFound from "./NotFound.jsx";

const KINDS = ["all", "news", "announcement", "event"];

function NewsMeta({ item }) {
  const { t, fmtDate } = useLang();
  return (
    <p className="news-meta">
      <span className={`kind kind-${item.kind}`}>{t(`kind_${item.kind}`)}</span>{" "}
      <time dateTime={item.published_at}>{fmtDate(item.published_at)}</time>
    </p>
  );
}

function EventDate({ item }) {
  const { t, fmtDate } = useLang();
  if (!item.event_date) return null;
  return (
    <p className="news-event">
      {t("eventDate")}: <time dateTime={item.event_date}>{fmtDate(item.event_date, true)}</time>
    </p>
  );
}

export function NewsItem({ item, headingLevel = 2 }) {
  const { tr, path } = useLang();
  const H = `h${headingLevel}`;
  return (
    <li className="news-item">
      {item.cover && <img src={item.cover} alt={tr(item, "cover_alt")} className="news-cover" loading="lazy" />}
      <div>
        <NewsMeta item={item} />
        <H className="news-title">
          <Link to={path(`news/${item.id}`)}>{tr(item, "title")}</Link>
        </H>
        <EventDate item={item} />
        {tr(item, "summary") && <p>{tr(item, "summary")}</p>}
      </div>
    </li>
  );
}

export function NewsList() {
  const { t } = useLang();
  const [params, setParams] = useSearchParams();
  const kind = KINDS.includes(params.get("kind")) ? params.get("kind") : "all";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const state = useApi(`/news/?page=${page}${kind !== "all" ? `&kind=${kind}` : ""}`);
  useTitle(t("news"));

  const show = (nextKind, nextPage = 1) => {
    setParams({ ...(nextKind !== "all" && { kind: nextKind }), ...(nextPage > 1 && { page: nextPage }) });
    window.scrollTo(0, 0);
  };

  return (
    <article aria-labelledby="page-title">
      <PageHeader title={t("news")} />
      <div className="filter" role="group" aria-label={t("news")}>
        {KINDS.map((k) => (
          <button key={k} type="button" className="filter-btn" aria-pressed={kind === k} onClick={() => show(k)}>
            {t(`kind_${k}`)}
          </button>
        ))}
      </div>
      {state.error?.status === 404 ? (
        <p className="muted">{t("noNews")}</p> // страницы с таким номером нет
      ) : (
        <Async state={state}>
          {(d) =>
            d.results.length ? (
              <>
                <ul className="news-list">
                  {d.results.map((n) => (
                    <NewsItem key={n.id} item={n} />
                  ))}
                </ul>
                {d.pages > 1 && (
                  <nav className="pager" aria-label={t("pageOf", { page, total: d.pages })}>
                    <button type="button" className="btn btn-ghost" disabled={!d.previous} onClick={() => show(kind, page - 1)}>
                      {t("prev")}
                    </button>
                    <span>{t("pageOf", { page, total: d.pages })}</span>
                    <button type="button" className="btn btn-ghost" disabled={!d.next} onClick={() => show(kind, page + 1)}>
                      {t("next")}
                    </button>
                  </nav>
                )}
              </>
            ) : (
              <p className="muted">{t("noNews")}</p>
            )
          }
        </Async>
      )}
    </article>
  );
}

export function NewsDetail() {
  const { id } = useParams();
  const { t, tr, path } = useLang();
  const state = useApi(`/news/${Number(id) || 0}/`);
  useTitle(state.data ? tr(state.data, "title") : t("news"));
  if (state.error?.status === 404) return <NotFound />;
  return (
    <Async state={state}>
      {(n) => (
        <article className="news-detail" aria-labelledby="page-title">
          <p>
            <Link to={path("news")}>← {t("backToNews")}</Link>
          </p>
          <PageHeader title={tr(n, "title")}>
            <NewsMeta item={n} />
            <EventDate item={n} />
          </PageHeader>
          {n.cover && <img src={n.cover} alt={tr(n, "cover_alt")} className="detail-cover" />}
          <RichText html={tr(n, "body")} />
          {n.photos.length > 0 && (
            <section aria-labelledby="gallery-title">
              <h2 id="gallery-title">{t("photos")}</h2>
              <ul className="gallery">
                {n.photos.map((p) => (
                  <li key={p.id}>
                    <a href={p.image} target="_blank" rel="noopener">
                      <img src={p.image} alt={tr(p, "alt")} loading="lazy" />
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </article>
      )}
    </Async>
  );
}
