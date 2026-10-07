import { useSite } from "../context.jsx";
import { useApi } from "../hooks.js";
import { useLang } from "../i18n.jsx";
import { Async, RichText, TextSection } from "../components/ui.jsx";
import { PeopleList, SectionPage } from "../components/content.jsx";

export function About() {
  const { t, tr } = useLang();
  const site = useSite();
  const groups = useApi("/groups/");
  return (
    <SectionPage slug="about">
      <TextSection id="history" title={t("history")} html={tr(site, "history")} />
      <TextSection id="founder" title={t("founder")} html={tr(site, "founder")} />
      <section className="section-block" aria-labelledby="groups">
        <h2 id="groups">{t("groups")}</h2>
        <Async state={groups} empty={t("notFilled")}>
          {(list) => (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">{t("groupName")}</th>
                    <th scope="col">{t("age")}</th>
                    <th scope="col">{t("instructionLang")}</th>
                  </tr>
                </thead>
                <tbody>
                  {list.map((g) => (
                    <tr key={g.id}>
                      <th scope="row">{tr(g, "name")}</th>
                      <td>{tr(g, "age")}</td>
                      <td>{t(`lang_${g.language}`)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Async>
      </section>
    </SectionPage>
  );
}

export const Leadership = () => (
  <SectionPage slug="leadership">
    <PeopleList kind="leader" />
  </SectionPage>
);

export const Teachers = () => (
  <SectionPage slug="teachers">
    <PeopleList kind="teacher" />
  </SectionPage>
);

export const Documents = () => <SectionPage slug="documents" docs={["charter", "gos", "rules", "program", "other"]} />;
export const Education = () => <SectionPage slug="education" docs={["program", "schedule"]} />;
export const Parents = () => <SectionPage slug="parents" docs={["admission", "contract", "payment"]} faq="parents" />;
export const Nutrition = () => <SectionPage slug="nutrition" docs={["menu", "nutrition"]} />;
export const Finance = () => <SectionPage slug="finance" docs={["report", "budget", "procurement"]} />;

export function Vacancies() {
  const { t, tr, fmtDate } = useLang();
  const state = useApi("/vacancies/");
  return (
    <SectionPage slug="vacancies">
      <Async state={state} empty={t("noVacancies")}>
        {(list) => (
          <ul className="vacancy-list">
            {list.map((v) => (
              <li key={v.id} className="vacancy">
                <h2>{tr(v, "title")}</h2>
                <p className="muted small">
                  {t("published")} {fmtDate(v.published_at)}
                </p>
                <h3>{t("requirements")}</h3>
                <RichText html={tr(v, "requirements")} />
                {tr(v, "conditions") && (
                  <>
                    <h3>{t("conditions")}</h3>
                    <RichText html={tr(v, "conditions")} />
                  </>
                )}
                <p>
                  <strong>{t("contactPerson")}:</strong> {v.contact}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Async>
    </SectionPage>
  );
}
