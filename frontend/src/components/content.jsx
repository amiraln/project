import { useApi, useTitle } from "../hooks.js";
import { useLang } from "../i18n.jsx";
import { Async, PageHeader, RichText, telHref } from "./ui.jsx";

function fmtSize(bytes) {
  if (!bytes) return "";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} КБ`;
  return `${(bytes / 1024 / 1024).toFixed(1).replace(".", ",")} МБ`;
}

function initials(fullName) {
  return fullName
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0])
    .join("");
}

export function DocumentList({ categories }) {
  const { t, tr, fmtDate } = useLang();
  const state = useApi(`/documents/?category=${categories.join(",")}`);
  return (
    <Async state={state}>
      {(docs) => {
        const byCat = categories.map((c) => [c, docs.filter((d) => d.category === c)]).filter(([, list]) => list.length);
        if (!byCat.length) return <p className="muted">{t("noDocuments")}</p>;
        return byCat.map(([cat, list]) => (
          <section key={cat} className="doc-section" aria-labelledby={`doc-${cat}`}>
            <h2 id={`doc-${cat}`}>{t(`cat_${cat}`)}</h2>
            <ul className="doc-list">
              {list.map((d) => {
                const type = d.extension?.toUpperCase();
                return (
                  <li key={d.id} className="doc-item">
                    <span className="doc-ext" aria-hidden="true">
                      {d.extension}
                    </span>
                    <div>
                      <a href={d.file} className="doc-title" target="_blank" rel="noopener">
                        {tr(d, "title")}
                        <span className="visually-hidden">
                          {" "}
                          ({type}, {fmtSize(d.size)})
                        </span>
                      </a>
                      <p className="doc-meta">
                        {t("published")} {fmtDate(d.published_at)}
                        {d.size ? `, ${type} ${fmtSize(d.size)}` : ""}
                        {d.language !== "both" ? `, ${t(`lang_${d.language}`).toLowerCase()}` : ""}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        ));
      }}
    </Async>
  );
}

export function FAQList({ section }) {
  const { t, tr } = useLang();
  const { data } = useApi(`/faq/?section=${section}`);
  if (!data?.length) return null;
  return (
    <section className="faq" aria-labelledby={`faq-${section}`}>
      <h2 id={`faq-${section}`}>{t("faq")}</h2>
      {data.map((q) => (
        <details key={q.id} className="faq-item">
          <summary>{tr(q, "question")}</summary>
          <RichText html={tr(q, "answer")} />
        </details>
      ))}
    </section>
  );
}

function Fact({ label, children }) {
  if (!children) return null;
  return (
    <>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </>
  );
}

export function PeopleList({ kind }) {
  const { t, tr, years } = useLang();
  const state = useApi(`/people/?kind=${kind}`);
  return (
    <Async state={state} empty={t("notFilled")}>
      {(people) => (
        <ul className={`people people-${kind}`}>
          {people.map((p) => (
            <li key={p.id} className="person">
              {p.photo ? (
                <img src={p.photo} alt={p.full_name} className="person-photo" loading="lazy" />
              ) : (
                <div className="person-photo person-photo-empty" aria-hidden="true">
                  {initials(p.full_name)}
                </div>
              )}
              <div>
                <h2 className="person-name">{p.full_name}</h2>
                <p className="person-position">{tr(p, "position")}</p>
                <dl className="facts">
                  <Fact label={t("educationLabel")}>{tr(p, "education")}</Fact>
                  <Fact label={t("qualification")}>{tr(p, "qualification")}</Fact>
                  <Fact label={t("experience")}>{p.experience_years != null && years(p.experience_years)}</Fact>
                  <Fact label={t("reception")}>{tr(p, "reception")}</Fact>
                  <Fact label={t("phone")}>{p.phone && <a href={telHref(p.phone)}>{p.phone}</a>}</Fact>
                  <Fact label={t("email")}>{p.email && <a href={`mailto:${p.email}`}>{p.email}</a>}</Fact>
                </dl>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Async>
  );
}

/* Общий шаблон раздела: заголовок + текст из админки + документы + вопросы + доп. содержимое */
export function SectionPage({ slug, docs, faq, children }) {
  const { t, tr, fmtDate } = useLang();
  const { data: page } = useApi(`/pages/${slug}/`); // раздел ещё не заполнен — просто нет текста
  const body = tr(page, "body");
  useTitle(t(slug));
  return (
    <article aria-labelledby="page-title">
      <PageHeader title={t(slug)}>
        {body && (
          <p className="muted small">
            {t("updated")}: {fmtDate(page.updated_at)}
          </p>
        )}
      </PageHeader>
      <RichText html={body} />
      {children}
      {docs && (
        <section className="section-block" aria-label={t("documents")}>
          <DocumentList categories={docs} />
        </section>
      )}
      {faq && <FAQList section={faq} />}
    </article>
  );
}
