import winterBack from "../assets/seasons/winter-back.webp";
import winterMom from "../assets/seasons/winter-mom.webp";
import winterMid from "../assets/seasons/winter-mid.webp";
import winterCalf from "../assets/seasons/winter-calf.webp";
import winterFront from "../assets/seasons/winter-front.webp";
import springBack from "../assets/seasons/spring-back.webp";
import springMom from "../assets/seasons/spring-mom.webp";
import springCalf from "../assets/seasons/spring-calf.webp";
import springFront from "../assets/seasons/spring-front.webp";
import summerBack from "../assets/seasons/summer-back.webp";
import summerMom from "../assets/seasons/summer-mom.webp";
import summerCalf from "../assets/seasons/summer-calf.webp";
import autumnBack from "../assets/seasons/autumn-back.webp";
import autumnMom from "../assets/seasons/autumn-mom.webp";
import autumnMid from "../assets/seasons/autumn-mid.webp";
import autumnCalf from "../assets/seasons/autumn-calf.webp";
import autumnFront from "../assets/seasons/autumn-front.webp";
import snowUrl from "../assets/seasons/overlay-winter.svg";
import snowStillUrl from "../assets/seasons/overlay-winter-still.svg";
import petalsUrl from "../assets/seasons/overlay-spring.svg";
import petalsStillUrl from "../assets/seasons/overlay-spring-still.svg";
import butterfliesUrl from "../assets/seasons/overlay-summer.svg";
import butterfliesStillUrl from "../assets/seasons/overlay-summer-still.svg";
import rainUrl from "../assets/seasons/overlay-autumn.svg";
import rainStillUrl from "../assets/seasons/overlay-autumn-still.svg";
import { useLang } from "../i18n.jsx";
import "./SeasonScene.css";

// Картинка собрана из слоёв: фон с туловищами, голова мамы, шарф или листья на шее,
// голова малыша, то, что лежит впереди. Головы двигаются (см. SeasonScene.css).
// Сверху летят снег, лепестки, бабочки или дождь с листьями.
const SEASONS = {
  winter: { back: winterBack, mom: winterMom, mid: winterMid, calf: winterCalf, front: winterFront,
            overlay: snowUrl, overlayStill: snowStillUrl },
  spring: { back: springBack, mom: springMom, calf: springCalf, front: springFront,
            overlay: petalsUrl, overlayStill: petalsStillUrl },
  summer: { back: summerBack, mom: summerMom, calf: summerCalf,
            overlay: butterfliesUrl, overlayStill: butterfliesStillUrl },
  autumn: { back: autumnBack, mom: autumnMom, mid: autumnMid, calf: autumnCalf, front: autumnFront,
            overlay: rainUrl, overlayStill: rainStillUrl },
};

// Декабрь–февраль зима, март–май весна, июнь–август лето, сентябрь–ноябрь осень.
export function currentSeason(date = new Date()) {
  const m = date.getMonth();
  if (m === 11 || m <= 1) return "winter";
  if (m <= 4) return "spring";
  if (m <= 7) return "summer";
  return "autumn";
}

// season: 'winter' | 'spring' | 'summer' | 'autumn' — необязательно; по умолчанию берётся текущее время года.
export default function SeasonScene({ className = "", season }) {
  const { t } = useLang();
  const key = SEASONS[season] ? season : currentSeason();
  const art = SEASONS[key];

  return (
    <div className={`season ${className}`}>
      <div className="season-scene" role="img" aria-label={t(`season_${key}`)}>
        <img className="season-layer" src={art.back} alt="" fetchpriority="high" />
        <img className="season-layer season-mom" src={art.mom} alt="" />
        {art.mid && <img className="season-layer" src={art.mid} alt="" />}
        <img className="season-layer season-calf" src={art.calf} alt="" />
        {art.front && <img className="season-layer" src={art.front} alt="" />}
      </div>
      {/* Если в системе включено «уменьшить движение» — снежинки, дождь и бабочки не двигаются */}
      <picture className="season-overlay" aria-hidden="true">
        <source srcSet={art.overlayStill} media="(prefers-reduced-motion: reduce)" />
        <img src={art.overlay} alt="" />
      </picture>
    </div>
  );
}
