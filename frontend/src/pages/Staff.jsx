import { useEffect, useRef, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../context.jsx";
import { useTitle } from "../hooks.js";
import { useLang } from "../i18n.jsx";
import { PageHeader } from "../components/ui.jsx";

// после входа можно вернуться только в раздел оплат
function paymentsNext(searchParams) {
  const next = searchParams.get("next");
  return next && /^\/payments(\/|$)/.test(next) ? next : null;
}

export function StaffLogin() {
  const { t, path } = useLang();
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const next = paymentsNext(searchParams);
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const errorRef = useRef(null);
  useTitle(t("staffLogin"));

  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  useEffect(() => {
    if (user && next) window.location.replace(next);
  }, [user, next]);

  if (user) return next ? <p className="muted" role="status">{t("loading")}</p> : <Navigate to={path("staff")} replace />;

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(form.username.trim(), form.password);
      if (!next) navigate(path("staff"), { replace: true });
    } catch (err) {
      setError(err.status === 429 ? t("tooMany") : err.status === 400 ? t("badCredentials") : t("loginFailed"));
      setForm((f) => ({ ...f, password: "" }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="login" aria-labelledby="page-title">
      <PageHeader title={t("staffLogin")} />
      <form className="form login-form" onSubmit={submit}>
        {error && (
          <p className="notice notice-error" role="alert" tabIndex={-1} ref={errorRef}>
            {error}
          </p>
        )}
        <div className="field">
          <label htmlFor="lg-user">{t("username")}</label>
          <input
            id="lg-user"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="lg-pass">{t("password")}</label>
          <input
            id="lg-pass"
            type="password"
            autoComplete="current-password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            required
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? t("signingIn") : t("signIn")}
        </button>
      </form>
    </article>
  );
}

export function RequireStaff({ children }) {
  const { user } = useAuth();
  const { t, path } = useLang();
  if (user === undefined) return <p className="muted" role="status">{t("loading")}</p>;
  if (!user) return <Navigate to={path("staff/login")} replace />;
  return children;
}

function AppealsBox() {
  const { t, fmtDate } = useLang();
  const [list, setList] = useState(null);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);

  useEffect(() => {
    api("/staff/appeals/?status=new,in_progress")
      .then(setList)
      .catch(() => setError("loadError"));
  }, []);

  async function setStatus(id, status) {
    setBusyId(id);
    setError(null);
    try {
      const updated = await api(`/staff/appeals/${id}/`, { method: "PATCH", body: { status } });
      setList((l) => (status === "done" ? l.filter((a) => a.id !== id) : l.map((a) => (a.id === id ? updated : a))));
    } catch {
      setError("saveError");
    } finally {
      setBusyId(null);
    }
  }

  if (!list) return error ? <p className="notice notice-error">{t(error)}</p> : <p className="muted">{t("loading")}</p>;
  if (!list.length) return <p className="muted">{t("noNewAppeals")}</p>;
  return (
    <>
      {error && (
        <p className="notice notice-error" role="alert">
          {t(error)}
        </p>
      )}
      <ul className="appeal-list">
        {list.map((a) => (
          <li key={a.id} className="appeal">
            <div className="appeal-head">
              <h3>{a.subject}</h3>
              <span className={`badge badge-${a.status}`}>{t(`status_${a.status}`)}</span>
            </div>
            <p className="muted small">
              {fmtDate(a.created_at, true)}, {a.full_name}, {a.contact}
            </p>
            <p className="appeal-text">{a.message}</p>
            <div className="appeal-actions">
              {a.status === "new" && (
                <button type="button" className="btn btn-ghost" disabled={busyId === a.id} onClick={() => setStatus(a.id, "in_progress")}>
                  {t("markInProgress")}
                </button>
              )}
              <button type="button" className="btn btn-primary" disabled={busyId === a.id} onClick={() => setStatus(a.id, "done")}>
                {t("markDone")}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}

export function StaffDashboard() {
  const { t, path } = useLang();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  useTitle(t("staffCabinet"));
  const admin = user.admin_url;

  // Ссылки ведут в админку Django: там удобнее загружать файлы и фото
  const links = [
    ["addNews", "content/news/add/"],
    ["uploadDocument", "content/document/add/"],
    ["editPages", "content/page/"],
    ["editPeople", "content/person/"],
    ["editVacancies", "content/vacancy/"],
    ["editSettings", "content/sitesettings/1/change/"],
  ];
  const paymentLinks = [
    ["paymentsTimesheet", "/payments/"],
    ["paymentsDebts", "/payments/debts/"],
    ["paymentsParents", "/payments/parents/"],
    ["paymentsReceipts", `${admin}payments/paymentimport/`],
  ];

  return (
    <article className="staff" aria-labelledby="page-title">
      <PageHeader title={t("staffCabinet")}>
        <div className="staff-user">
          <p>{t("greeting", { name: user.full_name })}</p>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={async () => {
              await logout();
              navigate(path(), { replace: true });
            }}
          >
            {t("signOut")}
          </button>
        </div>
      </PageHeader>

      <div className="staff-grid">
        {user.can_view_appeals && (
          <section aria-labelledby="appeals-title">
            <h2 id="appeals-title">{t("newAppeals")}</h2>
            <AppealsBox />
          </section>
        )}
        <div className="staff-side">
          {(user.can_access_payments || user.can_access_medjournal) && (
            <section aria-labelledby="payments-title">
              <h2 id="payments-title">{t(user.can_access_payments ? "payments" : "medjournal")}</h2>
              <ul className="manage-list">
                {user.can_access_payments &&
                  paymentLinks.map(([key, url]) => (
                    <li key={key}>
                      <a href={url}>{t(key)}</a>
                    </li>
                  ))}
                {user.can_access_medjournal && (
                  <li>
                    <a href="/payments/med/">{t("medjournal")}</a>
                  </li>
                )}
              </ul>
            </section>
          )}
          <section aria-labelledby="manage-title">
            <h2 id="manage-title">{t("manageSite")}</h2>
            <ul className="manage-list">
              {links.map(([key, url]) => (
                <li key={key}>
                  <a href={`${admin}${url}`}>{t(key)}</a>
                </li>
              ))}
              <li>
                <a href={admin}>{t("openAdmin")}</a>
              </li>
            </ul>
          </section>
        </div>
      </div>
    </article>
  );
}
