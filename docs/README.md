# Documentação do sistema

Backend que transforma **PDFs de livros de regras de RPG** em campanhas jogáveis em Markdown.

| Idioma | Comece aqui |
|---|---|
| Português | **[pt/README.md](pt/README.md)** — fluxo completo em uma página |
| English | **[en/README.md](en/README.md)** — full flow on one page |

## Como a documentação está organizada

1. **Página inicial (PT ou EN)** — o fluxo do backend, de ponta a ponta, em linguagem direta.
2. **Capítulos de aprofundamento** — um tema por ficheiro (arquitetura, RAG, pipeline, API, …). Abra só o que precisar.
3. **Glossário** — definição curta dos termos usados nos capítulos.
4. **Evidências** — [evidence/](evidence/README.md) para diagramas, logs e excertos opcionais.

```
docs/
├── README.md              ← você está aqui
├── evidence/              ← ficheiros de apoio (opcional)
├── pt/                    ← manual em português
│   ├── README.md          ← COMECE AQUI
│   ├── 01-arquitetura.md
│   ├── 02-job.md
│   ├── 03-rag.md
│   ├── 04-pipeline.md
│   ├── 05-api.md
│   ├── 06-operacao.md
│   ├── 07-avaliacao.md
│   ├── 08-limites.md
│   └── 09-glossario.md
└── en/                    ← same structure in English
```

PDFs de livros e campanhas geradas em `examples/eval_runs/` ficam no disco local e **não** entram no git.
