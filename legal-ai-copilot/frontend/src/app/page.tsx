"use client";

import { useEffect, useRef, useState } from "react";
import Sidebar from "@/components/Sidebar";
import ChatMessage from "@/components/ChatMessage";
import Composer from "@/components/Composer";
import { askQuestion, fetchSessionMessages, Message } from "@/lib/api";
import { createSession, loadSessions, SessionSummary, titleSession } from "@/lib/session";

const SUGGESTIONS = [
  "Người sử dụng lao động được đơn phương chấm dứt hợp đồng trong trường hợp nào?",
  "Thời gian nghỉ thai sản theo quy định hiện hành là bao lâu?",
  "Thu nhập nào được miễn thuế thu nhập cá nhân?",
];

export default function ChatPage() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isAsking, setIsAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Load the session index on mount; start a fresh session if the
  // browser has never talked to this app before.
  useEffect(() => {
    const existing = loadSessions();
    if (existing.length > 0) {
      setSessions(existing);
      setActiveId(existing[0].id);
    } else {
      const fresh = createSession();
      setSessions([fresh]);
      setActiveId(fresh.id);
    }
  }, []);

  // Load message history whenever the active session changes.
  useEffect(() => {
    if (!activeId) return;
    setMessages([]);
    setError(null);
    setIsLoadingHistory(true);
    fetchSessionMessages(activeId)
      .then(setMessages)
      .catch(() => {
        // A brand-new session_id has no history yet on the backend —
        // that's expected, not an error worth surfacing.
      })
      .finally(() => setIsLoadingHistory(false));
  }, [activeId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isAsking]);

  const handleNewSession = () => {
    const fresh = createSession();
    setSessions((prev) => [fresh, ...prev]);
    setActiveId(fresh.id);
    setSidebarOpen(false);
  };

  const handleSelectSession = (id: string) => {
    setActiveId(id);
    setSidebarOpen(false);
  };

  const handleSend = async (text: string) => {
    if (!activeId) return;
    setError(null);

    const isFirstQuestion = messages.length === 0;
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setIsAsking(true);

    try {
      const res = await askQuestion(activeId, text);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.answer, citations: res.citations, is_fallback: res.is_fallback },
      ]);
      if (isFirstQuestion) {
        titleSession(activeId, text);
        setSessions(loadSessions());
      }
    } catch (e) {
      setError(
        e instanceof Error
          ? `Không nhận được phản hồi: ${e.message}. Kiểm tra backend đã chạy chưa (docker-compose up backend).`
          : "Có lỗi không xác định khi gửi câu hỏi."
      );
    } finally {
      setIsAsking(false);
    }
  };

  return (
    <div className="app">
      <Sidebar
        sessions={sessions}
        activeId={activeId}
        onSelect={handleSelectSession}
        onNew={handleNewSession}
        className={sidebarOpen ? "open" : ""}
      />

      <div className="chat-column">
        <header className="chat-header">
          <button className="menu-btn" onClick={() => setSidebarOpen((v) => !v)} aria-label="Mở danh sách hội thoại">
            ☰
          </button>
          <div>
            <div className="chat-header-title">Trợ lý Pháp lý</div>
            <div className="chat-header-scope">Phạm vi hiện tại: Bộ luật Lao động · Luật Thuế</div>
          </div>
        </header>

        <div className="messages" ref={scrollRef}>
          <div className="messages-inner">
            {messages.length === 0 && !isLoadingHistory && (
              <div className="empty-state">
                <h1>Hỏi về Luật Lao động hay Luật Thuế</h1>
                <p>Mọi câu trả lời đều kèm trích dẫn Điều, Khoản cụ thể để bạn tự đối chiếu.</p>
                <div className="suggestion-list">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} className="suggestion-btn" onClick={() => handleSend(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, i) => (
              <ChatMessage key={i} message={m} />
            ))}

            {isAsking && (
              <div className="thinking" aria-label="Đang tìm căn cứ pháp lý">
                <span />
                <span />
                <span />
              </div>
            )}

            {error && <div className="error-note">{error}</div>}
          </div>
        </div>

        <Composer onSend={handleSend} disabled={isAsking || !activeId} />
      </div>
    </div>
  );
}
