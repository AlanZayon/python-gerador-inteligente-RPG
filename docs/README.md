# Documentação do sistema

Backend que transforma **PDFs de livros de regras de RPG** em campanhas jogáveis em Markdown, e corre a mesa com **Game Master Runtime** (Play).

## Site interativo

**[Abrir documentação live](https://raw.githack.com/AlanZayon/python-gerador-inteligente-RPG/main/docs/site/index.html)** — PT/EN, busca ⌘K, TOC, diagramas Mermaid, capítulos de Play/GM.

URL estável (depois de ativar Pages → GitHub Actions):  
https://alanzayon.github.io/python-gerador-inteligente-RPG/site/

No GitHub, um link para `site/index.html` só mostra o código-fonte — não uses esse caminho.

Local (opcional):

```bash
# na raiz do repositório
python -m http.server 8080
# http://localhost:8080/docs/site/
```

| Idioma | Comece aqui (Markdown) |
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
├── site/                  ← site HTML interativo (abra index.html via http.server)
├── evidence/              ← ficheiros de apoio (opcional)
├── pt/                    ← manual em português
│   ├── README.md          ← COMECE AQUI (Markdown)
│   ├── 01-arquitetura.md … 10-voz.md
│   └── 11-play-overview.md … 15-realtime.md
└── en/                    ← same structure in English
```

PDFs de livros e campanhas geradas em `examples/eval_runs/` ficam no disco local e **não** entram no git.
