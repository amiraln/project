import { createElement } from 'react';
import { TEXT } from './ParentsAdaptation.content';
import './ParentsAdaptation.css';

// Иконки 24×24: [тег, атрибуты]. Обводка и толщина задаются в CSS (.pa-icon).
const ICONS = {
  clock: [
    ['circle', { cx: 12, cy: 12, r: 9 }],
    ['path', { d: 'M12 7v5l3 2' }],
  ],
  heart: [
    ['path', { d: 'M19 14c1.5-1.5 3-3.2 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.8 0-3 .5-4.5 2-1.5-1.5-2.7-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4 3 5.5l7 7z' }],
  ],
  repeat: [
    ['path', { d: 'M17 2l4 4-4 4' }],
    ['path', { d: 'M3 11v-1a4 4 0 0 1 4-4h14' }],
    ['path', { d: 'M7 22l-4-4 4-4' }],
    ['path', { d: 'M21 13v1a4 4 0 0 1-4 4H3' }],
  ],
  sparkle: [
    ['path', { d: 'M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z' }],
    ['path', { d: 'M19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z' }],
  ],
  chevron: [['path', { d: 'M6 9l6 6 6-6' }]],
};

function Icon({ name }) {
  return (
    <svg className="pa-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {ICONS[name].map(([tag, attrs], i) => createElement(tag, { key: i, ...attrs }))}
    </svg>
  );
}

// lang: 'ru' | 'kk' — текущий язык сайта.
// headingLevel: уровень заголовка блока (2 — на странице «Родителям», 3 — внутри раздела на главной); у этапов — на один ниже.
// collapsed: этапы свёрнуты (на главной), посетитель раскрывает нужный; на отдельной странице всё раскрыто.
export default function ParentsAdaptation({ lang = 'ru', headingLevel = 2, collapsed = false }) {
  const t = TEXT[lang] ?? TEXT.ru;
  const H = `h${headingLevel}`;
  const StageH = `h${headingLevel + 1}`;

  return (
    <section className="pa" lang={lang === 'kk' ? 'kk' : 'ru'} aria-labelledby="pa-title">
      <header className="pa-hero">
        <H id="pa-title" className="pa-hero__title">{t.title}</H>
        <p className="pa-hero__lead">{t.lead}</p>
      </header>

      <ol className="pa-steps">
        {t.stages.map((stage) => (
          <li className="pa-step" key={stage.n}>
            <span className="pa-step__num" aria-hidden="true">{stage.n}</span>
            <details className="pa-card" open={!collapsed}>
              <summary className="pa-card__head">
                <span className="pa-when">{stage.when}</span>
                <StageH className="pa-card__title">{stage.title}</StageH>
                {stage.stay && (
                  <span className="pa-stay">
                    <Icon name="clock" />
                    {t.stayLabel}: {stage.stay}
                  </span>
                )}
                <span className="pa-card__chevron"><Icon name="chevron" /></span>
              </summary>
              <ul className="pa-tips">
                {stage.tips.map((tip, i) =>
                  typeof tip === 'string' ? (
                    <li key={i}>{tip}</li>
                  ) : (
                    <li key={i}>
                      {tip.text}
                      <blockquote className="pa-quote">«{tip.quote}»</blockquote>
                    </li>
                  ),
                )}
              </ul>
            </details>
          </li>
        ))}
      </ol>

      <div className="pa-notes">
        {t.notes.map((note) => (
          <aside className={`pa-note pa-note--${note.id}`} key={note.id} aria-labelledby={`pa-note-${note.id}`}>
            <span className="pa-note__icon"><Icon name={note.icon} /></span>
            <div>
              <StageH id={`pa-note-${note.id}`} className="pa-note__title">{note.title}</StageH>
              <p className="pa-note__text">{note.text}</p>
            </div>
          </aside>
        ))}
      </div>

      <p className="pa-footer">
        <Icon name="sparkle" />
        {t.footer}
      </p>
      <p className="pa-source">{t.source}</p>
    </section>
  );
}
