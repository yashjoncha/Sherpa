import * as vscode from "vscode";
import { fetchSprintProgress } from "./api";

export class SprintProgressProvider
  implements vscode.TreeDataProvider<vscode.TreeItem>
{
  private _onDidChangeTreeData = new vscode.EventEmitter<
    vscode.TreeItem | undefined | void
  >();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
    return element;
  }

  async getChildren(): Promise<vscode.TreeItem[]> {
    try {
      const data = await fetchSprintProgress();

      if (!data.sprint || !data.progress) {
        const item = new vscode.TreeItem(
          "No active sprint",
          vscode.TreeItemCollapsibleState.None
        );
        item.iconPath = new vscode.ThemeIcon("info");
        return [item];
      }

      const { sprint, progress } = data;
      const { percentage, done, total, in_progress, todo, blocked } = progress;

      // Header
      const header = new vscode.TreeItem(
        `Sprint: ${sprint.name}`,
        vscode.TreeItemCollapsibleState.None
      );
      header.description = `${percentage}% (${done}/${total})`;
      header.iconPath = new vscode.ThemeIcon("graph");

      // Progress bar — 16 chars
      const filled = Math.round((percentage / 100) * 16);
      const bar =
        "\u2588".repeat(filled) + "\u2591".repeat(16 - filled);
      const barItem = new vscode.TreeItem(
        bar,
        vscode.TreeItemCollapsibleState.None
      );

      // Breakdown
      const breakdown = new vscode.TreeItem(
        `Done: ${done} \u00b7 In Progress: ${in_progress} \u00b7 Todo: ${todo} \u00b7 Blocked: ${blocked}`,
        vscode.TreeItemCollapsibleState.None
      );
      breakdown.iconPath = new vscode.ThemeIcon("checklist");

      return [header, barItem, breakdown];
    } catch (err: any) {
      const item = new vscode.TreeItem(
        "Failed to load sprint progress",
        vscode.TreeItemCollapsibleState.None
      );
      item.iconPath = new vscode.ThemeIcon("warning");
      return [item];
    }
  }
}
