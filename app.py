from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import os
import fitz  # PyMuPDF
import pdfplumber
from deep_translator import GoogleTranslator
import logging
from collections import Counter
import time
from functools import wraps
import json
from datetime import datetime
import re
from typing import List, Dict, Any
import google.generativeai as genai
import markdown
import yaml


load_dotenv()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
CORS(app, origins=["http://localhost:5173", "https://pdf-translate-vue.vercel.app"])

UPLOAD_FOLDER = 'uploads/'
CAMPAIGN_FOLDER = 'campaigns/'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_PAGES = 500  # Aumentado para livros maiores

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CAMPAIGN_FOLDER'] = CAMPAIGN_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Configurar Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_CONFIGURED = bool(GEMINI_API_KEY and GEMINI_API_KEY != 'sua_chave_aqui' and len(GEMINI_API_KEY) > 10)

if GEMINI_CONFIGURED:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("✅ Gemini configurado com sucesso")
else:
    logger.warning("❌ Gemini API key não configurada")

# Criar diretórios se não existirem
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CAMPAIGN_FOLDER, exist_ok=True)

def rate_limit(max_calls=5, window=60):
    """Decorator para limitar taxa de requisições"""
    calls = []
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            calls[:] = [call_time for call_time in calls if now - call_time < window]
            
            if len(calls) >= max_calls:
                return jsonify({'error': 'Muitas requisições. Tente novamente em alguns segundos.'}), 429
            
            calls.append(now)
            return func(*args, **kwargs)
        return wrapper
    return decorator

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_pdf(file_path):
    """Valida se o PDF é processável"""
    try:
        doc = fitz.open(file_path)
        page_count = len(doc)
        doc.close()
        
        if page_count == 0:
            return False, "PDF vazio"
        if page_count > MAX_PAGES:
            return False, f"PDF muito grande (máximo {MAX_PAGES} páginas)"
        
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
            
        # Divide texto em chunks menores para evitar limites da API
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        translated_chunks = []
        
        for chunk in chunks:
            try:
                translated = GoogleTranslator(source='auto', target=target_lang).translate(chunk)
                translated_chunks.append(translated)
                time.sleep(0.5)  # Rate limiting
            except Exception as e:
                logger.warning(f"Erro ao traduzir chunk: {e}")
                translated_chunks.append(chunk)  # Mantém original em caso de erro
        
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
        
        # Garantir que o conteúdo está na língua correta
        if target_language != 'pt':
            campaign_content = translate_text(campaign_content, target_language)
        
        return format_campaign_output(campaign_content, campaign_complexity, target_language)
        
    except Exception as e:
        logger.error(f"Erro ao gerar campanha com Gemini: {e}")
        return generate_fallback_campaign(campaign_complexity, target_language)

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

def save_campaign_to_file(campaign_content, filename, language):
    """Salva campanha em arquivo markdown"""
    try:
        safe_filename = secure_filename(filename)
        campaign_file = f"campaign_{safe_filename}_{int(time.time())}.md"
        campaign_path = os.path.join(app.config['CAMPAIGN_FOLDER'], campaign_file)
        
        with open(campaign_path, 'w', encoding='utf-8') as f:
            f.write(campaign_content)
        
        logger.info(f"Campanha salva: {campaign_path}")
        return campaign_file
    except Exception as e:
        logger.error(f"Erro ao salvar campanha: {e}")
        return None

@app.route('/generate-campaign', methods=['POST'])
@rate_limit(max_calls=3, window=60)  # 3 campanhas por minuto
def generate_campaign():
    """Endpoint principal para gerar campanhas de RPG"""
    logger.info("🎲 Recebendo requisição de geração de campanha...")
    
    try:
        # Validações
        if 'file' not in request.files:
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Nenhum arquivo selecionado'}), 400

        if not file or not allowed_file(file.filename):
            return jsonify({'error': 'Tipo de arquivo não suportado. Use apenas PDF.'}), 400

        # Parâmetros da campanha
        target_language = request.form.get('target_language', 'pt')
        campaign_complexity = request.form.get('complexity', 'mediana')
        
        if campaign_complexity not in ['simples', 'mediana', 'complexa']:
            return jsonify({'error': 'Complexidade deve ser: simples, mediana ou complexa'}), 400

        logger.info(f"Parâmetros: Idioma={target_language}, Complexidade={campaign_complexity}")

        # Salvar arquivo
        filename = secure_filename(file.filename)
        input_pdf = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(input_pdf)

        # Validar PDF
        is_valid, validation_msg = validate_pdf(input_pdf)
        if not is_valid:
            os.remove(input_pdf)
            return jsonify({'error': validation_msg}), 400

        # Processar
        logger.info("Extraindo texto do livro de RPG...")
        book_text = extract_text_from_pdf(input_pdf)
        
        if not book_text or len(book_text.strip()) < 100:
            os.remove(input_pdf)
            return jsonify({'error': 'Texto insuficiente extraído do PDF. O arquivo pode ser digitalizado como imagem.'}), 400

        logger.info("Analisando livro e gerando campanha...")
        campaign_content = analyze_rpg_book_with_gemini(book_text, target_language, campaign_complexity)

        # Salvar campanha
        base_name = os.path.splitext(filename)[0]
        campaign_filename = save_campaign_to_file(campaign_content, base_name, target_language)

        # Limpar arquivo temporário
        try:
            os.remove(input_pdf)
        except:
            pass

        if campaign_filename:
            return jsonify({
                'success': True,
                'campaign_url': f'/download-campaign/{campaign_filename}',
                'message': f'Campanha {campaign_complexity} gerada com sucesso!',
                'preview': campaign_content[:500] + '...' if len(campaign_content) > 500 else campaign_content
            }), 200
        else:
            return jsonify({'error': 'Erro ao salvar campanha'}), 500

    except Exception as e:
        logger.error(f"Erro na geração de campanha: {e}")
        # Limpar arquivo se existir
        if 'input_pdf' in locals() and os.path.exists(input_pdf):
            try:
                os.remove(input_pdf)
            except:
                pass
        return jsonify({'error': f'Erro ao processar arquivo: {str(e)}'}), 500

