"use client";

import { ArrowSquareOut, CaretDown, Info } from "@phosphor-icons/react";
import { Citation, Message } from "@/lib/api";
import { parseAnswer, parseInline } from "@/lib/answerFormat";

function InlineText({ text }: { text: string }) {
  return (
    <>
      {parseInline(text).map((run, i) =>
        run.kind === "strong" ? (
          <strong key={i}>{run.text}</strong>
        ) : run.kind === "ref" ? (
          <span key={i} className="ref">
            {run.text}
          </span>
        ) : (
          <span key={i}>{run.text}</span>
        )
      )}
    </>
  );
}

function Answer({ text }: { text: string }) {
  return (
    <div className="answer">
      {parseAnswer(text).map((block, i) => {
        if (block.kind === "p") {
          return (
            <p key={i}>
              <InlineText text={block.text} />
            </p>
          );
        }
        const items = block.items.map((item, j) => (
          <li key={j}>
            <InlineText text={item} />
          </li>
        ));
        return block.kind === "ul" ? (
          <ul key={i}>{items}</ul>
        ) : (
          <ol key={i} start={block.start}>
            {items}
          </ol>
        );
      })}
    </div>
  );
}

// "Bộ luật Lao động 2019 (hợp nhất 2026)" -> "Bộ luật Lao động 2019" for the chip;
// the full name stays in the opened panel.
const shortLaw = (luat: string) => luat.replace(/\s*\(.*\)\s*$/, "");

function CitationChip({ c }: { c: Citation }) {
  return (
    <details className="citation">
      <summary>
        <span className="citation-id">
          {c.dieu}
          {c.khoan ? `, ${c.khoan}` : ""}
        </span>
        <span className="citation-law">{shortLaw(c.luat)}</span>
        <CaretDown size={14} className="citation-caret" aria-hidden />
      </summary>
      <div className="citation-panel">
        <div className="citation-panel-head">
          <span>{c.luat}</span>
          {c.source_url && (
            <a className="citation-source" href={c.source_url} target="_blank" rel="noopener noreferrer">
              Văn bản gốc
              <ArrowSquareOut size={14} aria-hidden />
            </a>
          )}
        </div>
        {c.text ? (
          <p className="citation-text">{c.text}</p>
        ) : (
          <p className="citation-text">Mở văn bản gốc để xem nội dung điều khoản này.</p>
        )}
      </div>
    </details>
  );
}

export default function ChatMessage({ message }: { message: Message }) {
  if (message.role === "user") {
    return <div className="msg-user">{message.content}</div>;
  }

  if (message.is_fallback) {
    return (
      <div className="msg-assistant">
        <div className="notice">
          <Info size={20} className="notice-icon" aria-hidden />
          <div>
            <p>{message.content}</p>
            <p className="notice-hint">
              Mẹo: nêu rõ tình huống, ví dụ loại hợp đồng, loại thu nhập hoặc người được hỏi đến.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="msg-assistant">
      <Answer text={message.content} />
      {!!message.citations?.length && (
        <section className="sources" aria-label="Căn cứ pháp lý">
          <p className="sources-label">Căn cứ pháp lý (bấm để xem nguyên văn)</p>
          <div className="citation-list">
            {message.citations.map((c, i) => (
              <CitationChip c={c} key={i} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
