import * as vscode from "vscode";
import { Ticket, Member } from "./tickets";
import { fetchTicketDetail, fetchMembers, updateTicket } from "./api";

const statusEmoji: Record<string, string> = {
  open: "⚪",
  planning: "📋",
  todo: "📝",
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

const STATUSES = ["open", "planning", "todo", "in_progress", "in_review", "done", "blocked"];
const PRIORITIES = ["critical", "high", "medium", "low"];

let currentPanel: vscode.WebviewPanel | undefined;
let currentTaskId: string | undefined;
let messageDisposable: vscode.Disposable | undefined;

export function showTicketPanel(
  ticket: Ticket,
  extensionUri: vscode.Uri,
  onRefresh: () => void
) {
  if (currentPanel) {
    // Reuse existing panel — just update content
    currentPanel.title = `${ticket.task_id}: ${ticket.title}`;
    currentPanel.reveal(vscode.ViewColumn.One);
  } else {
    // Create new panel
    currentPanel = vscode.window.createWebviewPanel(
      "sherpaTicketDetail",
      `${ticket.task_id}: ${ticket.title}`,
      vscode.ViewColumn.One,
      { enableScripts: true }
    );
    currentPanel.onDidDispose(() => {
      currentPanel = undefined;
      currentTaskId = undefined;
      if (messageDisposable) {
        messageDisposable.dispose();
        messageDisposable = undefined;
      }
    });
  }

  // Dispose old message listener before setting up new one
  if (messageDisposable) {
    messageDisposable.dispose();
    messageDisposable = undefined;
  }

  currentTaskId = ticket.task_id;
  loadAndRender(currentPanel, ticket.task_id, onRefresh);
}

async function loadAndRender(
  panel: vscode.WebviewPanel,
  taskId: string,
  onRefresh: () => void
) {
  try {
    const [ticket, members] = await Promise.all([
      fetchTicketDetail(taskId),
      fetchMembers(),
    ]);

    // Guard: user may have clicked another ticket while loading
    if (currentTaskId !== taskId) return;

    panel.webview.html = getHtml(ticket, members);

    messageDisposable = panel.webview.onDidReceiveMessage(async (msg) => {
      if (msg.type === "save") {
        try {
          await updateTicket(taskId, msg.fields);
          vscode.window.showInformationMessage(`${taskId} updated.`);
          onRefresh();
          const updated = await fetchTicketDetail(taskId);
          if (currentTaskId === taskId) {
            panel.webview.html = getHtml(updated, members);
          }
        } catch (err: any) {
          vscode.window.showErrorMessage(`Sherpa: ${err.message}`);
        }
      }
    });
  } catch (err: any) {
    panel.webview.html = `<html><body><h2>Error loading ticket</h2><p>${err.message}</p></body></html>`;
  }
}

function statusLabel(status: string): string {
  return status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
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

function escapeHtml(val: unknown): string {
  const str = typeof val === "string" ? val : val == null ? "" : typeof val === "object" ? JSON.stringify(val) : String(val);
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function getHtml(ticket: Ticket, members: Member[]): string {
  const statusOptions = STATUSES.map(
    (s) =>
      `<option value="${s}" ${s === ticket.status ? "selected" : ""}>${statusEmoji[s] ?? "⚪"} ${statusLabel(s)}</option>`
  ).join("");

  const priorityOptions = PRIORITIES.map(
    (p) =>
      `<option value="${p}" ${p === ticket.priority ? "selected" : ""}>${priorityEmoji[p] ?? "⚪"} ${p.charAt(0).toUpperCase() + p.slice(1)}</option>`
  ).join("");

  const assigneeList =
    (ticket.assignees ?? [])
      .map((a: any) => (typeof a === "string" ? a : a.display_name || a.username || a.name || JSON.stringify(a)))
      .join(", ") || "Unassigned";

  const memberOptions = members
    .map(
      (m) =>
        `<option value="${m.slack_user_id}">${escapeHtml(m.display_name)} (${escapeHtml(m.github_username)})</option>`
    )
    .join("");

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
    h1 { font-size: 22px; font-weight: 600; margin: 0; }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px 32px;
      margin-top: 16px;
    }
    .field { display: flex; flex-direction: column; gap: 4px; }
    .field-label {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: var(--vscode-descriptionForeground);
    }
    .field-value { font-size: 14px; font-weight: 500; }
    .full-width { grid-column: 1 / -1; }
    select, input, textarea {
      background: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border, #444);
      padding: 6px 8px;
      font-size: 13px;
      border-radius: 4px;
      font-family: inherit;
    }
    textarea { min-height: 100px; resize: vertical; }
    .btn {
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      padding: 8px 20px;
      font-size: 13px;
      border-radius: 4px;
      cursor: pointer;
      margin-top: 16px;
    }
    .btn:hover { background: var(--vscode-button-hoverBackground); }
    .meta {
      font-size: 12px;
      color: var(--vscode-descriptionForeground);
      margin-top: 20px;
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="task-id">${escapeHtml(ticket.task_id)}</div>
    <h1>${escapeHtml(ticket.title)}</h1>
  </div>

  <div class="grid">
    <div class="field">
      <span class="field-label">Status</span>
      <select id="status">${statusOptions}</select>
    </div>
    <div class="field">
      <span class="field-label">Priority</span>
      <select id="priority">${priorityOptions}</select>
    </div>
    <div class="field">
      <span class="field-label">Story Points</span>
      <input id="story_points" type="number" min="0" value="${ticket.story_points ?? 0}" />
    </div>
    <div class="field">
      <span class="field-label">Assignees</span>
      <span class="field-value">${escapeHtml(assigneeList)}</span>
    </div>
    <div class="field">
      <span class="field-label">Assign to</span>
      <select id="assignee">
        <option value="">— Don't change —</option>
        ${memberOptions}
      </select>
    </div>
    <div class="field">
      <span class="field-label">Sprint</span>
      <span class="field-value">${escapeHtml(typeof ticket.sprint === "object" && ticket.sprint ? (ticket.sprint as any).name : ticket.sprint ?? "—")}</span>
    </div>
    <div class="field full-width">
      <span class="field-label">Description</span>
      <textarea id="description">${escapeHtml(ticket.description ?? "")}</textarea>
    </div>
  </div>

  <button class="btn" onclick="save()">Save Changes</button>

  <div class="meta">
    Created: ${formatDateTime(ticket.created_at)} &nbsp;|&nbsp;
    Updated: ${formatDateTime(ticket.updated_at)}
    ${ticket.project ? " &nbsp;|&nbsp; Project: " + escapeHtml(typeof ticket.project === "object" && ticket.project ? (ticket.project as any).name : ticket.project) : ""}
  </div>

  <script>
    const vscode = acquireVsCodeApi();
    function save() {
      const fields = {
        status: document.getElementById("status").value,
        priority: document.getElementById("priority").value,
        story_points: Number(document.getElementById("story_points").value),
        description: document.getElementById("description").value,
      };
      const assignee = document.getElementById("assignee").value;
      if (assignee) {
        fields.assignee = assignee;
      }
      vscode.postMessage({ type: "save", fields });
    }
  </script>
</body>
</html>`;
}
