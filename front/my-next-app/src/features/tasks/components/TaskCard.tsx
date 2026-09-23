import { ArrowUpRight, MessageCircle, Star } from 'lucide-react';
import type { Task } from '../types';
import { getReadiness } from '../lib/rating';

const readinessLabels = { idea: 'Идея', developing: 'В проработке', ready: 'Готова к запуску' };
export function TaskCard({ task, onOpen, onRespond }: { task: Task; onOpen: (task: Task) => void; onRespond: (task: Task) => void }) {
  const readiness = getReadiness(task.rating);
  return <article className="idea-card task-card">
    <div className={`card-art ${task.category === 'Экология' ? 'mint' : task.category === 'Образование' ? 'lavender' : 'peach'}`}>
      <span className="art-emoji">{task.category === 'Экология' ? '🌱' : task.category === 'Образование' ? '✦' : '◈'}</span>
      <span className={`readiness-badge ${readiness}`}>{readinessLabels[readiness]}</span>
    </div>
    <div className="card-content">
      <div className="card-topline"><span>{task.category}</span><span className="rating"><Star size={14} fill="currentColor"/> {task.rating}/100</span></div>
      <h3>{task.title}</h3><p className="card-desc">{task.need || task.context}</p>
      <div className="task-mini-meta"><span>{task.author}</span><span><MessageCircle size={13}/> {task.responses.length} откликов</span></div>
      <div className="card-bottom"><button className="outline-button task-detail-button" onClick={() => onOpen(task)}>Подробнее <ArrowUpRight size={16}/></button><button className="card-arrow" onClick={() => onRespond(task)} aria-label="Откликнуться на задачу"><ArrowUpRight size={19}/></button></div>
    </div>
  </article>;
}
