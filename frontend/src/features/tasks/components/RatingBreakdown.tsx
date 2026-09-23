import { calculateTaskScore } from '../lib/rating';
import type { TaskFields } from '../types';

export function RatingBreakdown({
  fields,
  compact = false,
  scoreOverride,
}: {
  fields: TaskFields;
  compact?: boolean;
  scoreOverride?: number;
}) {
  const { score: calculatedScore, breakdown, missing } = calculateTaskScore(fields);
  const score = scoreOverride ?? calculatedScore;
  return (
    <section className="rating-panel" aria-live="polite">
      <div className="rating-total">
        <span>Готовность задачи</span>
        <strong>
          {score}
          <small>/100</small>
        </strong>
        <div className="rating-track">
          <i style={{ width: `${score}%` }} />
        </div>
      </div>
      {!compact && (
        <>
          <h4>Расшифровка баллов</h4>
          <ul className="score-list">
            {breakdown.map((item) => (
              <li key={item.key}>
                <span>{item.label}</span>
                <b>
                  {item.earned}/{item.points}
                </b>
              </li>
            ))}
          </ul>
          <h4>Что ещё добавить</h4>
          {missing.length ? (
            <ul className="missing-list">
              {missing.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <p className="all-complete">Все сведения заполнены — задача готова к публикации.</p>
          )}
        </>
      )}
      {compact && (
        <p className="rating-hint">Рейтинг пересчитывается при каждом изменении карточки.</p>
      )}
    </section>
  );
}
