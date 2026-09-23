import { useState } from 'react';
import { ArrowLeft, ArrowRight, Check, CircleHelp, X } from 'lucide-react';
import { emptyTaskFields, type Task, type TaskFields } from '../types';
import { calculateTaskScore, getReadiness } from '../lib/rating';
import { RatingBreakdown } from './RatingBreakdown';

const rounds: { title: string; subtitle: string; fields: { key: keyof TaskFields; label: string; placeholder: string }[] }[] = [
  { title: 'Поможем понять задачу', subtitle: 'Раунд 1 из 3 · контекст и люди', fields: [
    { key: 'context', label: 'В каком контексте возникла задача?', placeholder: 'Что происходит сейчас? Где и когда проявляется проблема?' },
    { key: 'need', label: 'Какую потребность или проблему нужно решить?', placeholder: 'Что сейчас не получается и почему это важно?' },
    { key: 'users', label: 'Для кого ищем решение?', placeholder: 'Опишите людей, которые столкнулись с проблемой.' },
  ] },
  { title: 'Уточним условия', subtitle: 'Раунд 2 из 3 · ресурсы и ограничения', fields: [
    { key: 'data', label: 'Какие данные или материалы уже доступны?', placeholder: 'Данные, исследования, доступ к площадкам, оборудование...' },
    { key: 'constraints', label: 'Какие есть ограничения?', placeholder: 'Сроки, бюджет, технологии, доступы, правила безопасности...' },
    { key: 'expectedResult', label: 'Какой результат вы хотите получить?', placeholder: 'Например: прототип, исследование, сервис или план пилота.' },
  ] },
  { title: 'Определим успех', subtitle: 'Раунд 3 из 3 · критерии и взаимодействие', fields: [
    { key: 'successCriteria', label: 'Как поймём, что решение сработало?', placeholder: 'Назовите измеримый результат или способ проверки.' },
    { key: 'contact', label: 'Как с вами связаться?', placeholder: 'Имя и рабочая почта или другой удобный контакт.' },
    { key: 'collaboration', label: 'Как будет устроена работа с командой?', placeholder: 'Онлайн или офлайн, примерная занятость, встречи, сроки.' },
  ] },
];
const fieldLabels: Record<keyof TaskFields, string> = { title:'Название задачи', context:'Контекст', need:'Потребность', users:'Пользователи', data:'Данные и материалы', constraints:'Ограничения', expectedResult:'Ожидаемый результат', successCriteria:'Критерии успеха', contact:'Контакт', collaboration:'Формат взаимодействия' };

