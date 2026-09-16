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
            <span className="citation-tag" key={i}>
              {c.dieu}
              {c.khoan ? `, ${c.khoan}` : ""} — {c.luat}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
