"use client";

import { Message } from "@/lib/api";

export default function ChatMessage({ message }: { message: Message }) {
  if (message.role === "user") {
    return <div className="msg-user">{message.content}</div>;
  }

  return (
    <div className={`msg-assistant ${message.is_fallback ? "is-fallback" : ""}`}>
      <div className="msg-assistant-body">{message.content}</div>
      {!!message.citations?.length && (
        <div className="citation-list">
          {message.citations.map((c, i) => (
            <details className="citation" key={i}>
              <summary className="citation-tag">
                {c.dieu}
                {c.khoan ? `, ${c.khoan}` : ""} — {c.luat}
              </summary>
              {c.text && <div className="citation-text">{c.text}</div>}
              {c.source_url && (
                <a className="citation-source" href={c.source_url} target="_blank" rel="noopener noreferrer">
                  Xem văn bản gốc ↗
                </a>
              )}
            </details>
          ))}
        </div>
      )}
    </div>
  );
}
