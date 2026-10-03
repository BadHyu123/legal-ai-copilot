"use client";

import { Plus, Scales, X } from "@phosphor-icons/react";
import { SessionSummary } from "@/lib/session";

interface Props {
  sessions: SessionSummary[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onClose: () => void;
  className?: string;
}

export default function Sidebar({ sessions, activeId, onSelect, onNew, onClose, className }: Props) {
  return (
    <aside className={`sidebar ${className ?? ""}`}>
      <div className="brand">
        <span className="brand-mark" aria-hidden>
          <Scales size={22} weight="duotone" />
        </span>
        <div>
          <div className="brand-name">Trợ lý Pháp lý</div>
          <div className="brand-scope">Luật Lao động và Luật Thuế</div>
        </div>
        <button className="icon-btn sidebar-close" onClick={onClose} aria-label="Đóng danh sách hội thoại">
          <X size={20} />
        </button>
      </div>

      <button className="new-session-btn" onClick={onNew}>
        <Plus size={16} weight="bold" />
        Hội thoại mới
      </button>

      {sessions.length > 0 && <p className="session-heading">Gần đây</p>}
      <nav className="session-list" aria-label="Các hội thoại">
        {sessions.map((s) => (
          <button
            key={s.id}
            className={`session-item ${s.id === activeId ? "active" : ""}`}
            onClick={() => onSelect(s.id)}
            aria-current={s.id === activeId ? "page" : undefined}
            title={s.title}
          >
            {s.title}
          </button>
        ))}
      </nav>

      <p className="disclaimer">
        Câu trả lời được tạo tự động và chỉ để tham khảo. Với việc quan trọng, hãy đối chiếu văn bản gốc
        hoặc hỏi luật sư.
      </p>
    </aside>
  );
}
