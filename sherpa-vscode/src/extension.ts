import * as vscode from "vscode";
import { TicketProvider, TicketItem } from "./ticketProvider";
import { SprintProgressProvider } from "./sprintProgressProvider";
import { showTicketPanel } from "./ticketPanel";
import { showCreateTicketPanel } from "./createTicketPanel";
import { Ticket, Project } from "./tickets";
import { updateTicket, fetchProjects, fetchAIProjectMatch } from "./api";
import { detectWorkspace, matchProject } from "./workspace";

export function activate(context: vscode.ExtensionContext) {
  const myProvider = new TicketProvider();
  const sprintProgressProvider = new SprintProgressProvider();

  vscode.window.registerTreeDataProvider("sherpaMyTickets", myProvider);
  vscode.window.registerTreeDataProvider("sherpaSprintProgress", sprintProgressProvider);

  function refreshAll() {
    myProvider.refresh();
    sprintProgressProvider.refresh();
  }

  // Auto-detect workspace project on activation
  let cachedProjects: Project[] = [];
  const log = vscode.window.createOutputChannel("Sherpa");

  async function autoDetectAndFilter() {
    log.appendLine("Sherpa: starting workspace detection...");
    try {
      const ws = await detectWorkspace();
      log.appendLine(`Workspace — repo: "${ws.repoName}", folder: "${ws.folderName}", branch: "${ws.branch}"`);

      cachedProjects = await fetchProjects();
      log.appendLine(`Fetched ${cachedProjects.length} projects: ${cachedProjects.map((p) => p.name).join(", ")}`);

      if (ws.repoName) {
        const matched = matchProject(ws.repoName, cachedProjects);
        if (matched) {
          log.appendLine(`Matched project: "${matched.name}"`);
          myProvider.setProjectFilter(matched.name);

        } else {
          // Tier 4: AI-powered matching
          const projectNames = cachedProjects.map((p) => p.name);
          const aiMatch = await fetchAIProjectMatch(ws.repoName, projectNames);
          if (aiMatch) {
            log.appendLine(`AI match → "${aiMatch}"`);
            myProvider.setProjectFilter(aiMatch);

          } else {
            log.appendLine(`No project matched for repo "${ws.repoName}" (string + AI)`);
          }
        }
      }
    } catch (err: any) {
      log.appendLine(`autoDetectAndFilter error: ${err.message}`);
    }
  }

  autoDetectAndFilter();

  // Re-detect when workspace folders change
  context.subscriptions.push(
    vscode.workspace.onDidChangeWorkspaceFolders(() => {
      autoDetectAndFilter();
    })
  );

  context.subscriptions.push(
    // Refresh
    vscode.commands.registerCommand("sherpa.refreshTickets", () => {
      myProvider.refresh();
    }),
    vscode.commands.registerCommand("sherpa.refreshSprintProgress", () => {
      sprintProgressProvider.refresh();
    }),
    // Open ticket detail
    vscode.commands.registerCommand("sherpa.openTicket", (ticket: Ticket) => {
      showTicketPanel(ticket, context.extensionUri, refreshAll);
    }),

    // Create ticket
    vscode.commands.registerCommand("sherpa.createTicket", () => {
      showCreateTicketPanel(context.extensionUri, refreshAll);
    }),

    // Filter by project
    vscode.commands.registerCommand("sherpa.filterByProject", async () => {
      try {
        if (cachedProjects.length === 0) {
          cachedProjects = await fetchProjects();
        }

        const items: vscode.QuickPickItem[] = [
          { label: "$(clear-all) Show All", description: "Remove project filter" },
          ...cachedProjects.map((p) => ({
            label: p.name,
            description: myProvider.getProjectFilter() === p.name ? "(active)" : "",
          })),
        ];

        const picked = await vscode.window.showQuickPick(items, {
          placeHolder: "Filter tickets by project",
        });

        if (!picked) {
          return;
        }

        if (picked.label.includes("Show All")) {
          myProvider.setProjectFilter(undefined);
        } else {
          myProvider.setProjectFilter(picked.label);
        }
      } catch (err: any) {
        vscode.window.showErrorMessage(`Sherpa: ${err.message}`);
      }
    }),

    // Quick-pick: Change status
    vscode.commands.registerCommand(
      "sherpa.updateTicketStatus",
      async (item: TicketItem) => {
        const statuses = [
          "open",
          "planning",
          "todo",
          "in_progress",
          "in_review",
          "done",
          "blocked",
        ];
        const picked = await vscode.window.showQuickPick(statuses, {
          placeHolder: `Change status of ${item.ticket.task_id} (current: ${item.ticket.status})`,
        });
        if (!picked) return;

        try {
          await updateTicket(item.ticket.task_id, { status: picked });
          vscode.window.showInformationMessage(
            `${item.ticket.task_id} status → ${picked}`
          );
          refreshAll();
        } catch (err: any) {
          vscode.window.showErrorMessage(`Sherpa: ${err.message}`);
        }
      }
    ),

  );
}

export function deactivate() {}
