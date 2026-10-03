"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowClockwise, Briefcase, List, Receipt, WarningCircle } from "@phosphor-icons/react";
import Sidebar from "@/components/Sidebar";
import ChatMessage from "@/components/ChatMessage";
import Composer from "@/components/Composer";
import { askQuestion, fetchSessionMessages, Message } from "@/lib/api";
import { createSession, loadSessions, SessionSummary, titleSession } from "@/lib/session";

const SUGGESTIONS = [
  { topic: "Lao động", icon: Briefcase, text: "Thời gian thử việc tối đa là bao lâu?" },
  { topic: "Lao động", icon: Briefcase, text: "Công ty được đơn phương chấm dứt hợp đồng khi nào?" },
  { topic: "Thuế thu nhập cá nhân", icon: Receipt, text: "Mức giảm trừ gia cảnh hiện nay là bao nhiêu?" },
  { topic: "Thuế thu nhập cá nhân", icon: Receipt, text: "Cho thuê nhà thì nộp thuế thu nhập cá nhân thế nào?" },
];

/** Shown while /ask runs (it can take 10-20 s): a skeleton in the shape of
 * an answer plus an honest elapsed-time counter, not a fake progress bar. */
function Pending() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="pending" role="status" aria-live="polite">
      <div className="pending-status">
        Đang tra cứu căn cứ pháp lý và soạn câu trả lời
        <time aria-hidden>{seconds}s</time>
      </div>
      <div className="skeleton" style={{ width: "94%" }} />
      <div className="skeleton" style={{ width: "86%" }} />
      <div className="skeleton" style={{ width: "62%" }} />
    </div>
  );
}

export default function ChatPage() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isAsking, setIsAsking] = useState(false);
  const [failedQuestion, setFailedQuestion] = useState<string | null>(null);
  const [errorText, setErrorText] = useState<string | null>(null);
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
    setErrorText(null);
    setFailedQuestion(null);
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
  }, [messages, isAsking, errorText]);

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

  // `retry` re-asks a question whose user bubble is already on screen.
  const ask = async (text: string, retry = false) => {
    if (!activeId) return;
    setErrorText(null);
    setFailedQuestion(null);

    const isFirstQuestion = messages.length === 0;
    if (!retry) setMessages((prev) => [...prev, { role: "user", content: text }]);
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
      setFailedQuestion(text);
      setErrorText(
        e instanceof Error
          ? `Chưa nhận được câu trả lời (${e.message}). Kiểm tra máy chủ backend đã chạy chưa rồi thử lại.`
          : "Có lỗi không xác định khi gửi câu hỏi. Vui lòng thử lại."
      );
    } finally {
      setIsAsking(false);
    }
  };

  const activeTitle = sessions.find((s) => s.id === activeId)?.title;

  return (
    <div className="app">
      <Sidebar
        sessions={sessions}
        activeId={activeId}
        onSelect={handleSelectSession}
        onNew={handleNewSession}
        onClose={() => setSidebarOpen(false)}
        className={sidebarOpen ? "open" : ""}
      />

      <main className="chat-column">
        <header className="chat-header">
          <button className="icon-btn" onClick={() => setSidebarOpen(true)} aria-label="Mở danh sách hội thoại">
            <List size={22} />
          </button>
          <div className="chat-header-title">
            {messages.length > 0 && activeTitle ? activeTitle : "Trợ lý Pháp lý"}
          </div>
        </header>

        <div className="messages" ref={scrollRef}>
          <div className="messages-inner">
            {messages.length === 0 && !isLoadingHistory && !isAsking && (
              <div className="empty-state">
                <h1>Hỏi về quyền lợi lao động và nghĩa vụ thuế</h1>
                <p>
                  Câu trả lời dựa trên văn bản luật đang có hiệu lực, kèm Điều, Khoản cụ thể để bạn tự đối chiếu.
                </p>
                <div className="suggestion-grid">
                  {SUGGESTIONS.map(({ topic, icon: Icon, text }) => (
                    <button key={text} className="suggestion" onClick={() => ask(text)}>
                      <span className="suggestion-topic">
                        <Icon size={16} weight="duotone" aria-hidden />
                        {topic}
                      </span>
                      <span className="suggestion-text">{text}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, i) => (
              <ChatMessage key={i} message={m} />
            ))}

            {isAsking && <Pending />}

            {errorText && (
              <div className="notice is-error" role="alert">
                <WarningCircle size={20} className="notice-icon" aria-hidden />
                <div>
                  <p>{errorText}</p>
                  {failedQuestion && (
                    <button className="retry-btn" onClick={() => ask(failedQuestion, true)}>
                      <ArrowClockwise size={14} weight="bold" aria-hidden />
                      Thử lại
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        <Composer onSend={(text) => ask(text)} disabled={isAsking || !activeId} />
      </main>
    </div>
  );
}
