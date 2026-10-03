/**
 * Turns the LLM's plain-text answer into readable blocks: paragraphs,
 * bullet lists and numbered lists, with **bold** and "Điều N" references
 * marked inline. The model writes light markdown; a full markdown library
 * would be overkill for these four shapes.
 */

export type Block =
  | { kind: "p"; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; start: number; items: string[] };

export type Inline = { kind: "text" | "strong" | "ref"; text: string };

const BULLET = /^\s*[-*•]\s+(.*)$/;
// "1. " / "2) " opening a line. "1.000 đồng" never matches: no space after the dot.
const NUMBERED = /^\s*(\d{1,2})[.)]\s+(.*)$/;

export function parseAnswer(text: string): Block[] {
  const blocks: Block[] = [];
  let para: string[] = [];
  const flush = () => {
    if (para.length) blocks.push({ kind: "p", text: para.join(" ") });
    para = [];
  };

  for (const raw of text.replace(/\r/g, "").split("\n")) {
    const line = raw.replace(/^\s*#+\s*/, "").trim();
    if (!line) {
      flush();
      continue;
    }
    const bullet = BULLET.exec(line);
    const numbered = NUMBERED.exec(line);
    const last = blocks[blocks.length - 1];
    if (bullet) {
      flush();
      if (last?.kind === "ul" && !para.length) last.items.push(bullet[1]);
      else blocks.push({ kind: "ul", items: [bullet[1]] });
    } else if (numbered) {
      flush();
      if (last?.kind === "ol") last.items.push(numbered[2]);
      else blocks.push({ kind: "ol", start: Number(numbered[1]), items: [numbered[2]] });
    } else {
      para.push(line);
    }
  }
  flush();
  return blocks;
}

// **bold** and article references ("Điều 25", "Điều 11a") as inline runs.
const INLINE = /\*\*(.+?)\*\*|(Điều\s+\d{1,3}[a-zđ]?)/g;

export function parseInline(text: string): Inline[] {
  const out: Inline[] = [];
  let at = 0;
  for (const m of text.matchAll(INLINE)) {
    if (m.index! > at) out.push({ kind: "text", text: text.slice(at, m.index) });
    out.push(m[1] !== undefined ? { kind: "strong", text: m[1] } : { kind: "ref", text: m[2] });
    at = m.index! + m[0].length;
  }
  if (at < text.length) out.push({ kind: "text", text: text.slice(at) });
  return out;
}
