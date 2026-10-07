"use client";

import { ChangeEvent, useEffect, useState } from "react";
import { CheckCircle, FileArrowUp, Info, MagnifyingGlass, Prohibit, Question, WarningCircle, X } from "@phosphor-icons/react";
import { CitationChip } from "@/components/ChatMessage";
import { reviewContract, ReviewItem, Verdict } from "@/lib/api";

const VERDICT_LABEL: Record<Verdict, string> = {
  trai_luat: "Có thể trái luật",
  can_luu_y: "Cần lưu ý",
  phu_hop: "Không phát hiện vấn đề",
  khong_doi_chieu: "Không có căn cứ để đối chiếu",
};

const VERDICT_ICON = {
  trai_luat: Prohibit,
  can_luu_y: WarningCircle,
  phu_hop: CheckCircle,
  khong_doi_chieu: Question,
};

const isFlagged = (v: Verdict) => v === "trai_luat" || v === "can_luu_y";

function Elapsed() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, []);
  return <time aria-hidden>{seconds}s</time>;
}

function FlaggedClause({ item }: { item: ReviewItem }) {
  const Icon = VERDICT_ICON[item.verdict];
  return (
    <article className={`review-item is-${item.verdict}`}>
      <p className="review-verdict">
        <Icon size={18} weight="fill" aria-hidden />
        {VERDICT_LABEL[item.verdict]}
      </p>
      <blockquote className="review-clause">{item.clause}</blockquote>
      {item.reason && <p className="review-reason">{item.reason}</p>}
      {item.citations.length > 0 && (
        <div className="citation-list" aria-label="Căn cứ pháp lý">
          {item.citations.map((c, i) => (
            <CitationChip c={c} key={i} />
          ))}
        </div>
      )}
    </article>
  );
}

export default function ContractReview({ hidden }: { hidden: boolean }) {
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [skipped, setSkipped] = useState(0);
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [running, setRunning] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);

  const start = async () => {
    setItems([]);
    setTotal(null);
    setSkipped(0);
    setErrorText(null);
    setRunning(true);
    try {
      await reviewContract(
        file ? { file } : { text },
        (n, skippedCount) => {
          setTotal(n);
          setSkipped(skippedCount);
        },
        (item) => setItems((prev) => [...prev, item])
      );
    } catch (e) {
      setErrorText(
        `Chưa rà soát xong: ${e instanceof Error ? e.message : "lỗi không xác định. Vui lòng thử lại."}`
      );
    } finally {
      setRunning(false);
    }
  };

  const onPick = (e: ChangeEvent<HTMLInputElement>) => {
    setFile(e.target.files?.[0] ?? null);
    e.target.value = ""; // picking the same file again still fires onChange
  };

  const flagged = items.filter((i) => isFlagged(i.verdict));
  const rest = items.filter((i) => !isFlagged(i.verdict));
  const count = (v: Verdict) => items.filter((i) => i.verdict === v).length;

  return (
    <div className="messages" hidden={hidden}>
      <div className="messages-inner">
        <div className="review-intro">
          <h1>Rà soát hợp đồng</h1>
          <p>
            Từng điều khoản được đối chiếu với Bộ luật Lao động, các luật thuế và nghị định hướng dẫn. Những điều khoản có thể trái luật
            hoặc cần lưu ý được nêu kèm Điều, Khoản làm căn cứ.
          </p>
        </div>

        <div className="review-input">
          <label htmlFor="contract" className="sr-only">
            Nội dung hợp đồng
          </label>
          <textarea
            id="contract"
            rows={8}
            placeholder={file ? "Đang dùng nội dung từ tệp đã chọn." : "Dán nội dung hợp đồng vào đây..."}
            value={text}
            disabled={!!file}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="review-actions">
            <label className="file-btn">
              <FileArrowUp size={18} aria-hidden />
              <span className="file-name">{file ? file.name : "Hoặc chọn tệp PDF, Word"}</span>
              <input type="file" accept=".pdf,.docx,.txt" className="sr-only" onChange={onPick} />
            </label>
            {file && (
              <button className="clear-file-btn" onClick={() => setFile(null)} aria-label="Bỏ tệp đã chọn">
                <X size={18} />
              </button>
            )}
            <button className="primary-btn" onClick={start} disabled={running || (!file && !text.trim())}>
              <MagnifyingGlass size={18} weight="bold" aria-hidden />
              Rà soát
            </button>
          </div>
          <p className="composer-hint">Hợp đồng chỉ được xử lý trên máy chủ chạy tại máy này, không gửi ra ngoài.</p>
        </div>

        {running && (
          <div className="pending-status" role="status" aria-live="polite">
            {total === null
              ? "Đang đọc và tách điều khoản"
              : `Đã rà soát ${items.length}/${total} điều khoản`}
            <Elapsed />
          </div>
        )}
        {running && total !== null && (
          <div className="review-progress" aria-hidden>
            <div style={{ width: `${(items.length / Math.max(total, 1)) * 100}%` }} />
          </div>
        )}

        {errorText && (
          <div className="notice is-error" role="alert">
            <WarningCircle size={20} className="notice-icon" aria-hidden />
            <p>{errorText}</p>
          </div>
        )}

        {skipped > 0 && (
          <div className="notice">
            <Info size={20} className="notice-icon" aria-hidden />
            <p>
              Hợp đồng dài nên chỉ {total} điều khoản đầu được rà soát; {skipped} điều khoản sau chưa được rà soát. Hãy
              dán riêng phần còn lại để rà soát tiếp.
            </p>
          </div>
        )}

        {items.length > 0 && (
          <p className="review-summary">
            {count("trai_luat")} có thể trái luật · {count("can_luu_y")} cần lưu ý · {rest.length} không phát hiện
            vấn đề
          </p>
        )}

        {flagged.map((item, i) => (
          <FlaggedClause item={item} key={i} />
        ))}

        {!running && items.length > 0 && flagged.length === 0 && (
          <div className="notice">
            <CheckCircle size={20} className="notice-icon" aria-hidden />
            <p>Không phát hiện điều khoản trái luật hay cần lưu ý trong phạm vi các văn bản đang có.</p>
          </div>
        )}

        {rest.length > 0 && (
          <details className="review-rest">
            <summary>Xem {rest.length} điều khoản không phát hiện vấn đề</summary>
            {rest.map((item, i) => (
              <div className="review-rest-item" key={i}>
                <span className="review-rest-label">{VERDICT_LABEL[item.verdict]}</span>
                <p>{item.clause}</p>
              </div>
            ))}
          </details>
        )}
      </div>
    </div>
  );
}
