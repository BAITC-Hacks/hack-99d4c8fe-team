import type { TaskFields } from '../types';

export const scoreRubric: { key: keyof TaskFields; label: string; points: number }[] = [
  { key: 'title', label: 'Название задачи', points: 10 },
  { key: 'context', label: 'Контекст и текущая ситуация', points: 12 },
  { key: 'need', label: 'Потребность или проблема', points: 12 },
  { key: 'users', label: 'Пользователи или аудитория', points: 10 },
  { key: 'data', label: 'Доступные данные и материалы', points: 8 },
  { key: 'constraints', label: 'Ограничения и условия', points: 8 },
  { key: 'expectedResult', label: 'Ожидаемый результат', points: 12 },
  { key: 'successCriteria', label: 'Критерии успеха', points: 10 },
  { key: 'contact', label: 'Контакт для связи', points: 10 },
  { key: 'collaboration', label: 'Формат взаимодействия', points: 8 },
];

export function calculateTaskScore(fields: TaskFields) {
  const earned = scoreRubric.map((criterion) => ({
    ...criterion,
    earned: fields[criterion.key].trim() ? criterion.points : 0,
  }));
  return {
    score: earned.reduce((sum, item) => sum + item.earned, 0),
    breakdown: earned,
    missing: earned.filter((item) => !fields[item.key].trim()).map((item) => item.label),
  };
}

export function getReadiness(score: number) {
  if (score >= 70) return 'ready' as const;
  if (score >= 40) return 'developing' as const;
  return 'idea' as const;
}
