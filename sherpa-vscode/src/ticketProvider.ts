import * as vscode from "vscode";
import { Ticket } from "./tickets";

const statusIcons: Record<Ticket["status"], vscode.ThemeIcon> = {
  open: new vscode.ThemeIcon("circle-large-outline"),
  in_progress: new vscode.ThemeIcon("loading~spin"),
  in_review: new vscode.ThemeIcon("eye"),
  done: new vscode.ThemeIcon("check"),
  blocked: new vscode.ThemeIcon("circle-slash"),
};

const priorityLabels: Record<Ticket["priority"], string> = {
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

  refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element: TicketItem): vscode.TreeItem {
    return element;
  }

  async getChildren(): Promise<TicketItem[]> {
    const tickets = await this.fetchTickets();
    return tickets.map((ticket) => new TicketItem(ticket));
  }

  private async fetchTickets(): Promise<Ticket[]> {
    const session = await vscode.authentication.getSession("github", ["user:email"], {
      createIfNone: true,
    });

    if (!session) {
      vscode.window.showWarningMessage("Sherpa: Please sign in with GitHub.");
      return [];
    }

    const config = vscode.workspace.getConfiguration("sherpa");
    const apiUrl = config.get<string>("apiUrl", "http://localhost:8000");

    try {
      const response = await fetch(`${apiUrl}/api/vscode/my-tickets/`, {
        headers: {
          Authorization: `Bearer ${session.accessToken}`,
        },
      });

      if (response.status === 404) {
        vscode.window.showWarningMessage(
          "Sherpa: Your GitHub account is not linked. Ask your admin to add you."
        );
        return [];
      }

      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as { error?: string };
        throw new Error(body.error || `HTTP ${response.status}`);
      }

      const data = (await response.json()) as { tickets?: Ticket[] };
      return data.tickets ?? [];
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
    this.description = priorityLabels[ticket.priority];
    this.tooltip = `${ticket.task_id}: ${ticket.title}\nStatus: ${ticket.status}\nPriority: ${ticket.priority}\nStory Points: ${ticket.story_points}`;
    this.iconPath = statusIcons[ticket.status];
    this.command = {
      command: "sherpa.openTicket",
      title: "Open Ticket",
      arguments: [ticket],
    };
  }
}
