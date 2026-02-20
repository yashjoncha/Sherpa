import * as vscode from "vscode";
import { Ticket } from "./tickets";

const statusEmoji: Record<string, string> = {
  open: "⚪",
  in_progress: "🔵",
  in_review: "👁️",
  done: "✅",
  blocked: "🚫",
};

const priorityEmoji: Record<string, string> = {
  critical: "🔴",
  high: "🟠",
  medium: "🟡",
  low: "🟢",
};

function formatDate(iso?: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function formatDateTime(iso?: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function statusLabel(status: string): string {
  return status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function priorityLabel(priority: string): string {
  return priority.charAt(0).toUpperCase() + priority.slice(1);
}

export function showTicketPanel(ticket: Ticket, extensionUri: vscode.Uri) {
  const panel = vscode.window.createWebviewPanel(
    "sherpaTicketDetail",
    `${ticket.task_id}: ${ticket.title}`,
    vscode.ViewColumn.One,
    { enableScripts: false }
  );

  panel.webview.html = getHtml(ticket);
}

function getHtml(ticket: Ticket): string {
  const sEmoji = statusEmoji[ticket.status] ?? "⚪";
  const pEmoji = priorityEmoji[ticket.priority] ?? "⚪";

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>
    body {
      font-family: var(--vscode-font-family, system-ui, sans-serif);
      color: var(--vscode-foreground);
      background: var(--vscode-editor-background);
      padding: 24px 32px;
      line-height: 1.6;
    }
    .header {
      margin-bottom: 24px;
      border-bottom: 1px solid var(--vscode-widget-border, #333);
      padding-bottom: 16px;
    }
    .task-id {
      font-size: 13px;
      color: var(--vscode-descriptionForeground);
      letter-spacing: 0.5px;
      margin-bottom: 4px;
    }
    h1 {
      font-size: 22px;
      font-weight: 600;
      margin: 0;
    }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px 32px;
      margin-top: 16px;
    }
    .field {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .field-label {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: var(--vscode-descriptionForeground);
    }
    .field-value {
      font-size: 14px;
      font-weight: 500;
    }
    .badge {
      display: inline-block;
      padding: 2px 10px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 600;
    }
    .badge-status {
      background: var(--vscode-badge-background, #333);
      color: var(--vscode-badge-foreground, #fff);
    }
    .badge-priority {
      background: var(--vscode-badge-background, #333);
      color: var(--vscode-badge-foreground, #fff);
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="task-id">${ticket.task_id}</div>
    <h1>${ticket.title}</h1>
  </div>
  <div class="grid">
    <div class="field">
      <span class="field-label">Status</span>
      <span class="field-value"><span class="badge badge-status">${sEmoji} ${statusLabel(ticket.status)}</span></span>
    </div>
    <div class="field">
      <span class="field-label">Priority</span>
      <span class="field-value"><span class="badge badge-priority">${pEmoji} ${priorityLabel(ticket.priority)}</span></span>
    </div>
    <div class="field">
      <span class="field-label">Story Points</span>
      <span class="field-value">${ticket.story_points}</span>
    </div>
    <div class="field">
      <span class="field-label">External Deadline</span>
      <span class="field-value">${formatDate(ticket.external_deadline)}</span>
    </div>
    <div class="field">
      <span class="field-label">Internal Deadline</span>
      <span class="field-value">${formatDate(ticket.internal_deadline)}</span>
    </div>
    <div class="field">
      <span class="field-label">Created</span>
      <span class="field-value">${formatDateTime(ticket.created_at)}</span>
    </div>
    <div class="field">
      <span class="field-label">Updated</span>
      <span class="field-value">${formatDateTime(ticket.updated_at)}</span>
    </div>
  </div>
</body>
</html>`;
}
