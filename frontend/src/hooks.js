import { useEffect, useState } from "react";
import { api } from "./api.js";
import { useSite } from "./context.jsx";
import { useLang } from "./i18n.jsx";

/* GET-запрос к API: { data, loading, error }; при смене path загружается заново */
export function useApi(path) {
  const [state, setState] = useState({ data: null, loading: true, error: null });
  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    api(path)
      .then((data) => alive && setState({ data, loading: false, error: null }))
      .catch((error) => alive && setState({ data: null, loading: false, error }));
    return () => {
      alive = false;
    };
  }, [path]);
  return state;
}

export function useSiteName() {
  const { tr } = useLang();
  return tr(useSite(), "name") || "Ботақаным";
}

export function useTitle(title) {
  const siteName = useSiteName();
  useEffect(() => {
    document.title = title ? `${title} | ${siteName}` : siteName;
  }, [title, siteName]);
}
