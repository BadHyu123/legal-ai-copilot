"use client";

import { SessionSummary } from "@/lib/session";

interface Props {
  sessions: SessionSummary[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  className?: string;
}

export default function Sidebar({ sessions, activeId, onSelect, onNew, className }: Props) {
  return (
    <aside className={`sidebar ${className ?? ""}`}>
      <div>
        <div className="wordmark">Trợ lý Pháp lý</div>
        <div className="wordmark-sub">Lao động · Thuế</div>
      </div>

      <button className="new-session-btn" onClick={onNew}>
        + Hội thoại mới
      </button>

      <nav className="session-list">
        {sessions.map((s) => (
          <button
            key={s.id}
            className={`session-item ${s.id === activeId ? "active" : ""}`}
            onClick={() => onSelect(s.id)}
            title={s.title}
          >
            {s.title}
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        Câu trả lời được tạo tự động, chỉ mang tính tham khảo — không thay thế tư vấn pháp lý chuyên môn.
      </div>
    </aside>
  );
}
