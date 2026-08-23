# 9. Limites e roadmap

## 9.1 Limites atuais (intencionais ou conhecidos)

1. **Cobertura empírica:** 4 PDFs. PbtA, FitD, OSR, scans, manuais de 400 p. mal extraídos não estão na matriz.
2. **Livro sem preset:** cai em `generic` + query de mecânica genérica. Deteção lexical ajuda GURPS/5e/CoC/PF2/Blood/Fragged, não um indie arbitrário.
3. **Rubrica satura** em vários eixos; ranking fino entre duas campanhas boas é fraco.
4. **Consistência** mede overlap de nomes, não lore contra o PDF.
5. **`key_terms`** enviesado a tokens capitalizados.
6. **Packing `simples`:** poucos chunks grandes podem encher o teto cedo.
7. **PDF scan / duas colunas / só imagem:** extração falha ou contexto vazio → job error, o que é preferível a fantasia genérica silenciosa — mas a UX ainda é “failed”.
8. **Fila `processing`:** sem reaper; crash deixa id preso.
9. **`/rag/*` sem auth** — só para dev.
10. **Frontend** não faz parte do núcleo; não documentar como produto.

## 9.2 Roadmap (por impacto no claim “muitos livros, alta qualidade”)

1. Matriz em livros **não vistos** (PbtA, um OSR, PF2 ou CoC real, um PDF sujo).
2. Cheque de **fidelidade**: procedimentos do índice vs tropes do sistema errado.
3. Rubrica que **reprove** texto raso (anti-saturação).
4. Query de mecânica **derivada do índice** quando o preset é generic.
5. Abortar cedo / mensagem clara em extração pobre.
6. Leitura humana de 2 campanhas em 2 sistemas.

Não é o próximo passo: um prompt gigante, multi-agente, ou um preset por jogo da moda.

## 9.3 Propriedade intelectual

O serviço indexa o PDF **do utilizador** para gerar texto novo. Não redistribuir o livro. Eval local permanece gitignored. Licença do código: MIT (README). Conteúdo gerado: ver `/legal/content-license`.
