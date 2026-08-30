# 8. Limits and roadmap

[← Evaluation](07-evaluation.md) · [Index](README.md) · [Next: Glossary →](09-glossary.md)

---

## Known limits

1. **Empirical coverage:** four PDFs in the live matrix. PbtA, FitD, OSR, scans, and hostile layouts are unmeasured.
2. **Book without preset:** falls through to `generic` mechanics queries. Lexical heuristics cover GURPS / 5e / CoC / PF2 / Blood & Honor / Fragged — not an arbitrary indie.
3. **Rubric saturation** on several axes; fine ranking between two good campaigns is weak.
4. **Consistency** is name overlap, not PDF-grounded lore.
5. **`key_terms`** prefers capitalized tokens.
6. **`simples` packing:** a few large chunks can fill the ceiling early.
7. **Scanned / image-only PDFs:** extraction fails or context is empty → job error (better than silent generic fantasy).
8. **`processing` queue:** no reaper; a crash leaves the id stuck.
9. **`/rag/*` without auth** — local development only.

## Roadmap (by impact)

1. Matrix on books **unseen** by the current code.
2. **Faithfulness** checks: index procedures vs wrong-system tropes.
3. A rubric that **fails** shallow drafts (anti-saturation).
4. Mechanics queries **mined from the index** when preset is `generic`.
5. Early abort / clear message on poor extraction.
6. Persist Campaign State next to Markdown for section regeneration.

Not next: one giant prompt, a multi-agent crew, or a preset per trendy game.

## Intellectual property

The service indexes the **request** PDF to write new text. Do not redistribute rulebooks. Local eval stays gitignored. Code license: MIT. Generated content: `GET /legal/content-license`.

---

[← Evaluation](07-evaluation.md) · [Index](README.md) · [Next: Glossary →](09-glossary.md)
