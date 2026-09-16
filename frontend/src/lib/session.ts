/**
 * The backend's SQLite session store is the source of truth for message
 * content (see /sessions/{id}/messages). This module only tracks, per
 * browser, *which* session_ids exist and what to label them in the
 * sidebar — a UI convenience, not authoritative data. Wiping localStorage
 * loses the sidebar list but not the actual conversation history on the
 * backend.
 */

export interface SessionSummary {
  id: string;
  title: string;
  createdAt: string;
}

const STORAGE_KEY = "legal-copilot:sessions";

export function loadSessions(): SessionSummary[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as SessionSummary[]) : [];
  } catch {
    return [];
  }
}

function saveSessions(sessions: SessionSummary[]): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
}

export function createSession(): SessionSummary {
  const session: SessionSummary = {
    id: crypto.randomUUID(),
    title: "Hội thoại mới",
    createdAt: new Date().toISOString(),
  };
  const sessions = [session, ...loadSessions()];
  saveSessions(sessions);
  return session;
}

/** Called once the first question in a session is known, so the sidebar
 * shows something meaningful instead of "Hội thoại mới" for every entry.
 */
export function titleSession(sessionId: string, firstQuestion: string): void {
  const sessions = loadSessions().map((s) =>
    s.id === sessionId && s.title === "Hội thoại mới"
      ? { ...s, title: firstQuestion.slice(0, 60) }
      : s
  );
  saveSessions(sessions);
}

export function deleteSession(sessionId: string): void {
  saveSessions(loadSessions().filter((s) => s.id !== sessionId));
}
