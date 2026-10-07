import { Link } from "react-router-dom";
import { useTitle } from "../hooks.js";
import { useLang } from "../i18n.jsx";
import { PageHeader } from "../components/ui.jsx";

export default function NotFound() {
  const { t, path } = useLang();
  useTitle(t("notFound"));
  return (
    <article aria-labelledby="page-title">
      <PageHeader title={t("notFound")} />
      <p>{t("notFoundText")}</p>
      <p>
        <Link className="btn btn-primary" to={path()}>
          {t("toHome")}
        </Link>
      </p>
    </article>
  );
}
