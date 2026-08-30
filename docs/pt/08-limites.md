# 8. Limites e roadmap

[← Avaliação](07-avaliacao.md) · [Índice](README.md) · [Seguinte: Glossário →](09-glossario.md)

---

## Limites conhecidos

1. **Cobertura empírica:** 4 PDFs na matriz ao vivo. PbtA, FitD, OSR, scans e layouts hostis não estão medidos.
2. **Livro sem preset:** cai em `generic` + query de mecânica genérica. A heurística lexical cobre GURPS / 5e / CoC / PF2 / Blood & Honor / Fragged — não um indie arbitrário.
3. **Rubrica satura** em vários eixos; ranking fino entre duas campanhas boas é fraco.
4. **Consistência** mede overlap de nomes, não lore contra o PDF.
5. **`key_terms`** enviesado a tokens capitalizados.
6. **Packing `simples`:** poucos chunks grandes podem encher o teto cedo.
7. **PDF scan / só imagem:** extração falha ou contexto vazio → erro de job (melhor que fantasia genérica silenciosa).
8. **Fila `processing`:** sem reaper; crash deixa id preso.
9. **`/rag/*` sem auth** — só para desenvolvimento local.

## Roadmap (por impacto)

1. Matriz em livros **não vistos** pelo código atual.
2. Cheque de **fidelidade**: procedimentos do índice vs tropes do sistema errado.
3. Rubrica que **reprove** texto raso (anti-saturação).
4. Query de mecânica **derivada do índice** quando o preset é `generic`.
5. Abortar cedo / mensagem clara em extração pobre.
6. Persistência do Campaign State junto do Markdown para regenerar secções.

Não é o próximo passo: um prompt único gigante, multi-agente, ou um preset por jogo da moda.

## Propriedade intelectual

O serviço indexa o PDF **do pedido** para gerar texto novo. Não redistribuir o livro. Eval local permanece gitignored. Licença do código: MIT. Conteúdo gerado: `GET /legal/content-license`.

---

[← Avaliação](07-avaliacao.md) · [Índice](README.md) · [Seguinte: Glossário →](09-glossario.md)
