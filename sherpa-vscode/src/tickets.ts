export interface Ticket {
  id: number;
  task_id: string;
  title: string;
  status: "open" | "in_progress" | "in_review" | "done" | "blocked";
  priority: "critical" | "high" | "medium" | "low";
  story_points: number;
  external_deadline?: string;
  internal_deadline?: string;
  created_at?: string;
  updated_at?: string;
}
