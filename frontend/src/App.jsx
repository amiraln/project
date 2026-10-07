import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import { A11yProvider, AuthProvider, SiteProvider } from "./context.jsx";
import { LANGS, LangProvider } from "./i18n.jsx";
import Appeals from "./pages/Appeals.jsx";
import Contacts from "./pages/Contacts.jsx";
import Home from "./pages/Home.jsx";
import { NewsDetail, NewsList } from "./pages/News.jsx";
import NotFound from "./pages/NotFound.jsx";
import { About, Documents, Education, Finance, Leadership, Nutrition, Parents, Teachers, Vacancies } from "./pages/Sections.jsx";
import { RequireStaff, StaffDashboard, StaffLogin } from "./pages/Staff.jsx";

const LANG_KEY = "site-lang";

function preferredLang() {
  try {
    const saved = localStorage.getItem(LANG_KEY);
    if (LANGS.includes(saved)) return saved;
  } catch {
    /* ignore */
  }
  return "kk"; // государственный язык — по умолчанию
}

function LangRoot() {
  const { lang } = useParams();
  const { pathname, search } = useLocation();
  const valid = LANGS.includes(lang);

  useEffect(() => {
    if (!valid) return;
    document.documentElement.lang = lang;
    try {
      localStorage.setItem(LANG_KEY, lang);
    } catch {
      /* ignore */
    }
  }, [lang, valid]);

  if (!valid) return <Navigate to={`/${preferredLang()}${pathname}${search}`} replace />;
  return (
    <LangProvider lang={lang}>
      <Layout />
    </LangProvider>
  );
}

export default function App() {
  return (
    <A11yProvider>
      <SiteProvider>
        <AuthProvider>
          <Routes>
            <Route path="/" element={<Navigate to={`/${preferredLang()}`} replace />} />
            <Route path="/:lang" element={<LangRoot />}>
              <Route index element={<Home />} />
              <Route path="about" element={<About />} />
              <Route path="leadership" element={<Leadership />} />
              <Route path="teachers" element={<Teachers />} />
              <Route path="documents" element={<Documents />} />
              <Route path="education" element={<Education />} />
              <Route path="parents" element={<Parents />} />
              <Route path="nutrition" element={<Nutrition />} />
              <Route path="finance" element={<Finance />} />
              <Route path="vacancies" element={<Vacancies />} />
              <Route path="news" element={<NewsList />} />
              <Route path="news/:id" element={<NewsDetail />} />
              <Route path="appeals" element={<Appeals />} />
              <Route path="contacts" element={<Contacts />} />
              <Route path="staff/login" element={<StaffLogin />} />
              <Route
                path="staff"
                element={
                  <RequireStaff>
                    <StaffDashboard />
                  </RequireStaff>
                }
              />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </AuthProvider>
      </SiteProvider>
    </A11yProvider>
  );
}
