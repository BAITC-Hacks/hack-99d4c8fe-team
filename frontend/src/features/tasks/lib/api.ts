import type { Task, TaskFields } from '../types';

export type ClarificationQuestion = {
  id: string;
  text: string;
  label?: string;
  placeholder?: string;
};
export type DraftStartResponse = {
  draftId: string;
  questions: ClarificationQuestion[];
  message?: string;
};
export type ClarificationResponse = {
  ready: boolean;
  questions?: ClarificationQuestion[];
  finalText?: string;
  taskFields?: Partial<TaskFields>;
  rating?: number;
  message?: string;
};
export type PublishedTaskResponse = {
  task?: Partial<TaskFields> & { id?: string; rating?: number };
  rating?: number;
};

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || '').replace(/\/$/, '');
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    });
  } catch {
    throw new Error(
      'Не удалось связаться с backend. Проверьте NEXT_PUBLIC_API_BASE_URL и доступность сервера.',
    );
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    const detailMessage =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail
              .map((item: { msg?: string }) => item.msg)
              .filter(Boolean)
              .join('; ')
          : undefined;
    const message =
      body.message || body.error || detailMessage || `Ошибка backend (${response.status})`;
    throw new Error(`${response.status}: ${message}`);
  }
  return body as T;
}

export async function createTaskDraft(payload: {
  title: string;
  description: string;
  category: string;
}) {
  const result = await request<DraftStartResponse>('/api/task-drafts', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  if (!result.draftId || !Array.isArray(result.questions))
    throw new Error('Backend должен вернуть draftId и массив questions.');
  return result;
}

export async function answerClarificationRound(
  draftId: string,
  round: number,
  answers: { questionId: string; answer: string }[],
) {
  const result = await request<ClarificationResponse>(
    `/api/task-drafts/${encodeURIComponent(draftId)}/answers`,
    { method: 'POST', body: JSON.stringify({ round, answers }) },
  );
  if (typeof result.ready !== 'boolean')
    throw new Error('В ответе backend отсутствует обязательный флаг ready.');
  return result;
}

export async function publishTaskDraft(
  draftId: string,
  payload: { category: string; fields: TaskFields; finalText: string; useGeneratedText: boolean },
) {
  return request<PublishedTaskResponse>(`/api/task-drafts/${encodeURIComponent(draftId)}/publish`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function deleteTaskFromApi(taskId: string) {
  await request<void>(`/api/tasks/${encodeURIComponent(taskId)}`, { method: 'DELETE' });
}

export async function fetchPublishedTasks(): Promise<Task[]> {
  const result = await request<{ items: Task[] }>('/api/tasks');
  return Array.isArray(result.items) ? result.items : [];
}
