import { createElement } from 'react';
import { ICONS, TEXT } from './ParentsDocuments.content';
import './ParentsDocuments.css';

function Icon({ name }) {
  return (
    <svg className="pd-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {ICONS[name].map(([tag, attrs], i) => createElement(tag, { key: i, ...attrs }))}
    </svg>
  );
}

// lang: 'ru' | 'kk' — передавайте текущий язык сайта.
// headingLevel: уровень заголовка раздела (2 — на отдельной странице, 3 — внутри раздела главной); у групп — на один ниже.
// Картинка по времени года — отдельно, в SeasonScene.jsx (на главной она рядом с режимом работы).
export default function ParentsDocuments({ lang = 'ru', headingLevel = 2 }) {
  const t = TEXT[lang] ?? TEXT.ru;
  const H = `h${headingLevel}`;
  const GroupH = `h${headingLevel + 1}`;

  return (
    <section className="pd" lang={lang === 'kk' ? 'kk' : 'ru'} aria-labelledby="pd-title">
      <header className="pd-hero">
        <H id="pd-title" className="pd-hero__title">{t.title}</H>
        <p className="pd-hero__lead">{t.lead}</p>
      </header>

      {t.groups.map((group) => (
        <section className="pd-group" key={group.id} aria-labelledby={`pd-group-${group.id}`}>
          <div className="pd-group__head">
            <GroupH id={`pd-group-${group.id}`} className="pd-group__title">{group.title}</GroupH>
            {group.note && <p className="pd-group__note">{group.note}</p>}
          </div>

          <ol className="pd-list" start={group.items[0].n}>
            {group.items.map((item) => (
              <li className={item.badge ? 'pd-item pd-item--key' : 'pd-item'} key={item.n}>
                <span className="pd-item__tile">
                  <Icon name={item.icon} />
                  <span className="pd-item__num" aria-hidden="true">{item.n}</span>
                </span>
                <div className="pd-item__body">
                  <p className="pd-item__title">
                    {item.title}
                    {item.tag && <span className="pd-tag">{item.tag}</span>}
                  </p>
                  {item.badge && (
                    <p className="pd-badge">
                      <Icon name="clock" />
                      {item.badge}
                    </p>
                  )}
                  {item.sub && <p className="pd-item__sub">{item.sub}</p>}
                </div>
              </li>
            ))}
          </ol>
        </section>
      ))}

      <p className="pd-footer">
        <Icon name="calendar" />
        {t.footer}
      </p>
    </section>
  );
}
