const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export interface Citation {
  luat: string;
  dieu: string;
  khoan: string | null;
}

export interface AskResponse {
  answer: string;
  citations: Citation[];
  is_fallback: boolean;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  is_fallback?: boolean;
}

export async function askQuestion(sessionId: string, question: string): Promise<AskResponse> {
  const res = await fetch(`${API_BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, question }),
  });
  if (!res.ok) {
    throw new Error(`Backend trả về lỗi ${res.status}`);
  }
  return res.json();
}

export async function fetchSessionMessages(sessionId: string): Promise<Message[]> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/messages`);
  if (!res.ok) {
    throw new Error(`Không tải được lịch sử hội thoại (${res.status})`);
  }
  return res.json();
}
