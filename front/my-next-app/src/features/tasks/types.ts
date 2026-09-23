export type Readiness = 'idea' | 'developing' | 'ready';

export type TaskFields = {
  title: string;
  context: string;
  need: string;
  users: string;
  data: string;
  constraints: string;
  expectedResult: string;
  successCriteria: string;
  contact: string;
  collaboration: string;
};

export type TeamResponse = {
  id: string;
  teamName: string;
  idea: string;
  plan: string;
  prototypeUrl: string;
  status: 'pending' | 'accepted' | 'rejected';
  createdAt: string;
};

export type Task = TaskFields & {
  id: string;
  author: string;
  category: string;
  rating: number;
  published: boolean;
  responses: TeamResponse[];
};

export const emptyTaskFields: TaskFields = {
  title: '', context: '', need: '', users: '', data: '', constraints: '',
  expectedResult: '', successCriteria: '', contact: '', collaboration: '',
};
