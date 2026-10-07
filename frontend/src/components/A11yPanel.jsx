import { useA11y } from "../context.jsx";
import { useLang } from "../i18n.jsx";

function Choice({ label, name, options }) {
  const { prefs, set } = useA11y();
  return (
    <fieldset className="a11y-group">
      <legend>{label}</legend>
      <div className="a11y-options">
        {options.map(([value, text, extra, ariaLabel]) => (
          <button
            key={value}
            type="button"
            className={`a11y-option ${extra || ""}`}
            aria-pressed={prefs[name] === value}
            aria-label={ariaLabel}
            onClick={() => set(name, value)}
          >
            {text}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

export default function A11yPanel({ id }) {
  const { t } = useLang();
  const { reset } = useA11y();
  return (
    <section id={id} className="a11y-panel" aria-label={t("a11y")}>
      <div className="container a11y-inner">
        <Choice
          label={t("fontSize")}
          name="font"
          options={[
            ["1", "A", "sz1", "100%"],
            ["2", "A", "sz2", "125%"],
            ["3", "A", "sz3", "150%"],
          ]}
        />
        <Choice
          label={t("colors")}
          name="scheme"
          options={[
            ["default", t("scheme_default")],
            ["bw", t("scheme_bw"), "sw-bw"],
            ["wb", t("scheme_wb"), "sw-wb"],
            ["blue", t("scheme_blue"), "sw-blue"],
          ]}
        />
        <Choice label={t("images")} name="images" options={[["on", t("show")], ["off", t("hide")]]} />
        <Choice label={t("spacing")} name="spacing" options={[["normal", t("normal")], ["wide", t("wide")]]} />
        <button type="button" className="btn btn-ghost" onClick={reset}>
          {t("resetA11y")}
        </button>
      </div>
    </section>
  );
}
