"use client";

import { KeyboardEvent, useRef, useState } from "react";
import { PaperPlaneRight } from "@phosphor-icons/react";

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
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  const autoGrow = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  };

  return (
    <div className="composer">
      <div className="composer-box">
        <label htmlFor="question" className="sr-only">
          Câu hỏi của bạn
        </label>
        <textarea
          id="question"
          ref={textareaRef}
          rows={1}
          placeholder="Hỏi về lao động hoặc thuế..."
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            autoGrow();
          }}
          onKeyDown={handleKeyDown}
        />
        <button className="send-btn" onClick={submit} disabled={disabled || !value.trim()} aria-label="Gửi câu hỏi">
          <PaperPlaneRight size={18} weight="fill" />
        </button>
      </div>
      <p className="composer-hint">Enter để gửi, Shift + Enter để xuống dòng</p>
    </div>
  );
}