export function TaskBuilder({ onClose, onPublish }: { onClose: () => void; onPublish: (task: Task) => void }) {
  const [fields, setFields] = useState<TaskFields>(emptyTaskFields);
  const [category, setCategory] = useState('Технологии');
  const [step, setStep] = useState(-1); // first screen is free-form idea input
  const [error, setError] = useState('');
  const update = (key: keyof TaskFields, value: string) => { setFields((current) => ({ ...current, [key]: value })); setError(''); };
  const score = calculateTaskScore(fields);
  const canContinue = step === -1 ? fields.title.trim().length >= 3 : rounds[step]?.fields.every(({ key }) => fields[key].trim());
  const next = () => {
    if (!canContinue) { setError(step === -1 ? 'Добавьте название задачи, чтобы продолжить.' : 'Заполните все три уточнения этого раунда.'); return; }
    setError(''); setStep((current) => current + 1);
  };
  const publish = () => {
    if (score.score < 40) { setError('Для публикации заполните карточку хотя бы на 40 баллов. Добавьте недостающий контекст, потребность и аудиторию.'); return; }
    onPublish({ ...fields, id: `task-${Date.now()}`, author: 'Вы', category, rating: score.score, published: true, responses: [] });
  };
  return <div className="modal-backdrop" onClick={onClose}><div className="form-modal task-builder-modal" role="dialog" aria-modal="true" aria-label="Конструктор задачи" onClick={(event) => event.stopPropagation()}>
    <button className="close-button" onClick={onClose} aria-label="Закрыть"><X size={21}/></button>
    <aside className="form-side task-builder-side"><span className="section-kicker">КОНСТРУКТОР ЗАДАЧИ</span><div><h2>Соберём задачу, понятную команде<span>.</span></h2><p>Опишите идею, ответьте на три раунда уточнений, отредактируйте карточку и подтвердите публикацию вручную.</p></div>
      <div className="form-progress-list">{['Описание','Контекст и люди','Ресурсы и условия','Успех и формат','Проверка карточки'].map((label, index) => <div key={label} className={index === step + 1 ? 'current' : index < step + 1 ? 'done' : ''}><span>{index < step + 1 ? <Check size={16}/> : `0${index + 1}`}</span><div><strong>{label}</strong><small>{index < step + 1 ? 'Готово' : index === step + 1 ? 'Текущий шаг' : 'Впереди'}</small></div></div>)}</div>
    </aside>
    <div className="form-main task-builder-main">
      <div className="form-progress-top"><span>{step < 0 ? 'ШАГ 1 ИЗ 5' : step < 3 ? `РАУНД ${step + 1} ИЗ 3` : 'ПРОВЕРКА И РЕДАКТИРОВАНИЕ'}</span><span>{step < 3 ? `${Math.max(1, step + 2) * 20}%` : `${score.score}/100`}</span></div><div className="progress-track"><div style={{ width: step === 4 ? '100%' : `${Math.max(1, step + 2) * 20}%` }}/></div>
      <div className="task-builder-content">
        {step === -1 && <><span className="form-icon"><CircleHelp size={24}/></span><h2>Начните со свободного описания</h2><p>Напишите своими словами, что хотите изменить или создать. Мы поможем уточнить задачу по шагам.</p><label>Название задачи<input value={fields.title} onChange={(event) => update('title', event.target.value)} placeholder="Например, сократить пищевые отходы"/></label><label>Тема<select value={category} onChange={(event) => setCategory(event.target.value)}><option>Технологии</option><option>Образование</option><option>Экология</option><option>Еда и сервис</option><option>Социальные проекты</option><option>Другое</option></select></label><label>Краткое описание идеи<textarea rows={3} value={fields.context} onChange={(event) => update('context', event.target.value)} placeholder="Что вы хотите решить? Опишите ситуацию, даже если пока не знаете деталей."/></label></>}
        {step >= 0 && step < 3 && <><span className="form-icon"><CircleHelp size={24}/></span><h2>{rounds[step].title}</h2><p>{rounds[step].subtitle}. Ответы можно будет поправить в итоговой карточке.</p>{rounds[step].fields.map(({ key, label, placeholder }) => <label key={key}>{label}<textarea rows={3} value={fields[key]} onChange={(event) => update(key, event.target.value)} placeholder={placeholder}/></label>)}</>}
        {step === 3 && <><span className="form-icon"><Check size={24}/></span><h2>Проверьте и отредактируйте карточку</h2><p>Все поля доступны для редактирования. Рейтинг обновляется автоматически.</p><div className="review-grid">{(Object.keys(fieldLabels) as (keyof TaskFields)[]).map((key) => <label key={key}>{fieldLabels[key]}{key === 'title' ? <input value={fields[key]} onChange={(event) => update(key, event.target.value)} placeholder="Заполните поле"/> : <textarea rows={key === 'context' || key === 'need' ? 3 : 2} value={fields[key]} onChange={(event) => update(key, event.target.value)} placeholder="Добавьте информацию или оставьте пустым"/>}</label>)}</div><RatingBreakdown fields={fields}/></>}
        {step === 4 && <><span className="form-icon"><Check size={24}/></span><h2>Карточка готова к подтверждению</h2><p>После подтверждения задача появится в общем каталоге для всех команд. Отклики вы будете выбирать вручную.</p><div className="confirm-summary"><div className="card-topline"><span>{category}</span><b>{score.score}/100 · {score.score >= 70 ? 'Готова к запуску' : 'В проработке'}</b></div><h3>{fields.title}</h3><p>{fields.need || fields.context}</p><RatingBreakdown fields={fields} compact/></div><button className="text-link edit-again" onClick={() => setStep(3)}><ArrowLeft size={16}/> Вернуться к редактированию</button></>}
      </div>
      {error && <p className="form-error">{error}</p>}
      <div className="form-footer"><button className="back-button" disabled={step === -1} onClick={() => { setError(''); setStep((current) => current - 1); }}><ArrowLeft size={17}/> Назад</button>{step < 3 ? <button className="primary-button" onClick={next}>Продолжить <ArrowRight size={18}/></button> : step === 3 ? <button className="primary-button" onClick={() => { setError(''); setStep(4); }}>Перейти к подтверждению <ArrowRight size={18}/></button> : <button className="primary-button" onClick={publish}>Подтвердить и опубликовать <Check size={18}/></button>}</div>
    </div>
  </div></div>;
}
