/**
 * Arcane Forge docs — page registry (PT / EN).
 * Paths are relative to the repo root when served via http.server.
 */
window.DOCS_CONTENT = {
  defaultLang: "pt",
  langs: {
    pt: { label: "PT", htmlLang: "pt" },
    en: { label: "EN", htmlLang: "en" },
  },
  ui: {
    pt: {
      brand: "Arcane Forge",
      tagline: "AI Game Master",
      searchPlaceholder: "Buscar na documentação…",
      searchHint: "⌘K",
      searchEmpty: "Nenhum resultado.",
      onThisPage: "Nesta página",
      prev: "Anterior",
      next: "Seguinte",
      menu: "Menu",
      close: "Fechar",
      copy: "Copiar",
      copied: "Copiado",
      markdownSource: "Fonte Markdown",
      openSearch: "Buscar",
      loading: "A carregar…",
      notFound: "Página não encontrada.",
      fetchError: "Não foi possível carregar este capítulo. Serve o repositório com um servidor HTTP local.",
      serveHint:
        "Abra o site live no README, ou na raiz: python -m http.server 8080 → /docs/site/",
      billingCallout:
        "Billing, créditos e Stripe estão fora do âmbito do produto portfolio (ADR 0004). Endpoints ainda listados no capítulo API são legado.",
      sections: {
        start: "Começar",
        generation: "Geração",
        play: "Play / GM",
        reference: "Referência",
      },
    },
    en: {
      brand: "Arcane Forge",
      tagline: "AI Game Master",
      searchPlaceholder: "Search the docs…",
      searchHint: "⌘K",
      searchEmpty: "No results.",
      onThisPage: "On this page",
      prev: "Previous",
      next: "Next",
      menu: "Menu",
      close: "Close",
      copy: "Copy",
      copied: "Copied",
      markdownSource: "Markdown source",
      openSearch: "Search",
      loading: "Loading…",
      notFound: "Page not found.",
      fetchError:
        "Could not load this chapter. Serve the repository with a local HTTP server.",
      serveHint:
        "Open the live site from the README, or from the repo root: python -m http.server 8080 → /docs/site/",
      billingCallout:
        "Billing, credits, and Stripe are out of scope for the portfolio product (ADR 0004). Endpoints still listed in the API chapter are legacy.",
      sections: {
        start: "Start",
        generation: "Generation",
        play: "Play / GM",
        reference: "Reference",
      },
    },
  },
  /**
   * slug is the hash path segment after lang: #/pt/overview
   * file is relative to docs/{lang}/
   * twin maps to the other language's slug when filenames differ
   */
  pages: [
    {
      id: "overview",
      section: "start",
      pt: { slug: "overview", file: "README.md", title: "Visão geral", search: "fluxo PDF RAG plano Markdown" },
      en: { slug: "overview", file: "README.md", title: "Overview", search: "flow PDF RAG plan Markdown" },
      showBillingCallout: true,
    },
    {
      id: "architecture",
      section: "generation",
      pt: { slug: "01-arquitetura", file: "01-arquitetura.md", title: "Arquitetura", search: "API worker Redis filas S3" },
      en: { slug: "01-architecture", file: "01-architecture.md", title: "Architecture", search: "API worker Redis queues S3" },
    },
    {
      id: "job",
      section: "generation",
      pt: { slug: "02-job", file: "02-job.md", title: "Ciclo de vida do job", search: "créditos progress stages falha" },
      en: { slug: "02-job", file: "02-job.md", title: "Job lifecycle", search: "credits progress stages failure" },
    },
    {
      id: "rag",
      section: "generation",
      pt: { slug: "03-rag", file: "03-rag.md", title: "RAG", search: "fingerprint FAISS lanes packing book_id" },
      en: { slug: "03-rag", file: "03-rag.md", title: "RAG", search: "fingerprint FAISS lanes packing book_id" },
    },
    {
      id: "pipeline",
      section: "generation",
      pt: { slug: "04-pipeline", file: "04-pipeline.md", title: "Pipeline de geração", search: "plano escrita rubrica revisão" },
      en: { slug: "04-pipeline", file: "04-pipeline.md", title: "Generation pipeline", search: "plan write rubric revision" },
    },
    {
      id: "api",
      section: "generation",
      pt: { slug: "05-api", file: "05-api.md", title: "API HTTP", search: "JWT endpoints generate-campaign" },
      en: { slug: "05-api", file: "05-api.md", title: "HTTP API", search: "JWT endpoints generate-campaign" },
      showBillingCallout: true,
    },
    {
      id: "operations",
      section: "generation",
      pt: { slug: "06-operacao", file: "06-operacao.md", title: "Operação", search: "env deploy CI segurança" },
      en: { slug: "06-operations", file: "06-operations.md", title: "Operations", search: "env deploy CI security" },
    },
    {
      id: "evaluation",
      section: "generation",
      pt: { slug: "07-avaliacao", file: "07-avaliacao.md", title: "Avaliação", search: "matriz métrica testes" },
      en: { slug: "07-evaluation", file: "07-evaluation.md", title: "Evaluation", search: "matrix metric tests" },
    },
    {
      id: "limits",
      section: "generation",
      pt: { slug: "08-limites", file: "08-limites.md", title: "Limites e roadmap", search: "limites IP roadmap" },
      en: { slug: "08-limits", file: "08-limits.md", title: "Limits & roadmap", search: "limits IP roadmap" },
    },
    {
      id: "voice-gen",
      section: "generation",
      pt: { slug: "10-voz", file: "10-voz.md", title: "Voz (TTS)", search: "ElevenLabs VoiceDirector Audio Tags" },
      en: { slug: "10-voice", file: "10-voice.md", title: "Voice (TTS)", search: "ElevenLabs VoiceDirector Audio Tags" },
    },
    {
      id: "play-overview",
      section: "play",
      pt: { slug: "11-play-overview", file: "11-play-overview.md", title: "Play — visão geral", search: "Campaign Blueprint GameSession Character" },
      en: { slug: "11-play-overview", file: "11-play-overview.md", title: "Play — overview", search: "Campaign Blueprint GameSession Character" },
    },
    {
      id: "gm-runtime",
      section: "play",
      pt: { slug: "12-gm-runtime", file: "12-gm-runtime.md", title: "Game Master Runtime", search: "GM Tools memória autoridade" },
      en: { slug: "12-gm-runtime", file: "12-gm-runtime.md", title: "Game Master Runtime", search: "GM Tools memory authority" },
    },
    {
      id: "roll-call",
      section: "play",
      pt: { slug: "13-roll-call", file: "13-roll-call.md", title: "Roll Call", search: "dados DiceRng confirmação PC" },
      en: { slug: "13-roll-call", file: "13-roll-call.md", title: "Roll Call", search: "dice DiceRng confirm PC" },
    },
    {
      id: "combat",
      section: "play",
      pt: { slug: "14-combat", file: "14-combat.md", title: "Combat tracker", search: "iniciativa HP begin_combat" },
      en: { slug: "14-combat", file: "14-combat.md", title: "Combat tracker", search: "initiative HP begin_combat" },
    },
    {
      id: "realtime",
      section: "play",
      pt: { slug: "15-realtime", file: "15-realtime.md", title: "Realtime & sessão", search: "WebSocket sync presença" },
      en: { slug: "15-realtime", file: "15-realtime.md", title: "Realtime & session", search: "WebSocket sync presence" },
    },
    {
      id: "glossary",
      section: "reference",
      pt: { slug: "09-glossario", file: "09-glossario.md", title: "Glossário", search: "termos definições" },
      en: { slug: "09-glossary", file: "09-glossary.md", title: "Glossary", search: "terms definitions" },
    },
  ],
};
