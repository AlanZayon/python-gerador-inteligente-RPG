# Documentação do sistema (português)

Gerador de campanhas de RPG a partir de **livros de regras em PDF**. O artefato principal é o **backend**. A interface Vue só demonstra o job ponta a ponta.

## Como ler

1. [Visão geral](01-visao-geral.md) — problema, não-objetivos, o que a evidência prova.
2. [Arquitetura](02-arquitetura.md) — processos, filas, armazenamento.
3. [Ciclo de vida do job](03-ciclo-de-vida.md) — do `202` ao Markdown no S3.
4. [RAG](04-rag.md) — fingerprint, chunks, lanes, packing.
5. [Pipeline de qualidade](05-pipeline.md) — plano JSON, escrita, rubrica, revisão.
6. [API](06-api.md) — contratos HTTP.
7. [Operação e segurança](07-operacao.md) — env, worker, CI, segredos.
8. [Avaliação](08-avaliacao.md) — matriz 4×3, o que a métrica é e não é.
9. [Limites e roadmap](09-limites.md) — honestidade técnica.
10. [Glossário](10-glossario.md)

Evidências: coloque arquivos em [`../evidence/`](../evidence/README.md). Os capítulos já citam os nomes.

Documento legado (mais curto): [`../CAMPAIGN_GENERATION.md`](../CAMPAIGN_GENERATION.md).
