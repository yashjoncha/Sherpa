export interface Ticket {
  id: number;
  task_id: string;
  title: string;
  status: "open" | "planning" | "todo" | "in_progress" | "in_review" | "done" | "blocked";
  priority: "critical" | "high" | "medium" | "low";
  story_points: number;
  description?: string;
  assignees?: string[];
  sprint?: string;
  project?: string;
  external_deadline?: string;
  internal_deadline?: string;
  created_at?: string;
  updated_at?: string;
}

export interface Member {
  id: number;
  display_name: string;
  github_username: string;
  slack_user_id: string;
}

export interface Sprint {
  id: number | string;
  name: string;
  status?: string;
  start_date?: string;
  end_date?: string;
}

export interface Project {
  id: number | string;
  name: string;
}

export interface SprintProgress {
  sprint: {
    id: number | string;
    name: string;
    start_date: string | null;
    end_date: string | null;
  } | null;
  progress: {
    total: number;
    done: number;
    in_progress: number;
    todo: number;
    blocked: number;
    other: number;
    percentage: number;
  } | null;
}

export interface CreateTicketPayload {
  title: string;
  description?: string;
  priority?: string;
  story_points?: number;
  assignee?: string;
  sprint?: string;
  project?: string;
}
