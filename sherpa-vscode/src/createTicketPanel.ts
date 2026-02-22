import * as vscode from "vscode";
import { Member, Project, Sprint } from "./tickets";
import { createTicket, fetchMembers, fetchProjects, fetchSprints, fetchAIProjectMatch } from "./api";
import { detectWorkspace, matchProject } from "./workspace";

const PRIORITIES = ["critical", "high", "medium", "low"];

export async function showCreateTicketPanel(
  extensionUri: vscode.Uri,
  onRefresh: () => void
) {
  let members: Member[] = [];
  let projects: Project[] = [];
  let sprints: Sprint[] = [];
  try {
    [members, projects, sprints] = await Promise.all([fetchMembers(), fetchProjects(), fetchSprints()]);
  } catch {
    // Non-critical — form still works without these lists
  }

  // Pick the latest active sprint (by end_date descending)
  const activeSprints = sprints.filter((s) => s.status === "active");
  activeSprints.sort((a, b) => {
    const da = a.end_date ?? "";
    const db = b.end_date ?? "";
    return db.localeCompare(da);
  });
  const latestActiveSprint = activeSprints[0];

  let matchedProject: Project | undefined;
  try {
    const ws = await detectWorkspace();
    if (ws.repoName) {
      matchedProject = matchProject(ws.repoName, projects);
      if (!matchedProject && projects.length > 0) {
        const aiMatch = await fetchAIProjectMatch(
          ws.repoName,
          projects.map((p) => p.name)
        );
        if (aiMatch) {
          matchedProject = projects.find((p) => p.name === aiMatch);
        }
      }
    }
  } catch {
    // Workspace detection is best-effort
  }

  // Determine current GitHub user to pre-select as assignee
  let currentGitHubUsername = "";
  try {
    const session = await vscode.authentication.getSession("github", ["user:email"], {
      createIfNone: false,
    });
    if (session) {
      currentGitHubUsername = session.account.label;
    }
  } catch {
    // Best-effort
  }

  const panel = vscode.window.createWebviewPanel(
    "sherpaCreateTicket",
    "Create Ticket",
    vscode.ViewColumn.One,
    { enableScripts: true }
  );

  panel.webview.html = getHtml(members, projects, sprints, matchedProject, latestActiveSprint, currentGitHubUsername);

  panel.webview.onDidReceiveMessage(async (msg) => {
    if (msg.type === "create") {
      try {
        const ticket = await createTicket(msg.payload);
        vscode.window.showInformationMessage(
          `Ticket created: ${ticket.task_id ?? ticket.id}`
        );
        onRefresh();
        panel.dispose();
      } catch (err: any) {
        vscode.window.showErrorMessage(`Sherpa: ${err.message}`);
      }
    }
  });
}

function escapeHtml(val: unknown): string {
  const str = typeof val === "string" ? val : val == null ? "" : String(val);
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function getHtml(
  members: Member[],
  projects: Project[],
  sprints: Sprint[],
  matchedProject?: Project,
  latestActiveSprint?: Sprint,
  currentGitHubUsername?: string
): string {
  const priorityOptions = PRIORITIES.map(
    (p) => `<option value="${p}">${p.charAt(0).toUpperCase() + p.slice(1)}</option>`
  ).join("");

  const memberOptions = members
    .map((m) => {
      const selected =
        currentGitHubUsername &&
        m.github_username.toLowerCase() === currentGitHubUsername.toLowerCase()
          ? " selected"
          : "";
      return `<option value="${m.slack_user_id}"${selected}>${escapeHtml(m.display_name)} (${escapeHtml(m.github_username)})</option>`;
    })
    .join("");

  const sprintOptions = sprints
    .map((s) => {
      const selected = latestActiveSprint && String(s.id) === String(latestActiveSprint.id) ? " selected" : "";
      const label = s.status === "active" ? `${s.name} (active)` : s.name;
      return `<option value="${escapeHtml(String(s.id))}"${selected}>${escapeHtml(label)}</option>`;
    })
    .join("");

  const projectOptions = projects
    .map((p) => {
      const selected = matchedProject && String(p.id) === String(matchedProject.id) ? " selected" : "";
      return `<option value="${escapeHtml(String(p.id))}"${selected}>${escapeHtml(p.name)}</option>`;
    })
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
    h1 { font-size: 22px; font-weight: 600; margin: 0 0 24px; }
    .form { display: flex; flex-direction: column; gap: 16px; max-width: 600px; }
    .field { display: flex; flex-direction: column; gap: 4px; }
    .field-label {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: var(--vscode-descriptionForeground);
    }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    input, select, textarea {
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
      align-self: flex-start;
    }
    .btn:hover { background: var(--vscode-button-hoverBackground); }
  </style>
</head>
<body>
  <h1>Create Ticket</h1>
  <div class="form">
    <div class="field">
      <span class="field-label">Title *</span>
      <input id="title" type="text" placeholder="Ticket title" />
    </div>
    <div class="field">
      <span class="field-label">Description</span>
      <textarea id="description" placeholder="Description (optional)"></textarea>
    </div>
    <div class="row">
      <div class="field">
        <span class="field-label">Priority</span>
        <select id="priority">
          <option value="">— Default —</option>
          ${priorityOptions}
        </select>
      </div>
      <div class="field">
        <span class="field-label">Story Points</span>
        <input id="story_points" type="number" min="0" value="0" />
      </div>
    </div>
    <div class="row">
      <div class="field">
        <span class="field-label">Project</span>
        <select id="project_id">
          <option value="">— Select Project —</option>
          ${projectOptions}
        </select>
      </div>
      <div class="field">
        <span class="field-label">Sprint</span>
        <select id="sprint">
          <option value="">— No Sprint —</option>
          ${sprintOptions}
        </select>
      </div>
    </div>
    <div class="field">
      <span class="field-label">Assign to</span>
      <select id="assignee">
        <option value="">— Unassigned —</option>
        ${memberOptions}
      </select>
    </div>
    <button class="btn" onclick="submit()">Create</button>
  </div>

  <script>
    const vscode = acquireVsCodeApi();
    function submit() {
      const title = document.getElementById("title").value.trim();
      if (!title) {
        return; // title required
      }
      const payload = { title };
      const desc = document.getElementById("description").value.trim();
      if (desc) payload.description = desc;
      const pri = document.getElementById("priority").value;
      if (pri) payload.priority = pri;
      const sp = Number(document.getElementById("story_points").value);
      if (sp) payload.story_points = sp;
      const projectId = document.getElementById("project_id").value;
      if (projectId) payload.project = projectId;
      const sprint = document.getElementById("sprint").value;
      if (sprint) payload.sprint = sprint;
      const assignee = document.getElementById("assignee").value;
      if (assignee) payload.assignee = assignee;
      vscode.postMessage({ type: "create", payload });
    }
  </script>
</body>
</html>`;
}
