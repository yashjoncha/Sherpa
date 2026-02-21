import * as vscode from "vscode";
import { Ticket } from "./tickets";
import { fetchMyTickets, fetchAllTickets } from "./api";

const statusIcons: Record<string, vscode.ThemeIcon> = {
  open: new vscode.ThemeIcon("circle-large-outline"),
  planning: new vscode.ThemeIcon("note"),
  todo: new vscode.ThemeIcon("circle-outline"),
  in_progress: new vscode.ThemeIcon("loading~spin"),
  in_review: new vscode.ThemeIcon("eye"),
  done: new vscode.ThemeIcon("check"),
  blocked: new vscode.ThemeIcon("circle-slash"),
};

const priorityLabels: Record<string, string> = {
  critical: "\u{1F534} Critical",
  high: "\u{1F7E0} High",
  medium: "\u{1F7E1} Medium",
  low: "\u{1F7E2} Low",
};

export class TicketProvider implements vscode.TreeDataProvider<TicketItem> {
  private _onDidChangeTreeData = new vscode.EventEmitter<
    TicketItem | undefined | void
  >();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private _projectFilter: string | undefined;

  constructor(private mode: "my" | "all") {}

  setProjectFilter(project: string | undefined): void {
    this._projectFilter = project;
    this._onDidChangeTreeData.fire();
  }

  getProjectFilter(): string | undefined {
    return this._projectFilter;
  }

  refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element: TicketItem): vscode.TreeItem {
    return element;
  }

  async getChildren(): Promise<TicketItem[]> {
    try {
      const tickets =
        this.mode === "my"
          ? await fetchMyTickets(this._projectFilter)
          : await fetchAllTickets(this._projectFilter);
      return tickets.map((t) => new TicketItem(t));
    } catch (err: any) {
      vscode.window.showErrorMessage(`Sherpa: ${err.message}`);
      return [];
    }
  }
}

export class TicketItem extends vscode.TreeItem {
  public readonly ticket: Ticket;

  constructor(ticket: Ticket) {
    super(
      `${ticket.task_id}: ${ticket.title}`,
      vscode.TreeItemCollapsibleState.None
    );
    this.ticket = ticket;
    this.contextValue = "ticket";
    this.description = priorityLabels[ticket.priority] ?? ticket.priority;
    this.tooltip = `${ticket.task_id}: ${ticket.title}\nStatus: ${ticket.status}\nPriority: ${ticket.priority}\nStory Points: ${ticket.story_points}`;
    this.iconPath = statusIcons[ticket.status] ?? statusIcons.open;
    this.command = {
      command: "sherpa.openTicket",
      title: "Open Ticket",
      arguments: [ticket],
    };
  }
}
