# 9. Limits and roadmap

## 9.1 Known limits

1. Empirical coverage: **four** PDFs. PbtA, FitD, OSR, scans, hostile layouts are unproven.
2. Unknown systems fall through to `generic` mechanics queries.
3. Rubric saturation on several axes.
4. Consistency is name overlap, not PDF-grounded lore.
5. `key_terms` prefers capitalized tokens.
6. `simples` packing can hit the ceiling on a few huge chunks.
7. Image-only/scanned PDFs fail extraction (better than silent generic fantasy; UX still “failed”).
8. No reaper for stuck `processing` ids.
9. `/rag/*` unauthenticated — dev only.
10. Frontend is not the product.

## 9.2 Roadmap (toward “many books, high quality”)

1. Eval matrix on **unseen** books.
2. Faithfulness checks (procedures vs wrong-system tropes).
3. A rubric that **fails** shallow drafts (anti-saturation).
4. Mechanics queries **mined from the index** when preset is generic.
5. Early abort on poor extraction.
6. Human GM read of two campaigns in two systems.

Not next: one giant prompt, a multi-agent crew, or a preset per trendy game.

## 9.3 IP

The service indexes **the user’s** PDF to write new text. Do not redistribute rulebooks. Local eval stays gitignored. Code: MIT. Generated content: `/legal/content-license`.