@app.route('/download-campaign/<filename>')
def download_campaign(filename):
    """Download da campanha gerada"""
    try:
        return send_from_directory(app.config['CAMPAIGN_FOLDER'], filename, 
                                 as_attachment=True, 
                                 download_name=f"campanha_rpg_{filename}")
    except Exception as e:
        logger.error(f"Erro no download da campanha: {e}")
        return jsonify({'error': 'Campanha não encontrada'}), 404

@app.route('/campaign-complexities', methods=['GET'])
def get_campaign_complexities():
    """Retorna complexidades de campanha disponíveis"""
    complexities = {
        'simples': {
            'name': 'Campanha Simples',
            'sessions': '1-2 sessões',
            'description': 'História direta e objetiva, perfeita para oneshots ou introduções',
            'duration': '3-8 horas totais',
            'focus': 'Combate e objetivos claros'
        },
        'mediana': {
            'name': 'Campanha Mediana', 
            'sessions': '3-4 sessões',
            'description': 'Equilíbrio entre combate, exploração e desenvolvimento',
            'duration': '9-16 horas totais',
            'focus': 'História com ramificações e escolhas'
        },
        'complexa': {
            'name': 'Campanha Complexa',
            'sessions': '5+ sessões',
            'description': 'Arco épico com múltiplos caminhos e consequências',
            'duration': '17+ horas totais', 
            'focus': 'Narrativa profunda e desenvolvimento de personagem'
        }
    }
    return jsonify(complexities)

@app.route('/supported-languages', methods=['GET'])
def get_supported_languages():
    """Retorna idiomas suportados para campanhas"""
    languages = {
        'pt': 'Português',
        'en': 'English', 
        'es': 'Español',
        'fr': 'Français',
        'de': 'Deutsch',
        'it': 'Italiano',
        'ja': '日本語',
        'ko': '한국어',
        'zh': '中文',
        'ru': 'Русский'
    }
    return jsonify(languages)

@app.route('/status', methods=['GET'])
def get_status():
    """Status da API"""
    return jsonify({
        'status': 'online',
        'service': 'RPG Campaign Generator',
        'supported_formats': list(ALLOWED_EXTENSIONS),
        'max_file_size_mb': MAX_FILE_SIZE // (1024 * 1024),
        'gemini_configured': GEMINI_CONFIGURED
    })

@app.route('/example-campaign', methods=['GET'])
def get_example_campaign():
    """Retorna um exemplo de campanha sem precisar de upload"""
    try:
        complexity = request.args.get('complexity', 'mediana')
        language = request.args.get('language', 'pt')
        
        example = generate_fallback_campaign(complexity, language)
        
        return jsonify({
            'success': True,
            'complexity': complexity,
            'language': language,
            'content': example,
            'message': 'Exemplo de campanha gerado'
        })
        
    except Exception as e:
        logger.error(f"Erro ao gerar exemplo: {e}")
        return jsonify({'error': 'Erro ao gerar exemplo'}), 500

def cleanup_old_files():
    """Remove arquivos antigos (mais de 24 horas)"""
    try:
        now = time.time()
        for folder in [UPLOAD_FOLDER, CAMPAIGN_FOLDER]:
            if os.path.exists(folder):
                for filename in os.listdir(folder):
                    file_path = os.path.join(folder, filename)
                    if os.path.isfile(file_path):
                        if now - os.path.getmtime(file_path) > 86400:  # 24 horas
                            os.remove(file_path)
                            logger.info(f"Arquivo antigo removido: {file_path}")
    except Exception as e:
        logger.warning(f"Erro na limpeza: {e}")

if __name__ == '__main__':
    cleanup_old_files()
    logger.info("🚀 Servidor iniciado - Gerador de Campanhas de RPG")
    print("""
    🎲 RPG CAMPAIGN GENERATOR 🎲
    ===========================
    Serviço: Transformação de livros de RPG em campanhas prontas
    Endpoints:
    - POST /generate-campaign   → Gera campanha a partir de PDF
    - GET  /example-campaign    → Exemplo sem upload
    - GET  /campaign-complexities → Tipos de campanha
    - GET  /supported-languages → Idiomas disponíveis
    """)
    app.run(host='0.0.0.0', port=5000, debug=False)