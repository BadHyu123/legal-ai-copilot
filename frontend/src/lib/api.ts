const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export interface Citation {
  luat: string;
  dieu: string;
  khoan: string | null;
  text?: string;
  source_url?: string | null;
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

export type Verdict = "trai_luat" | "can_luu_y" | "phu_hop" | "khong_doi_chieu";

export interface ReviewItem {
  clause: string;
  verdict: Verdict;
  reason: string;
  citations: Citation[];
}

/** POST /review streams NDJSON: {"total": N, "skipped": M} first (M clauses
 * past the server's cap are not reviewed), then one ReviewItem per clause
 * as it is reviewed (~8 s each), in document order. */
export async function reviewContract(
  input: { file?: File; text?: string },
  onTotal: (total: number, skipped: number) => void,
  onItem: (item: ReviewItem) => void
): Promise<void> {
  const form = new FormData();
  if (input.file) form.append("file", input.file);
  else form.append("text", input.text ?? "");

  // Every thrown message is a Vietnamese sentence the UI shows as is.
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/review`, { method: "POST", body: form });
  } catch {
    throw new Error("không kết nối được máy chủ backend. Kiểm tra máy chủ đã chạy chưa rồi thử lại.");
  }
  if (!res.ok || !res.body) {
    // Our 413/422 carry a message meant for the user; FastAPI's own
    // validation errors carry a list, which isn't.
    const detail = await res.json().then(
      (j) => (typeof j.detail === "string" ? j.detail : null),
      () => null
    );
    throw new Error(detail ?? `máy chủ trả về lỗi ${res.status}. Vui lòng thử lại.`);
  }

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  let total: number | null = null;
  let received = 0;
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value;
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.trim()) continue;
        const data = JSON.parse(line);
        if ("total" in data) {
          total = data.total;
          onTotal(data.total, data.skipped ?? 0);
        } else {
          received += 1;
          onItem(data);
        }
      }
    }
  } catch {
    // A dropped connection or a cut-off line: reported by the check below.
  }
  // A server error mid-stream can also end the response cleanly from the
  // browser's side; don't let a partial review pass for a complete one.
  if (total === null || received < total) {
    throw new Error(`kết nối bị ngắt sau ${received}/${total ?? "?"} điều khoản. Vui lòng thử lại.`);
  }
}
