import { useState } from 'react';
import { Check, X } from 'lucide-react';
import type { Task } from '../types';
import { calculateTaskScore } from '../lib/rating';
import { RatingBreakdown } from './RatingBreakdown';

const fields = [
  ['title', 'Название задачи'],
  ['context', 'Контекст'],
  ['need', 'Потребность'],
  ['users', 'Пользователи'],
  ['data', 'Данные и материалы'],
  ['constraints', 'Ограничения'],
  ['expectedResult', 'Ожидаемый результат'],
  ['successCriteria', 'Критерии успеха'],
  ['contact', 'Контакт'],
  ['collaboration', 'Формат взаимодействия'],
] as const;
export function TaskEditor({
  task,
  onClose,
  onSave,
}: {
  task: Task;
  onClose: () => void;
  onSave: (task: Task) => void;
}) {
  const [draft, setDraft] = useState(task);
  const score = calculateTaskScore(draft);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="response-form-modal editor-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Редактировать задачу"
        onClick={(event) => event.stopPropagation()}
      >
        <button className="close-button" onClick={onClose} aria-label="Закрыть">
          <X size={21} />
        </button>
        <span className="section-kicker">РЕДАКТИРОВАНИЕ КАРТОЧКИ</span>
        <h2>Уточните задачу</h2>
        <p className="muted-copy">
          Оценка пересчитывается сразу. После сохранения обновлённая карточка останется в общем
          каталоге.
        </p>
        <div className="review-grid">
          {fields.map(([key, label]) => (
            <label key={key}>
              {label}
              {key === 'title' ? (
                <input
                  value={draft[key]}
                  onChange={(event) => setDraft({ ...draft, [key]: event.target.value })}
                />
              ) : (
                <textarea
                  rows={2}
                  value={draft[key]}
                  onChange={(event) => setDraft({ ...draft, [key]: event.target.value })}
                  placeholder="Добавьте информацию"
                />
              )}
            </label>
          ))}
        </div>
        <RatingBreakdown fields={draft} />
        <div className="form-footer">
          <button className="back-button" onClick={onClose}>
            Отмена
          </button>
          <button
            className="primary-button"
            onClick={() => onSave({ ...draft, rating: score.score })}
          >
            Сохранить изменения <Check size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
