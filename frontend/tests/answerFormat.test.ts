// Self-check for the answer formatter. Run: node tests/answerFormat.test.ts (Node >= 23.6)
import assert from "node:assert/strict";
import { parseAnswer, parseInline } from "../src/lib/answerFormat.ts";

const answer = `Theo **Điều 25**, thời gian thử việc tối đa:

1. Không quá 180 ngày với người quản lý.
2. Không quá 60 ngày với trình độ cao đẳng.
- Mức phạt 1.000.000 đồng là ví dụ.
- Ý thứ hai
1.000 đồng không phải danh sách.`;

assert.deepEqual(parseAnswer(answer), [
  { kind: "p", text: "Theo **Điều 25**, thời gian thử việc tối đa:" },
  { kind: "ol", start: 1, items: ["Không quá 180 ngày với người quản lý.", "Không quá 60 ngày với trình độ cao đẳng."] },
  { kind: "ul", items: ["Mức phạt 1.000.000 đồng là ví dụ.", "Ý thứ hai"] },
  { kind: "p", text: "1.000 đồng không phải danh sách." },
]);

assert.deepEqual(parseInline("Theo **Điều 25**, xem Điều 11a và khoản 2."), [
  { kind: "text", text: "Theo " },
  { kind: "strong", text: "Điều 25" },
  { kind: "text", text: ", xem " },
  { kind: "ref", text: "Điều 11a" },
  { kind: "text", text: " và khoản 2." },
]);

console.log("answerFormat OK");
