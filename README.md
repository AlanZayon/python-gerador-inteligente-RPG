# Gerador Inteligente de RPG - API

API para geração, organização e gestão de conteúdo de RPG (campanhas, personagens, regras e resumos) usando inteligência artificial. O serviço expõe endpoints HTTP para iniciar tarefas assíncronas de criação/expansão de campanhas, acompanhar status de jobs e acessar artefatos gerados (resumos, bases de conhecimento, planilhas de personagem, etc.).

## Principais recursos
- Geração de conteúdo de campanha (ganchos, tramas, NPCs, locais) com IA
- Processamento assíncrono via filas (web dyno + worker)
- Consulta ao status de jobs e resultados processados
- Organização de arquivos por tipos: campaigns/, summaries/, knowledge_base/, character_sheets/, game_rules/
- Upload e processamento de arquivos de apoio (textos, PDFs transcritos, etc.)
- Observabilidade básica por logs

## Estrutura do projeto
- app.py: aplicação web (endpoints HTTP)
- worker.py: consumidor de fila e executor das tarefas de IA
- tasks/: tarefas de campanha (campaign_tasks.py) e auxiliares
- campaigns/: saídas de campanhas geradas
- summaries/: resumos gerados
- knowledge_base/: base de conhecimento consolidada
- character_sheets/: planilhas de personagens
- game_rules/: regras e sistemas
- uploads/: arquivos enviados para processamento
- job_status/: metadados e progresso de jobs
- cache/, processed/, translated/: artefatos intermediários

## Requisitos
- Python 3.10+
- Dependências do arquivo requirements.txt
- Variáveis de ambiente configuradas (.env) para chaves de IA/filas (ex.: OpenAI, Redis ou similar) e configurações da aplicação

## Instalação e execução local
1. Crie e ative um ambiente virtual:
   - python -m venv .venv
   - source .venv/bin/activate
2. Instale dependências:
   - pip install -r requirements.txt
3. Configure variáveis de ambiente no arquivo .env (ver seção Configuração)
4. Inicie a API web:
   - python app.py
5. Em um processo separado, inicie o worker:
   - python worker.py

A API ficará disponível por padrão em http://localhost:8000 (ou conforme definido em app.py). O worker processa as tarefas em background.

## Configuração (.env)
Exemplos de variáveis comuns (ajuste aos nomes efetivamente usados no projeto):
- GEMINI_API_KEY=... (provedor de IA)
- REDIS_URL=... (Ex.: Redis/CloudAMQP)
- MAX_FILE_SIZE=52428800
- MAX_PAGES=500


## Endpoints (visão geral)
Observação: Os caminhos e payloads exatos podem variar conforme implementação em app.py e tasks/campaign_tasks.py. Esta seção descreve o fluxo típico.

- POST /campaigns
  - Inicia a geração/expansão de uma campanha
  - Body (JSON, exemplo):
    {
      "title": "Sombras de Valendor",
      "system": "D&D 5e",
      "tone": "Dark fantasy",
      "inputs": ["briefing inicial", "história de mundo", "lista de NPCs"],
      "language": "pt-BR"
    }
  - Resposta: { "job_id": "<id>" }

- GET /jobs/<job_id>
  - Retorna status do job e, quando concluído, caminhos/links para artefatos gerados
  - Exemplo de resposta:
    {
      "status": "completed",
      "outputs": {
        "campaign_path": "campaigns/valendor/",
        "summary": "summaries/valendor.md"
      }
    }

- GET /campaigns/<id>
  - Retorna metadados da campanha e links para arquivos organizados (NPCs, locais, ganchos, etc.)

- POST /uploads
  - Faz upload de arquivos de referência para enriquecer a geração
  - Resposta inclui referência para uso posterior nas tasks

- GET /health
  - Sinalização simples de saúde do serviço


## Fluxo de uso recomendado
1. Envie materiais de referência (opcional) via /uploads
2. Chame POST /campaigns com o briefing e preferências do sistema/estilo
3. Receba job_id e acompanhe em GET /jobs/<job_id>
4. Ao finalizar, acesse os arquivos organizados em campaigns/, summaries/ e demais pastas

## Formato dos resultados
- Campaigns: diretórios com textos da campanha, capítulos, NPCs, locais, itens
- Summaries: arquivos .md com resumos de sessões e visão geral
- Knowledge base: notas unificadas, glosários, timelines
- Character sheets: fichas em JSON/Markdown conforme sistema
- Game rules: referências e adaptações de regras

## Execução em produção
- Procfile indica processos web e worker para plataformas compatíveis (ex.: Heroku, Railway)
- Defina variáveis de ambiente seguras e volumes/persistência de arquivos
- Garanta que web e worker compartilhem o mesmo backend de fila/armazenamento

## Observabilidade
- Logs estruturados em app e worker (stdout/stderr)
- job_status/ mantém progresso e metadados
- Integre métricas/APM conforme necessidade

## Boas práticas e limites
- Valide entradas e tamanho de prompts
- Respeite limites de tokens/custos do provedor de IA
- Faça versionamento dos artefatos de campanha
- Evite subir ao repositório arquivos com dados sensíveis ou pesados; use .gitignore

## Desenvolvimento
- tasks/campaign_tasks.py concentra as rotinas principais de geração
- Teste localmente com payloads pequenos e evolua para cenários maiores
- Adapte prompts, templates e estrutura de saída conforme seu sistema de RPG

## Licença
Defina a licença do projeto (MIT, Apache-2.0, etc.) conforme sua preferência.
