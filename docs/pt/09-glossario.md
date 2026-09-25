# 9. Glossário

[← Limites](08-limites.md) · [Índice](README.md) · [Play →](11-play-overview.md)

---

| Termo | Significado neste repositório |
|---|---|
| **Job** | Unidade assíncrona: PDF + parâmetros → um Markdown |
| **Campaign State / plano** | JSON canónico da campanha; fonte dos nomes |
| **Digest** | Render textual truncado do estado, injetado nos prompts de escrita |
| **Lane** | Uma de quatro queries de retrieval (setting, mechanics, lore, theme) |
| **Packing** | Seleção de chunks sob orçamento de tokens |
| **Preset** | Id de sistema (`gurps`, `dnd5e`, …) que muda query de mecânica e bloco de prompt |
| **Rubrica** | Score heurístico 0–10 em 7 categorias |
| **Hard gate** | `validate_campaign`: se falhar, o job do utilizador não completa com qualidade aceitável |
| **9router** | Gateway local OpenAI-compatible (`NINEROUTER_URL`) |
| **book_id** | `bk_` + 16 hex do SHA-256 (ou índice reutilizado por Hamming) |
| **simples / mediana / complexa** | Tamanho do **grafo** da campanha, não um adjetivo de qualidade |
| **Front** | Pressão off-screen (impulse, portents, doom) |
| **Fallback-full** | Um único prompt clássico quando o plano JSON não serve |
| **Ack** | `LREM` do job em `rpg:processing_jobs` após sucesso ou falha terminal |
| **Voice Director** | Transforma a narração da mesa em input de TTS (speaker, Audio Tags); não conhece regras |
| **Voice Profile** | Nome do speaker → `voice_id` ElevenLabs |
| **Campaign Blueprint** | Desenho durável da campanha (plano JSON); copiado para a Campaign na criação |
| **Campaign** | Instância jogável criada a partir de um Job completed |
| **Campaign State** | Verdade mutável em play (cena, flags, Roll Call, combate) — distinto do Blueprint |
| **GameSession** | Sala multiplayer ao vivo (lobby → active → ended) |
| **Player** | Assento na mesa (User + Character opcional) |
| **Character** | PC do roster; reclamado no lobby |
| **Roll Call** | Pedido GM de confirmação de check; RNG no servidor após o Player autorizar |
| **Combat Encounter** | Tracker leve de combate no Campaign State |
| **Combatant** | Linha PC/NPC no encounter (não confundir Character com NPC) |
| **Game Master Runtime** | Loop intenção → tools → narração → estado |
| **GM Tool** | Capacidade server-side invocável pelo agente GM |
| **BookIndex** | Identidade indexada do livro (`book_id`, embeddings) usada em play via `lookup_rules` |

Play: [visão geral](11-play-overview.md) · [GM Runtime](12-gm-runtime.md) · [Roll Call](13-roll-call.md) · [Combat](14-combat.md) · [Realtime](15-realtime.md)

---

[← Realtime](15-realtime.md) · [Índice](README.md)
