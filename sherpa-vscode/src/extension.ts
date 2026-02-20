import * as vscode from "vscode";
import { TicketProvider } from "./ticketProvider";
import { showTicketPanel } from "./ticketPanel";
import { Ticket } from "./tickets";

export function activate(context: vscode.ExtensionContext) {
  const ticketProvider = new TicketProvider();

  vscode.window.registerTreeDataProvider("sherpaTickets", ticketProvider);

  context.subscriptions.push(
    vscode.commands.registerCommand("sherpa.refreshTickets", () => {
      ticketProvider.refresh();
    }),
    vscode.commands.registerCommand("sherpa.openTicket", (ticket: Ticket) => {
      showTicketPanel(ticket, context.extensionUri);
    })
  );
}

export function deactivate() {}
