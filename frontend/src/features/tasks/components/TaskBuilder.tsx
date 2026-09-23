import { useState } from 'react';
import { ArrowLeft, ArrowRight, Check, CircleHelp, LoaderCircle, X } from 'lucide-react';
import { taskCategories } from '../data';
import { emptyTaskFields, type Task, type TaskFields } from '../types';
import { calculateTaskScore } from '../lib/rating';
import {
  answerClarificationRound,
  createTaskDraft,
  publishTaskDraft,
  type ClarificationQuestion,
  type ClarificationResponse,
} from '../lib/api';
import { RatingBreakdown } from './RatingBreakdown';

const fieldLabels: Record<keyof TaskFields, string> = {
  title: 'Название задачи',
  context: 'Контекст',
  need: 'Потребность',
  users: 'Пользователи',
  data: 'Данные и материалы',
  constraints: 'Ограничения',
  expectedResult: 'Ожидаемый результат',
  successCriteria: 'Критерии успеха',
  contact: 'Контакт',
  collaboration: 'Формат взаимодействия',
};
type Stage = 'intro' | 'questions' | 'review';

export function TaskBuilder({
  onClose,
  onPublish,
}: {
  onClose: () => void;
  onPublish: (task: Task) => void;
}) {
  const [fields, setFields] = useState<TaskFields>(emptyTaskFields);
  const [category, setCategory] = useState(taskCategories[0]);
  const [stage, setStage] = useState<Stage>('intro');
  const [draftId, setDraftId] = useState('');
  const [originalText, setOriginalText] = useState('');
  const [round, setRound] = useState(1);
  const [questions, setQuestions] = useState<ClarificationQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [backendResult, setBackendResult] = useState<ClarificationResponse | null>(null);
  const [useGeneratedText, setUseGeneratedText] = useState(true);
  const [finalText, setFinalText] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const score = calculateTaskScore(fields);
  const updateField = (key: keyof TaskFields, value: string) =>
    setFields((current) => ({ ...current, [key]: value }));

  const begin = async () => {
    if (fields.title.trim().length < 3 || fields.context.trim().length < 10) {
      setError('Укажите название и кратко опишите исходную задачу.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const result = await createTaskDraft({
        title: fields.title.trim(),
        description: fields.context.trim(),
        category,
      });
      if (result.questions.length === 0)
        throw new Error('Backend вернул пустой список вопросов для первого блока.');
      setDraftId(result.draftId);
      setOriginalText(fields.context.trim());
      setQuestions(result.questions);
      setAnswers({});
      setRound(1);
      setStage('questions');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Не удалось создать черновик.');
    } finally {
      setLoading(false);
    }
  };

  const submitAnswers = async () => {
    if (!questions.length || questions.some((question) => !answers[question.id]?.trim())) {
      setError('Ответьте на все вопросы этого блока.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const result = await answerClarificationRound(
        draftId,
        round,
        questions.map((question) => ({
          questionId: question.id,
          answer: answers[question.id].trim(),
        })),
      );
      setBackendResult(result);
      if (result.ready) {
        const merged = { ...fields, ...result.taskFields };
        setFields(merged);
        const generatedText = result.finalText || result.taskFields?.context || '';
        setFinalText(generatedText || originalText);
        setUseGeneratedText(Boolean(generatedText));
        setStage('review');
        return;
      }
      if (!result.questions?.length)
        throw new Error(
          result.message || 'Задача пока не готова. Backend должен вернуть уточняющие вопросы.',
        );
      setQuestions(result.questions);
      setAnswers({});
      if (round < 3) setRound((current) => current + 1);
      else
        setError(
          result.message ||
            'Нужны дополнительные уточнения. Ответьте на вопросы этого блока ещё раз.',
        );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Не удалось отправить ответы.');
    } finally {
      setLoading(false);
    }
  };

  const publish = async () => {
    if (!draftId) {
      setError('Не найден ID черновика. Начните оформление заново.');
      return;
    }
    const chosenText = finalText.trim();
    if (!chosenText) {
      setError('Укажите итоговый текст карточки или выберите свой вариант.');
      return;
    }
    const submittedFields = { ...fields, context: chosenText };
    setLoading(true);
    setError('');
    try {
      const result = await publishTaskDraft(draftId, {
        category,
        fields: submittedFields,
        finalText: chosenText,
        useGeneratedText,
      });
      const apiTask = result.task || {};
      const published: Task = {
        ...submittedFields,
        ...apiTask,
        context: chosenText,
        id: apiTask.id || `task-${Date.now()}`,
        author: 'Вы',
        category,
        rating: apiTask.rating ?? result.rating ?? backendResult?.rating ?? score.score,
        backendManaged: Boolean(apiTask.id),
        published: true,
        responses: [],
        createdAt: new Date().toISOString(),
      };
      onPublish(published);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Не удалось опубликовать задачу.');
    } finally {
      setLoading(false);
    }
  };

  const progress = stage === 'intro' ? 20 : stage === 'questions' ? 20 + round * 20 : 100;
  return (
    <div className="modal-backdrop" onClick={() => !loading && onClose()}>
      <div
        className="form-modal task-builder-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Конструктор задачи"
        onClick={(event) => event.stopPropagation()}
      >
        <button className="close-button" onClick={onClose} aria-label="Закрыть" disabled={loading}>
          <X size={21} />
        </button>
        <aside className="form-side task-builder-side">
          <span className="section-kicker">КОНСТРУКТОР ЗАДАЧИ</span>
          <div>
            <h2>
              Соберём задачу, понятную команде<span>.</span>
            </h2>
            <p>
              Backend уточнит детали в трёх блоках. Затем вы проверите текст, отредактируете
              карточку и подтвердите публикацию.
            </p>
          </div>
          <div className="form-progress-list">
            {[
              'Описание',
              'Контекст и люди',
              'Ресурсы и условия',
              'Успех и формат',
              'Проверка карточки',
            ].map((label, index) => {
              const activeIndex = stage === 'intro' ? 0 : stage === 'review' ? 4 : round;
              return (
                <div
                  key={label}
                  className={index === activeIndex ? 'current' : index < activeIndex ? 'done' : ''}
                >
                  <span>{index < activeIndex ? <Check size={16} /> : `0${index + 1}`}</span>
                  <div>
                    <strong>{label}</strong>
                    <small>
                      {index < activeIndex
                        ? 'Готово'
                        : index === activeIndex
                          ? 'Текущий шаг'
                          : 'Впереди'}
                    </small>
                  </div>
                </div>
              );
            })}
          </div>
        </aside>
        <div className="form-main task-builder-main">
          <div className="form-progress-top">
            <span>
              {stage === 'intro'
                ? 'ШАГ 1 ИЗ 5'
                : stage === 'questions'
                  ? `БЛОК УТОЧНЕНИЙ ${round} ИЗ 3`
                  : 'ПРОВЕРКА И ПУБЛИКАЦИЯ'}
            </span>
            <span>
              {stage === 'review' ? `${backendResult?.rating ?? score.score}/100` : `${progress}%`}
            </span>
          </div>
          <div className="progress-track">
            <div style={{ width: `${progress}%` }} />
          </div>
          <div className="task-builder-content">
            {stage === 'intro' && (
              <>
                <span className="form-icon">
                  <CircleHelp size={24} />
                </span>
                <h2>Опишите задачу своими словами</h2>
                <p>После отправки backend подготовит первый блок уточняющих вопросов.</p>
                <label>
                  Название задачи
                  <input
                    value={fields.title}
                    onChange={(event) => updateField('title', event.target.value)}
                    placeholder="Например, сократить пищевые отходы"
                  />
                </label>
                <label>
                  Категория
                  <select value={category} onChange={(event) => setCategory(event.target.value)}>
                    {taskCategories.map((item) => (
                      <option key={item}>{item}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Исходное описание
                  <textarea
                    rows={4}
                    value={fields.context}
                    onChange={(event) => updateField('context', event.target.value)}
                    placeholder="Что хотите изменить или создать? Опишите ситуацию, даже если пока не знаете деталей."
                  />
                </label>
              </>
            )}
            {stage === 'questions' && (
              <>
                <span className="form-icon">
                  <CircleHelp size={24} />
                </span>
                <h2>
                  {round === 1
                    ? 'Уточним контекст и пользователей'
                    : round === 2
                      ? 'Разберём ресурсы и ограничения'
                      : 'Определим результат и критерии'}
                </h2>
                <p>Вопросы пришли с backend. Ответы отправятся вместе с номером блока.</p>
                {questions.map((question) => (
                  <label key={question.id}>
                    {question.label || question.text}
                    <textarea
                      rows={3}
                      value={answers[question.id] || ''}
                      onChange={(event) => {
                        setAnswers((current) => ({
                          ...current,
                          [question.id]: event.target.value,
                        }));
                        setError('');
                      }}
                      placeholder={question.placeholder || 'Ваш ответ...'}
                    />
                  </label>
                ))}
              </>
            )}
            {stage === 'review' && (
              <>
                <span className="form-icon">
                  <Check size={24} />
                </span>
                <h2>Задача готова к публикации</h2>
                <p>
                  Backend подтвердил готовность. Выберите текст карточки, при необходимости
                  отредактируйте его и подтвердите публикацию.
                </p>
                <fieldset className="text-choice">
                  <legend>Какой текст использовать?</legend>
                  <label>
                    <input
                      type="radio"
                      name="text-choice"
                      checked={useGeneratedText}
                      onChange={() => {
                        setUseGeneratedText(true);
                        setFinalText(backendResult?.finalText || '');
                      }}
                      disabled={!backendResult?.finalText && !backendResult?.taskFields?.context}
                    />{' '}
                    Текст, подготовленный backend {backendResult?.finalText ? '' : '(не пришёл)'}
                  </label>
                  <label>
                    <input
                      type="radio"
                      name="text-choice"
                      checked={!useGeneratedText}
                      onChange={() => {
                        setUseGeneratedText(false);
                        setFinalText(originalText);
                      }}
                    />{' '}
                    Оставить свой исходный вариант
                  </label>
                </fieldset>
                <label>
                  {useGeneratedText
                    ? 'Итоговый текст backend (можно редактировать)'
                    : 'Ваш вариант (можно редактировать)'}
                  <textarea
                    rows={5}
                    value={finalText}
                    onChange={(event) => setFinalText(event.target.value)}
                    placeholder="Текст карточки задачи"
                  />
                </label>
                <div className="review-grid">
                  {(Object.keys(fieldLabels) as (keyof TaskFields)[])
                    .filter((key) => key !== 'title' && key !== 'context')
                    .map((key) => (
                      <label key={key}>
                        {fieldLabels[key]}
                        <textarea
                          rows={2}
                          value={fields[key]}
                          onChange={(event) => updateField(key, event.target.value)}
                          placeholder="Заполните или уточните"
                        />
                      </label>
                    ))}
                </div>
                <RatingBreakdown
                  fields={{ ...fields, context: finalText }}
                  scoreOverride={backendResult?.rating}
                />
              </>
            )}
          </div>
          {error && <p className="form-error">{error}</p>}
          <div className="form-footer">
            <button
              className="back-button"
              disabled={loading || stage !== 'review'}
              onClick={() => {
                setStage('questions');
                setError('');
              }}
            >
              <ArrowLeft size={17} /> К вопросам
            </button>
            {stage === 'intro' ? (
              <button className="primary-button" disabled={loading} onClick={begin}>
                {loading ? <LoaderCircle className="spin" size={18} /> : null}Отправить{' '}
                <ArrowRight size={18} />
              </button>
            ) : stage === 'questions' ? (
              <button
                className="primary-button"
                disabled={loading || questions.length === 0}
                onClick={submitAnswers}
              >
                {loading ? <LoaderCircle className="spin" size={18} /> : null}
                {round < 3 ? 'Отправить ответы' : 'Проверить готовность'} <ArrowRight size={18} />
              </button>
            ) : (
              <button className="primary-button" disabled={loading} onClick={publish}>
                {loading ? <LoaderCircle className="spin" size={18} /> : null}Подтвердить и
                опубликовать <Check size={18} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
