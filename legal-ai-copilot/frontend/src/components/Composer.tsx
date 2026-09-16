"use client";

import { KeyboardEvent, useRef, useState } from "react";

interface Props {
  onSend: (text: string) => void;
  disabled: boolean;
}

export default function Composer({ onSend, disabled }: Props) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const autoGrow = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  };

  return (
    <div className="composer">
      <div className="composer-inner">
        <textarea
          ref={textareaRef}
          rows={1}
          placeholder="Nhập câu hỏi về Luật Lao động hoặc Luật Thuế..."
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            autoGrow();
          }}
          onKeyDown={handleKeyDown}
        />
        <button className="send-btn" onClick={submit} disabled={disabled || !value.trim()}>
          Gửi
        </button>
      </div>
      <div className="composer-note">Enter để gửi · Shift+Enter để xuống dòng</div>
    </div>
  );
}
