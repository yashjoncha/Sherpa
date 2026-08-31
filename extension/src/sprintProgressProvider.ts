import * as vscode from "vscode";

async function getGithubUsername(): Promise<string | undefined> {
  const session = await vscode.authentication.getSession(
    "github",
    ["user:email"],
    { createIfNone: false }
  );
  return session?.account.label;
}

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
    const username = await getGithubUsername();
    const hello = new vscode.TreeItem(
      `Hi ${username ?? "Yash"}`,
      vscode.TreeItemCollapsibleState.None
    );
    hello.iconPath = new vscode.ThemeIcon("account");
    return [hello];
  }
}
