import * as vscode from "vscode";
import { Project } from "./tickets";

export interface WorkspaceInfo {
  repoName: string | undefined;
  branch: string | undefined;
  folderName: string | undefined;
}

/**
 * Detect the current workspace's git repo name and branch.
 * Waits for the Git extension to activate if needed.
 * Falls back to the workspace folder name if git info is unavailable.
 */
export async function detectWorkspace(): Promise<WorkspaceInfo> {
  const folderName = vscode.workspace.workspaceFolders?.[0]?.name;

  const gitExt = vscode.extensions.getExtension<GitExtension>("vscode.git");
  if (!gitExt) {
    return { repoName: folderName, branch: undefined, folderName };
  }

  // Wait for the git extension to activate if it hasn't yet
  if (!gitExt.isActive) {
    try {
      await gitExt.activate();
    } catch {
      return { repoName: folderName, branch: undefined, folderName };
    }
  }

  const git = gitExt.exports.getAPI(1);

  // Git extension is active but repos may not be loaded yet — wait briefly
  if (git.repositories.length === 0) {
    await new Promise<void>((resolve) => {
      const disposable = git.onDidOpenRepository(() => {
        disposable.dispose();
        resolve();
      });
      // Don't wait forever — 3 second timeout
      setTimeout(() => {
        disposable.dispose();
        resolve();
      }, 3000);
    });
  }

  const repo = git.repositories[0];
  if (!repo) {
    return { repoName: folderName, branch: undefined, folderName };
  }

  const branch = repo.state.HEAD?.name;
  const remote = repo.state.remotes.find((r: GitRemote) => r.name === "origin");
  const remoteUrl = remote?.fetchUrl || remote?.pushUrl;

  const repoName = repo.rootUri.path.split("/").pop() || folderName;
  return { repoName, branch, folderName };
}

/**
 * Extract the repository name from a git remote URL.
 * Supports both SSH (git@...) and HTTPS formats.
 */
export function extractRepoName(url: string): string {
  // Remove trailing .git
  const cleaned = url.replace(/\.git$/, "");
  // SSH: git@github.com:org/repo
  const sshMatch = cleaned.match(/[:\/]([^/:]+\/[^/:]+)$/);
  if (sshMatch) {
    return sshMatch[1].split("/").pop()!;
  }
  // HTTPS: https://github.com/org/repo
  const parts = cleaned.split("/");
  return parts[parts.length - 1] || cleaned;
}

/**
 * Match a repo name against the list of projects using 3-tier matching:
 * 1. Exact match (case-insensitive)
 * 2. Prefix match (project name starts with repo name or vice-versa)
 * 3. Substring match (one contains the other)
 */
export function matchProject(
  repoName: string,
  projects: Project[]
): Project | undefined {
  if (!repoName || projects.length === 0) {
    return undefined;
  }

  const lower = repoName.toLowerCase();

  // Tier 1: exact match
  const exact = projects.find((p) => p.name.toLowerCase() === lower);
  if (exact) {
    return exact;
  }

  // Tier 2: prefix match
  const prefix = projects.find((p) => {
    const pLower = p.name.toLowerCase();
    return pLower.startsWith(lower) || lower.startsWith(pLower);
  });
  if (prefix) {
    return prefix;
  }

  // Tier 3: substring match
  const substring = projects.find((p) => {
    const pLower = p.name.toLowerCase();
    return pLower.includes(lower) || lower.includes(pLower);
  });
  return substring;
}

// Minimal type definitions for the VS Code Git extension API
interface GitExtension {
  getAPI(version: 1): GitAPI;
}

interface GitAPI {
  repositories: GitRepository[];
  onDidOpenRepository: (cb: () => void) => { dispose(): void };
}

interface GitRepository {
  rootUri: { path: string };
  state: {
    HEAD: { name?: string } | undefined;
    remotes: GitRemote[];
  };
}

interface GitRemote {
  name: string;
  fetchUrl?: string;
  pushUrl?: string;
}
