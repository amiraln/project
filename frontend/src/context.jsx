import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api.js";

/* ---------- Настройки сайта (название, контакты) ---------- */
const SiteContext = createContext(null);

export function SiteProvider({ children }) {
  const [settings, setSettings] = useState(null);
  useEffect(() => {
    api("/settings/").then(setSettings).catch(() => setSettings({}));
  }, []);
  return <SiteContext.Provider value={settings}>{children}</SiteContext.Provider>;
}
export const useSite = () => useContext(SiteContext);

/* ---------- Вход сотрудников ---------- */
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(undefined); // undefined = ещё проверяем
  useEffect(() => {
    api("/auth/me/")
      .then((d) => setUser(d.authenticated ? d : null))
      .catch(() => setUser(null));
  }, []);
  const login = useCallback(async (username, password) => {
    const d = await api("/auth/login/", { method: "POST", body: { username, password } });
    setUser(d);
    return d;
  }, []);
  const logout = useCallback(async () => {
    await api("/auth/logout/", { method: "POST" }).catch(() => {});
    setUser(null);
  }, []);
  return <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>;
}
export const useAuth = () => useContext(AuthContext);

/* ---------- Версия для слабовидящих ---------- */
const A11Y_DEFAULTS = { font: "1", scheme: "default", images: "on", spacing: "normal" };
const A11Y_KEY = "a11y-prefs";
const A11yContext = createContext(null);

function loadPrefs() {
  try {
    return { ...A11Y_DEFAULTS, ...JSON.parse(localStorage.getItem(A11Y_KEY) || "{}") };
  } catch {
    return A11Y_DEFAULTS;
  }
}

export function A11yProvider({ children }) {
  const [prefs, setPrefs] = useState(loadPrefs);
  useEffect(() => {
    const el = document.documentElement;
    for (const [k, v] of Object.entries(prefs)) {
      if (v === A11Y_DEFAULTS[k]) el.removeAttribute(`data-${k}`);
      else el.setAttribute(`data-${k}`, v);
    }
    try {
      localStorage.setItem(A11Y_KEY, JSON.stringify(prefs));
    } catch {
      /* приватный режим — просто не запоминаем */
    }
  }, [prefs]);
  const set = (key, value) => setPrefs((p) => ({ ...p, [key]: value }));
  const reset = () => setPrefs(A11Y_DEFAULTS);
  const active = Object.keys(A11Y_DEFAULTS).some((k) => prefs[k] !== A11Y_DEFAULTS[k]);
  return <A11yContext.Provider value={{ prefs, set, reset, active }}>{children}</A11yContext.Provider>;
}
export const useA11y = () => useContext(A11yContext);
