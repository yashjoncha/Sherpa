import * as vscode from "vscode";
import { Ticket, Member, Sprint, CreateTicketPayload } from "./tickets";

async function getSession(): Promise<vscode.AuthenticationSession | undefined> {
  return vscode.authentication.getSession("github", ["user:email"], {
    createIfNone: true,
  });
}

function getBaseUrl(): string {
  const config = vscode.workspace.getConfiguration("sherpa");
  return config.get<string>("apiUrl", "http://localhost:8000");
}

async function apiFetch(
  path: string,
  options: { method?: string; body?: unknown } = {}
): Promise<any> {
  const session = await getSession();
  if (!session) {
    throw new Error("Please sign in with GitHub.");
  }

  const url = `${getBaseUrl()}/api${path}`;
  const init: RequestInit = {
    method: options.method || "GET",
    headers: {
      Authorization: `Bearer ${session.accessToken}`,
      "Content-Type": "application/json",
    },
  };
  if (options.body !== undefined) {
    init.body = JSON.stringify(options.body);
  }

  const response = await fetch(url, init);

  if (response.status === 404) {
    const body = (await response.json().catch(() => ({}))) as { error?: string };
    throw new Error(
      body.error || "Your GitHub account is not linked. Ask your admin to add you."
    );
  }

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { error?: string };
    throw new Error(body.error || `HTTP ${response.status}`);
  }

  return response.json();
}

// ── Tickets ──────────────────────────────────────────────────────────────

export async function fetchMyTickets(): Promise<Ticket[]> {
  const data = await apiFetch("/vscode/my-tickets/");
  return data.tickets ?? [];
}

export async function fetchAllTickets(): Promise<Ticket[]> {
  const data = await apiFetch("/vscode/tickets/");
  return data.tickets ?? [];
}

export async function fetchTicketDetail(ticketId: string): Promise<Ticket> {
  const data = await apiFetch(`/vscode/tickets/${ticketId}/`);
  return data.ticket;
}

export async function updateTicket(
  ticketId: string,
  fields: Record<string, unknown>
): Promise<Ticket> {
  const data = await apiFetch(`/vscode/tickets/${ticketId}/`, {
    method: "PUT",
    body: fields,
  });
  return data.ticket;
}

export async function createTicket(payload: CreateTicketPayload): Promise<Ticket> {
  const data = await apiFetch("/vscode/tickets/create/", {
    method: "POST",
    body: payload,
  });
  return data.ticket;
}

// ── Members & Sprints ────────────────────────────────────────────────────

export async function fetchMembers(): Promise<Member[]> {
  const data = await apiFetch("/vscode/members/");
  return data.members ?? [];
}

export async function fetchSprints(): Promise<Sprint[]> {
  const data = await apiFetch("/vscode/sprints/");
  return data.sprints ?? [];
}
