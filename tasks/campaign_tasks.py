"""
Módulo de tarefas para processamento assíncrono de campanhas
ATUALIZADO para trabalhar com arquivos S3
"""

import os
import logging
import time
import tempfile
import requests
import fitz  # PyMuPDF
from deep_translator import GoogleTranslator
import google.generativeai as genai
from datetime import datetime
from werkzeug.utils import secure_filename
import json
from dotenv import load_dotenv
from urllib.parse import urlparse

# Carregar variáveis de ambiente
load_dotenv()

from services.s3_storage import upload_content_to_s3

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configurações
CAMPAIGN_FOLDER = 'campaigns/'
JOB_STATUS_FOLDER = 'job_status/'

# Configurar Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_CONFIGURED = bool(GEMINI_API_KEY and GEMINI_API_KEY != 'sua_chave_aqui' and len(GEMINI_API_KEY) > 10)

if GEMINI_CONFIGURED:
    genai.configure(api_key=GEMINI_API_KEY)

def save_job_status(job_id, status, data=None):
    """Salva o status do job em arquivo JSON"""
    try:
        os.makedirs(JOB_STATUS_FOLDER, exist_ok=True)
        status_file = os.path.join(JOB_STATUS_FOLDER, f'{job_id}.json')
        status_data = {
            'job_id': job_id,
            'status': status,
            'last_updated': datetime.now().isoformat(),
            'data': data or {}
        }
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(status_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar status do job {job_id}: {e}")
        return False

def download_file_from_s3(file_url, job_id):
    """Baixa arquivo do S3 para um arquivo temporário"""
    try:
        # Criar diretório temporário específico para o job
        temp_dir = os.path.join(tempfile.gettempdir(), f"rpg_job_{job_id}")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Extrair nome do arquivo da URL
        parsed_url = urlparse(file_url)
        filename = os.path.basename(parsed_url.path)
        
        # Definir caminho local
        local_path = os.path.join(temp_dir, secure_filename(filename))
        
        logger.info(f"Baixando arquivo do S3: {file_url} para {local_path}")
        
        # Download do arquivo
        response = requests.get(file_url, stream=True, timeout=60)
        response.raise_for_status()
        
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Download concluído: {local_path} ({os.path.getsize(local_path)} bytes)")
        return local_path
        
    except Exception as e:
        logger.error(f"Erro ao baixar arquivo do S3: {e}")
        raise

def cleanup_temp_files(file_path):
    """Limpa arquivos temporários"""
    try:
        if file_path and os.path.exists(file_path):
            # Remover arquivo
            os.remove(file_path)
            
            # Tentar remover diretório pai se estiver vazio
            parent_dir = os.path.dirname(file_path)
            if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                os.rmdir(parent_dir)
                
            logger.info(f"Arquivos temporários limpos: {file_path}")
    except Exception as e:
        logger.warning(f"Erro ao limpar arquivos temporários: {e}")

def validate_pdf(file_path):
    """Valida se o PDF é processável"""
    try:
        doc = fitz.open(file_path)
        page_count = len(doc)
        doc.close()
        
        if page_count == 0:
            return False, "PDF vazio"
        if page_count > 500:  # MAX_PAGES
            return False, f"PDF muito grande (máximo 500 páginas)"
        
        logger.info(f"PDF validado: {page_count} páginas")
        return True, "OK"
    except Exception as e:
        logger.error(f"Erro na validação do PDF: {e}")
        return False, "PDF corrompido ou ilegível"

def extract_text_from_pdf(file_path):
    """Extrai texto completo do PDF"""
    try:
        full_text = ""
        with fitz.open(file_path) as doc:
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text()
                full_text += f"\n--- Página {page_num + 1} ---\n{text}"
        
        logger.info(f"Texto extraído: {len(full_text)} caracteres")
        return full_text
    except Exception as e:
        logger.error(f"Erro na extração de texto: {e}")
        return ""

def translate_text(text, target_lang):
    """Traduz texto usando Google Translator"""
    try:
        if not text.strip() or len(text.strip()) < 10:
            return text
            
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        translated_chunks = []
        
        for chunk in chunks:
            try:
                translated = GoogleTranslator(source='auto', target=target_lang).translate(chunk)
                translated_chunks.append(translated)
                time.sleep(0.5)  # Rate limiting
            except Exception as e:
                logger.warning(f"Erro ao traduzir chunk: {e}")
                translated_chunks.append(chunk)
        
        return " ".join(translated_chunks)
        
    except Exception as e:
        logger.error(f"Erro na tradução: {e}")
        return text

def analyze_rpg_book_with_gemini(book_text, target_language, campaign_complexity):
    """Analisa o livro de RPG e gera campanha usando Gemini"""
    if not GEMINI_CONFIGURED:
        return generate_fallback_campaign(campaign_complexity, target_language)
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash-lite')
        
        prompt = f"""
        VOCÊ É UM MESTRE DE RPG ESPECIALISTA em criar campanhas completas e prontas para jogar.

        **LIVRO DE RPG FORNECIDO:**
        {book_text[:15000]}... [texto truncado para análise]

        **INSTRUÇÕES:**
        1. Analise o livro de RPG acima e ENTENDA seu sistema, cenário, mecânicas e estilo
        2. Crie uma campanha **{campaign_complexity.upper()}** na língua: {target_language}
        3. A campanha deve ser COMPLETA - o mestre deve poder pegar e jogar SEM preparação adicional

        **FORMATO DA CAMPANHA ({campaign_complexity}):**
        {get_complexity_guidelines(campaign_complexity)}

        **ESTRUTURA OBRIGATÓRIA:**
        ```yaml
        Título: [Título criativo da campanha]
        Complexidade: {campaign_complexity}
        Sessões: [número baseado na complexidade]
        Nível dos Personagens: [intervalo recomendado]
        Sistema: [baseado no livro analisado]
        ```

        **CONTEÚDO DETALHADO:**
        - **VISÃO GERAL**: Resumo envolvente da campanha
        - **GANCHO INICIAL**: Como começar a primeira sessão
        - **ARQUETRAMAS DE PERSONAGENS**: Sugestões que se encaixam na campanha
        - **SESSÕES DETALHADAS**: Cada sessão com objetivos, encontros, NPCs, tesouros
        - **NPCs IMPORTANTES**: Estatísticas completas ou referências
        - **INIMIGOS E CRIATURAS**: Encontros balanceados
        - **RECOMPENSAS E TESOUROS**: Itens mágicos, equipamentos, recompensas
        - **DESAFIOS E ENIGMAS**: Quebra-cabeças e desafios não-combativos
        - **FINAIS POSSÍVEIS**: Múltiplos desfechos baseados nas escolhas
        - **MAPAS E LOCALIZAÇÕES**: Descrições detalhadas ou instruções para criar

        **ESTILO:**
        - Use markdown para formatação
        - Seja específico e detalhado
        - Forneça estatísticas ou referências claras ao sistema
        - Inclua diálogos de NPCs quando relevante
        - Balanceie combate, exploração e roleplay

        Gere a campanha completa em {target_language}:
        """

        response = model.generate_content(prompt)
        campaign_content = response.text
        
        if target_language != 'pt':
            campaign_content = translate_text(campaign_content, target_language)
        
        return format_campaign_output(campaign_content, campaign_complexity, target_language)
        
    except Exception as e:
        logger.error(f"Erro ao gerar campanha com Gemini: {e}")
        return generate_fallback_campaign(campaign_complexity, target_language)

def generate_fallback_campaign(complexity, language):
    """Gera campanha fallback se o Gemini falhar"""
    base_campaigns = {
        'simples': {
            'title': 'A Taverna do Dragão Adormecido',
            'sessions': 2,
            'overview': 'Uma taverna isolada esconde um segredo mortal sob seu porão.',
            'content': """
# A Taverna do Dragão Adormecido

## Visão Geral
Os jogadores chegam à taverna "O Dragão Adormecido" durante uma tempestade. O local parece comum, mas esconde um culto que realiza ritual sob o estabelecimento.

## Sessão 1: A Chegada
**Objetivo**: Investigar os desaparecimentos na taverna

**Cena 1**: Chegada durante tempestade
- NPCs: Thorin (dono), Liana (garçonete), Viajantes
- Evento: Um viajante desaparece durante a noite

**Cena 2**: Investigação
- Pistas: Manchas estranhas no porão, símbolos ocultos
- Encontro: Guardas do culto (2 humanos, 1 feiticeiro)

## Sessão 2: O Ritual
**Objetivo**: Impedir o ritual de invocação

**Cena 1**: Túneis secretos
- Quebra-cabeça: Símbolos elementais para abrir portas

**Cena 2**: Salão do ritual
- Chefe: Líder do culto e acólitos
- Recompensa: Artefato mágico do dragão

## NPCs Principais
- **Thorin**: Humano guerreiro Nível 3 (aliança possível)
- **Líder do Culto**: Feiticeiro Nível 4

## Recompensas
- 500 PO + Amuleto de Proteção (resistência a magia)
            """
        },
        'mediana': {
            'title': 'A Maldição da Floresta Ancestral',
            'sessions': 4,
            'overview': 'Uma floresta amaldiçoada está se expandindo e corrompendo tudo ao redor.',
            'content': """
# A Maldição da Floresta Ancestral

## Visão Geral
Uma floresta ancestral começou a se expandir magicamente, corrompendo terras vizinhas. Os jogadores devem descobrir a fonte da maldição.

## Sessão 1: Vila na Fronteira
**Objetivo**: Investigar a expansão florestal

**Cena 1**: Vila de Oakhaven
- NPCs: Prefeito preocupado, Druida recluso
- Missões: Resgatar desaparecidos, coletar amostras

**Cena 2**: Orla da floresta
- Encontro: Criaturas corrompidas (lobos, ursos)

## Sessão 2: Coração da Floresta
**Objetivo**: Encontrar o druida ancião

**Cena 1**: Navegação perigosa
- Desafios: Labirinto natural, plantas carnívoras

**Cena 2**: Clareira do druida
- NPC: Elowen (druida Nível 5), revela origem da maldição

## Sessão 3: Templo Esquecido
**Objetivo**: Recuperar artefato purificador

**Cena 1**: Ruínas submersas
- Quebra-cabeça: Alinhamento celestial

**Cena 2**: Guardiões do templo
- Combate: Elementais da natureza

## Sessão 4: Confronto Final
**Objetivo**: Purificar a fonte da corrupção

**Cena 1**: Nascente corrompida
- Chefe: Espírito Corrompido (CR 6)
- Recompensas: Tesouro druídico

## Desenvolvimento de Personagem
Sugestões de arquetipagem: Ranger da floresta, Druida, Clérigo da natureza
            """
        }
    }
    
    campaign = base_campaigns.get(complexity, base_campaigns['mediana'])
    
    if language != 'pt':
        campaign['content'] = translate_text(campaign['content'], language)
        campaign['title'] = translate_text(campaign['title'], language)
        campaign['overview'] = translate_text(campaign['overview'], language)
    
    return format_campaign_output(campaign['content'], complexity, language, campaign['title'])

def format_campaign_output(content, complexity, language, title=None):
    """Formata a saída da campanha de forma padronizada"""
    session_counts = {'simples': '1-2', 'mediana': '3-4', 'complexa': '5+'}
    
    formatted = f"""
# 🎲 CAMPANHA DE RPG - {complexity.upper()}
{'#' if not title else f'# {title}'}
**Duração**: {session_counts.get(complexity, '3-4')} sessões  
**Idioma**: {language}  
**Gerado em**: {datetime.now().strftime('%d/%m/%Y %H:%M')}  
**Complexidade**: {complexity.capitalize()}

---

{content}

---

*Campanha gerada automaticamente a partir de análise de livro de RPG.  
Balanceamento pode precisar de ajustes para seu grupo específico.*
"""
    return formatted

def save_campaign_to_s3(campaign_content, original_filename):
    base_name = os.path.splitext(secure_filename(original_filename))[0]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    campaign_filename = f"campaign_{base_name}_{timestamp}.md"
    
    return upload_content_to_s3(campaign_content, campaign_filename)

def get_complexity_guidelines(complexity):
    """Retorna diretrizes baseadas na complexidade"""
    guidelines = {
        'simples': """
        - 1-2 sessões de 3-4 horas cada
        - História linear e objetiva
        - 2-3 encontros principais (combate/roleplay)
        - 1-2 NPCs importantes
        - 1 localização principal
        - Resolução direta
        """,
        'mediana': """
        - 3-4 sessões de 3-4 horas cada  
        - História com alguns ramos e escolhas
        - 4-6 encontros diversificados
        - 3-5 NPCs com personalidades distintas
        - 2-3 localizações interconectadas
        - Múltiplas formas de resolver problemas
        """,
        'complexa': """
        - 5+ sessões de 3-4 horas cada
        - História não-linear com múltiplos arcos
        - 8+ encontros variados (combate, social, exploração)
        - 6+ NPCs com motivações complexas
        - 4+ localizações detalhadas
        - Sistema de consequências por escolhas
        - Múltiplos finais possíveis
        """
    }
    return guidelines.get(complexity, guidelines['mediana'])

def process_campaign_generation(job_id, file_url, filename, target_language, campaign_complexity):
    """
    Função principal para processar geração de campanha a partir de arquivo S3
    """
    logger.info(f"🎲 Iniciando processamento do job {job_id}")
    local_file_path = None
    
    try:
        # Atualizar status para processando
        save_job_status(job_id, 'processing', {'progress': 'Baixando arquivo do S3...'})
        
        # 1. Baixar arquivo do S3
        local_file_path = download_file_from_s3(file_url, job_id)
        
        # 2. Validar PDF
        save_job_status(job_id, 'processing', {'progress': 'Validando PDF...'})
        is_valid, validation_msg = validate_pdf(local_file_path)
        if not is_valid:
            save_job_status(job_id, 'failed', {'error': validation_msg})
            cleanup_temp_files(local_file_path)
            return None
        
        # 3. Extrair texto
        save_job_status(job_id, 'processing', {'progress': 'Extraindo texto do PDF...'})
        book_text = extract_text_from_pdf(local_file_path)
        
        if not book_text or len(book_text.strip()) < 100:
            save_job_status(job_id, 'failed', {'error': 'Texto insuficiente extraído do PDF.'})
            cleanup_temp_files(local_file_path)
            return None
        
        # 4. Gerar campanha
        save_job_status(job_id, 'processing', {'progress': 'Gerando campanha com IA...'})
        campaign_content = analyze_rpg_book_with_gemini(book_text, target_language, campaign_complexity)
        
        # 5. Salvar campanha no S3
        save_job_status(job_id, 'processing', {'progress': 'Salvando campanha gerada no S3...'})
        upload_result = save_campaign_to_s3(campaign_content, filename)

        s3_key = upload_result['s3_key']
        campaign_url = upload_result['file_url']        
        # 6. Limpar arquivo temporário
        cleanup_temp_files(local_file_path)
        
        if s3_key:
            result = {
                'campaign_url': campaign_url,  # URL pré-assinada do S3
                's3_key': s3_key,  # S3 Key para referência futura
                'preview': campaign_content[:500] + '...' if len(campaign_content) > 500 else campaign_content,
                'file_size': len(campaign_content)  # Tamanho do conteúdo da campanha
            }
            save_job_status(job_id, 'completed', result)
            logger.info(f"✅ Job {job_id} concluído com sucesso")
            return result
        else:
            save_job_status(job_id, 'failed', {'error': 'Erro ao salvar campanha no S3'})
            return None
            
    except Exception as e:
        logger.error(f"Erro no processamento do job {job_id}: {e}")
        save_job_status(job_id, 'failed', {'error': str(e)})
        
        # Limpar arquivo temporário em caso de erro
        cleanup_temp_files(local_file_path if 'local_file_path' in locals() else None)
        return None