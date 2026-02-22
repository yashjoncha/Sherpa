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

  // Match current assignee to a member slack_user_id
  let currentAssigneeSlackId = "";
  const assignees = ticket.assignees ?? [];
  if (assignees.length > 0) {
    const first: any = assignees[0];
    const name = typeof first === "string" ? first : first.display_name || first.username || first.name || "";
    const nameLower = name.toLowerCase();
    const match = members.find(
      (m) =>
        m.slack_user_id === name ||
        m.display_name.toLowerCase() === nameLower ||
        m.github_username.toLowerCase() === nameLower
    );
    if (match) currentAssigneeSlackId = match.slack_user_id;
  }

  const memberOptions = members
    .map(
      (m) =>
        `<option value="${m.slack_user_id}" ${m.slack_user_id === currentAssigneeSlackId ? "selected" : ""}>${escapeHtml(m.display_name)}</option>`
    )
    .join("");

  const sprintName = typeof ticket.sprint === "object" && ticket.sprint ? (ticket.sprint as any).name : ticket.sprint ?? "";
  const projectName = typeof ticket.project === "object" && ticket.project ? (ticket.project as any).name : ticket.project ?? "";

  const statusColor: Record<string, string> = {
    open: "#9e9e9e",
    planning: "#ab47bc",
    todo: "#42a5f5",
    in_progress: "#1e88e5",
    in_review: "#ff9800",
    done: "#66bb6a",
    blocked: "#ef5350",
  };

  const priorityColor: Record<string, string> = {
    critical: "#ef5350",
    high: "#ff9800",
    medium: "#ffca28",
    low: "#66bb6a",
  };

  const currentStatusColor = statusColor[ticket.status] ?? "#9e9e9e";
  const currentPriorityColor = priorityColor[ticket.priority] ?? "#9e9e9e";

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--vscode-font-family, system-ui, sans-serif);
      color: var(--vscode-foreground);
      background: var(--vscode-editor-background);
      padding: 24px 32px 40px;
      line-height: 1.5;
    }

    /* ── Header ── */
    .header {
      display: flex;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 28px;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--vscode-widget-border, rgba(255,255,255,0.08));
    }
    .header-content { flex: 1; min-width: 0; }
    .task-id {
      display: inline-block;
      font-size: 12px;
      font-weight: 600;
      color: var(--vscode-button-background, #007acc);
      background: color-mix(in srgb, var(--vscode-button-background, #007acc) 15%, transparent);
      padding: 2px 8px;
      border-radius: 4px;
      letter-spacing: 0.3px;
      margin-bottom: 8px;
    }
    h1 {
      font-size: 22px;
      font-weight: 600;
      line-height: 1.3;
      word-break: break-word;
    }

    /* ── Badges row ── */
    .badges {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 24px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      font-weight: 500;
      padding: 4px 10px;
      border-radius: 20px;
      background: var(--vscode-input-background);
      border: 1px solid var(--vscode-input-border, rgba(255,255,255,0.1));
    }
    .badge-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      flex-shrink: 0;
    }

    /* ── Card sections ── */
    .section {
      background: var(--vscode-input-background);
      border: 1px solid var(--vscode-input-border, rgba(255,255,255,0.08));
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 16px;
    }
    .section-title {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: var(--vscode-descriptionForeground);
      margin-bottom: 16px;
      font-weight: 600;
    }

    /* ── Grid inside sections ── */
    .fields-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px 24px;
    }
    .field { display: flex; flex-direction: column; gap: 6px; }
    .field-label {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      color: var(--vscode-descriptionForeground);
      font-weight: 500;
    }
    .field-value {
      font-size: 13px;
      font-weight: 500;
      color: var(--vscode-foreground);
    }
    .full-width { grid-column: 1 / -1; }

    /* ── Inputs ── */
    select, input[type="number"] {
      background: var(--vscode-editor-background);
      color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border, rgba(255,255,255,0.12));
      padding: 7px 10px;
      font-size: 13px;
      border-radius: 6px;
      font-family: inherit;
      width: 100%;
      transition: border-color 0.15s;
    }
    select:hover, input:hover, textarea:hover {
      border-color: var(--vscode-focusBorder, #007acc);
    }
    select:focus, input:focus, textarea:focus {
      outline: none;
      border-color: var(--vscode-focusBorder, #007acc);
      box-shadow: 0 0 0 1px var(--vscode-focusBorder, #007acc);
    }
    textarea {
      background: var(--vscode-editor-background);
      color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border, rgba(255,255,255,0.12));
      padding: 10px 12px;
      font-size: 13px;
      border-radius: 6px;
      font-family: inherit;
      width: 100%;
      min-height: 120px;
      resize: vertical;
      transition: border-color 0.15s;
      line-height: 1.5;
    }

    /* ── Save button ── */
    .actions {
      display: flex;
      gap: 10px;
      margin-top: 8px;
    }
    .btn-save {
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      padding: 9px 28px;
      font-size: 13px;
      font-weight: 500;
      border-radius: 6px;
      cursor: pointer;
      transition: background 0.15s, transform 0.1s;
    }
    .btn-save:hover {
      background: var(--vscode-button-hoverBackground);
    }
    .btn-save:active { transform: scale(0.98); }

    /* ── Footer meta ── */
    .meta {
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
      font-size: 11px;
      color: var(--vscode-descriptionForeground);
      margin-top: 24px;
      padding-top: 16px;
      border-top: 1px solid var(--vscode-widget-border, rgba(255,255,255,0.06));
    }
    .meta-item {
      display: flex;
      align-items: center;
      gap: 4px;
    }
    .meta-label { opacity: 0.7; }
  </style>
</head>
<body>

  <!-- Header -->
  <div class="header">
    <div class="header-content">
      <div class="task-id">${escapeHtml(ticket.task_id)}</div>
      <h1>${escapeHtml(ticket.title)}</h1>
    </div>
  </div>

  <!-- Status badges -->
  <div class="badges">
    <span class="badge">
      <span class="badge-dot" style="background:${currentStatusColor}"></span>
      ${statusEmoji[ticket.status] ?? "⚪"} ${escapeHtml(statusLabel(ticket.status))}
    </span>
    <span class="badge">
      <span class="badge-dot" style="background:${currentPriorityColor}"></span>
      ${priorityEmoji[ticket.priority] ?? "⚪"} ${escapeHtml(ticket.priority.charAt(0).toUpperCase() + ticket.priority.slice(1))}
    </span>
    ${sprintName ? `<span class="badge">🏃 ${escapeHtml(sprintName)}</span>` : ""}
    ${projectName ? `<span class="badge">📁 ${escapeHtml(projectName)}</span>` : ""}
  </div>

  <!-- Details section -->
  <div class="section">
    <div class="section-title">Details</div>
    <div class="fields-grid">
      <div class="field">
        <span class="field-label">Status</span>
        <select id="status">${statusOptions}</select>
      </div>
      <div class="field">
        <span class="field-label">Priority</span>
        <select id="priority">${priorityOptions}</select>
      </div>
      <div class="field">
        <span class="field-label">Assign To</span>
        <select id="assignee">
          <option value="">Unassigned</option>
          ${memberOptions}
        </select>
      </div>
      <div class="field">
        <span class="field-label">Story Points</span>
        <input id="story_points" type="number" min="0" value="${ticket.story_points ?? 0}" />
      </div>
    </div>
  </div>

  <!-- Description section -->
  <div class="section">
    <div class="section-title">Description</div>
    <textarea id="description" placeholder="Add a description...">${escapeHtml(ticket.description ?? "")}</textarea>
  </div>

  <!-- Actions -->
  <div class="actions">
    <button class="btn-save" onclick="save()">Save Changes</button>
  </div>

  <!-- Footer -->
  <div class="meta">
    <span class="meta-item">
      <span class="meta-label">Created</span> ${formatDateTime(ticket.created_at)}
    </span>
    <span class="meta-item">
      <span class="meta-label">Updated</span> ${formatDateTime(ticket.updated_at)}
    </span>
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
