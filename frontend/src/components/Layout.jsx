import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useA11y, useAuth, useSite } from "../context.jsx";
import { useSiteName } from "../hooks.js";
import { LANGS, useLang } from "../i18n.jsx";
import A11yPanel from "./A11yPanel.jsx";
import { telHref } from "./ui.jsx";

// «Родителям» и «Обращения» — не в меню, а на главной странице (см. pages/Home.jsx)
const NAV = [
  { key: "home", to: "" },
  { key: "groupKindergarten", items: ["about", "leadership", "teachers", "documents", "finance", "vacancies"] },
  { key: "groupLearning", items: ["education", "nutrition"] },
  { key: "news", to: "news" },
  { key: "contacts", to: "contacts" },
];

function NavGroup({ group, openKey, setOpenKey }) {
  const { t, path } = useLang();
  const { pathname } = useLocation();
  const open = openKey === group.key;
  const listId = `nav-${group.key}`;
  const current = group.items.some((i) => pathname.startsWith(path(i)));
  return (
    <li className="nav-group">
      <button
        type="button"
        className={`nav-link nav-toggle${current ? " is-current" : ""}`}
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpenKey(open ? null : group.key)}
      >
        {t(group.key)}
        <span className="chev" aria-hidden="true" />
      </button>
      <ul id={listId} className="nav-sub" hidden={!open}>
        {group.items.map((item) => (
          <li key={item}>
            <NavLink to={path(item)} className="nav-sublink">
              {t(item)}
            </NavLink>
          </li>
        ))}
      </ul>
    </li>
  );
}

function LangSwitch() {
  const { lang } = useLang();
  const { pathname, search } = useLocation();
  const rest = pathname.replace(/^\/(kk|ru)/, "");
  const names = { kk: "Қазақша", ru: "Русский" };
  return (
    <ul className="lang-switch" aria-label="Тіл / Язык">
      {LANGS.map((l) => (
        <li key={l}>
          <Link to={`/${l}${rest}${search}`} lang={l} hrefLang={l} aria-current={l === lang ? "true" : undefined}>
            {names[l]}
          </Link>
        </li>
      ))}
    </ul>
  );
}

export default function Layout() {
  const { t, tr, path, fmtDate } = useLang();
  const site = useSite();
  const { user } = useAuth();
  const { active: a11yActive } = useA11y();
  const [a11yOpen, setA11yOpen] = useState(a11yActive);
  const [menuOpen, setMenuOpen] = useState(false);
  const [openKey, setOpenKey] = useState(null);
  const { pathname } = useLocation();
  const mainRef = useRef(null);
  const navRef = useRef(null);
  const shownPath = useRef(pathname);

  const closeMenus = () => {
    setMenuOpen(false);
    setOpenKey(null);
  };

  // При переходе на другую страницу: закрыть меню, прокрутить вверх и перенести фокус на содержимое
  // (важно для экранных дикторов). При первой загрузке фокус не трогаем.
  useEffect(() => {
    if (shownPath.current === pathname) return;
    shownPath.current = pathname;
    closeMenus();
    window.scrollTo(0, 0);
    mainRef.current?.focus({ preventScroll: true });
  }, [pathname]);

  // Закрытие подменю по Esc и по клику вне навигации
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && setOpenKey(null);
    const onClick = (e) => navRef.current && !navRef.current.contains(e.target) && setOpenKey(null);
    document.addEventListener("keydown", onKey);
    document.addEventListener("click", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("click", onClick);
    };
  }, []);

  const name = useSiteName();

  return (
    <>
      <a className="skip-link" href="#main">
        {t("skip")}
      </a>

      <div className="topbar">
        <div className="container topbar-inner">
          <LangSwitch />
          <button
            type="button"
            className="topbar-btn"
            aria-expanded={a11yOpen}
            aria-controls="a11y-panel"
            onClick={() => setA11yOpen((v) => !v)}
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20">
              <path
                d="M1.5 12S5.5 5 12 5s10.5 7 10.5 7-4 7-10.5 7S1.5 12 1.5 12Z"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              />
              <circle cx="12" cy="12" r="3.2" fill="currentColor" />
            </svg>
            {t("a11y")}
          </button>
          <Link className="topbar-staff" to={path(user ? "staff" : "staff/login")}>
            {user ? t("staffCabinet") : t("staffLogin")}
          </Link>
        </div>
      </div>
      {a11yOpen && <A11yPanel id="a11y-panel" />}

      <header className="masthead">
        <div className="container masthead-inner">
          <Link to={path()} className="brand">
            {site?.logo && <img src={site.logo} alt="" className="brand-logo" />}
            <span className="brand-name">{name}</span>
          </Link>
          {site?.phone && (
            <a className="masthead-phone" href={telHref(site.phone)}>
              {site.phone}
            </a>
          )}
          <button
            type="button"
            className="menu-btn"
            aria-expanded={menuOpen}
            aria-controls="main-nav"
            onClick={() => setMenuOpen((v) => !v)}
          >
            {menuOpen ? t("close") : t("menu")}
          </button>
        </div>
        <nav
          id="main-nav"
          ref={navRef}
          className={`main-nav${menuOpen ? " is-open" : ""}`}
          aria-label={t("menu")}
          onClick={(e) => e.target.closest("a") && closeMenus()}
        >
          <ul className="container nav-list">
            {NAV.map((item) =>
              item.items ? (
                <NavGroup key={item.key} group={item} openKey={openKey} setOpenKey={setOpenKey} />
              ) : (
                <li key={item.key}>
                  <NavLink to={path(item.to)} end={item.to === ""} className="nav-link">
                    {t(item.key)}
                  </NavLink>
                </li>
              )
            )}
          </ul>
        </nav>
      </header>

      <main id="main" ref={mainRef} tabIndex={-1}>
        <div className="container">
          <Outlet />
        </div>
      </main>

      <footer className="site-footer">
        <div className="container footer-inner">
          <div>
            <p className="footer-name">{name}</p>
            {tr(site, "address") && <p>{tr(site, "address")}</p>}
            {tr(site, "work_hours") && <p>{tr(site, "work_hours")}</p>}
          </div>
          <div>
            {site?.phone && (
              <p>
                <a href={telHref(site.phone)}>{site.phone}</a>
              </p>
            )}
            {site?.email && (
              <p>
                <a href={`mailto:${site.email}`}>{site.email}</a>
              </p>
            )}
          </div>
          <div className="footer-note">
            <p>{t("footerNote")}</p>
            {site?.updated_at && (
              <p>
                {t("lastUpdate")}: {fmtDate(site.updated_at)}
              </p>
            )}
          </div>
        </div>
      </footer>
    </>
  );
}
