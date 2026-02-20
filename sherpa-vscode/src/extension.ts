import * as vscode from "vscode";
import { TicketProvider, TicketItem } from "./ticketProvider";
import { showTicketPanel } from "./ticketPanel";
import { showCreateTicketPanel } from "./createTicketPanel";
import { Ticket } from "./tickets";
import { updateTicket, fetchMembers } from "./api";

export function activate(context: vscode.ExtensionContext) {
  const myProvider = new TicketProvider("my");
  const allProvider = new TicketProvider("all");

  vscode.window.registerTreeDataProvider("sherpaMyTickets", myProvider);
  vscode.window.registerTreeDataProvider("sherpaAllTickets", allProvider);

  function refreshAll() {
    myProvider.refresh();
    allProvider.refresh();
  }

  context.subscriptions.push(
    // Refresh
    vscode.commands.registerCommand("sherpa.refreshTickets", () => {
      myProvider.refresh();
    }),
    vscode.commands.registerCommand("sherpa.refreshAllTickets", () => {
      allProvider.refresh();
    }),

    // Open ticket detail
    vscode.commands.registerCommand("sherpa.openTicket", (ticket: Ticket) => {
      showTicketPanel(ticket, context.extensionUri, refreshAll);
    }),

    // Create ticket
    vscode.commands.registerCommand("sherpa.createTicket", () => {
      showCreateTicketPanel(context.extensionUri, refreshAll);
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

    // Quick-pick: Assign ticket
    vscode.commands.registerCommand(
      "sherpa.assignTicket",
      async (item: TicketItem) => {
        try {
          const members = await fetchMembers();
          const picks = members.map((m) => ({
            label: m.display_name,
            description: m.github_username,
            slackId: m.slack_user_id,
          }));

          const picked = await vscode.window.showQuickPick(picks, {
            placeHolder: `Assign ${item.ticket.task_id} to…`,
          });
          if (!picked) return;

          await updateTicket(item.ticket.task_id, {
            assignee: picked.slackId,
          });
          vscode.window.showInformationMessage(
            `${item.ticket.task_id} assigned to ${picked.label}`
          );
          refreshAll();
        } catch (err: any) {
          vscode.window.showErrorMessage(`Sherpa: ${err.message}`);
        }
      }
    )
  );
}

export function deactivate() {}
