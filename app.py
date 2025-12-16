from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import requests
import os
import logging
import time
from functools import wraps
import uuid
import redis
from rq import Queue
import json
from datetime import datetime

# IMPORTE A FUNÇÃO DO MÓDULO DE TAREFAS
from tasks.campaign_tasks import process_campaign_generation
from services.s3_storage import upload_pdf_to_s3


load_dotenv()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=["http://localhost:5173", "https://pdf-translate-vue.vercel.app"])

UPLOAD_FOLDER = 'uploads/'
CAMPAIGN_FOLDER = 'campaigns/'
JOB_STATUS_FOLDER = 'job_status/'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CAMPAIGN_FOLDER'] = CAMPAIGN_FOLDER
app.config['JOB_STATUS_FOLDER'] = JOB_STATUS_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Configurar Redis e RQ
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
redis_conn = None
task_queue = None

try:
    redis_conn = redis.from_url(REDIS_URL, socket_connect_timeout=5)
    redis_conn.ping()
    logger.info(f"✅ Redis conectado: {REDIS_URL}")
    task_queue = Queue('campaign_generation', connection=redis_conn, default_timeout=3600)
except redis.ConnectionError as e:
    logger.warning(f"❌ Redis não disponível: {e}")
    logger.warning("Usando modo de desenvolvimento sem Redis (jobs serão processados sincronamente)")
    task_queue = None
except Exception as e:
    logger.warning(f"❌ Erro ao conectar ao Redis: {e}")
    task_queue = None

def trigger_worker():
    owner = os.getenv("GITHUB_REPO_OWNER")
    repo = os.getenv("GITHUB_REPO_NAME")
    workflow = os.getenv("GITHUB_WORKFLOW_FILE", "campaign_worker.yml")
    branch = os.getenv("GITHUB_BRANCH", "main")
    token = os.getenv("GITHUB_TOKEN")

    if not all([owner, repo, workflow, token]):
        logger.warning("⚠️ Variáveis de ambiente do GitHub não configuradas")
        return

    url = (
        f"https://api.github.com/repos/"
        f"{owner}/{repo}/"
        f"actions/workflows/{workflow}/dispatches"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    payload = {"ref": branch}

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code not in (200, 204):
        logger.error(
            f"❌ Falha ao disparar worker: "
            f"{response.status_code} - {response.text}"
        )
        response.raise_for_status()

    logger.info("🚀 Worker do GitHub Actions disparado com sucesso")

# Criar diretórios se não existirem
for folder in [UPLOAD_FOLDER, CAMPAIGN_FOLDER, JOB_STATUS_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# FUNÇÕES DE APOIO (mantenha apenas essas)
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def rate_limit(max_calls=10, window=60):
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

def get_job_status(job_id):
    """Obtém o status do job do arquivo JSON"""
    try:
        status_file = os.path.join(app.config['JOB_STATUS_FOLDER'], f'{job_id}.json')
        if os.path.exists(status_file):
            with open(status_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    except Exception as e:
        logger.error(f"Erro ao ler status do job {job_id}: {e}")
        return None

def cleanup_old_files():
    """Remove arquivos antigos (mais de 24 horas)"""
    try:
        now = time.time()
        for folder in [UPLOAD_FOLDER, CAMPAIGN_FOLDER, JOB_STATUS_FOLDER]:
            if os.path.exists(folder):
                for filename in os.listdir(folder):
                    file_path = os.path.join(folder, filename)
                    if os.path.isfile(file_path):
                        if now - os.path.getmtime(file_path) > 86400:  # 24 horas
                            os.remove(file_path)
                            logger.info(f"Arquivo antigo removido: {file_path}")
    except Exception as e:
        logger.warning(f"Erro na limpeza: {e}")

# ROTAS (mantenha todas as rotas, exceto a função generate_campaign que vamos atualizar)
@app.route('/generate-campaign', methods=['POST'])
@rate_limit(max_calls=5, window=60)
def generate_campaign():
    """Endpoint para iniciar geração de campanha (assíncrono via Redis + S3)"""
    logger.info("🎲 Recebendo requisição de geração de campanha...")

    input_pdf = None

    try:
        # =========================
        # Validações do arquivo
        # =========================
        if 'file' not in request.files:
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': 'Nenhum arquivo selecionado'}), 400

        if not allowed_file(file.filename):
            return jsonify({'error': 'Tipo de arquivo não suportado. Use apenas PDF.'}), 400

        # =========================
        # Parâmetros da campanha
        # =========================
        target_language = request.form.get('target_language', 'pt')
        campaign_complexity = request.form.get('complexity', 'mediana')

        if campaign_complexity not in ['simples', 'mediana', 'complexa']:
            return jsonify({
                'error': 'Complexidade deve ser: simples, mediana ou complexa'
            }), 400

        # =========================
        # Criar Job
        # =========================
        job_id = str(uuid.uuid4())
        logger.info(
            f"Novo job criado: {job_id} | Idioma={target_language} | Complexidade={campaign_complexity}"
        )

        # =========================
        # Salvar arquivo TEMPORÁRIO
        # =========================
        filename = secure_filename(file.filename)
        input_pdf = os.path.join(
            app.config['UPLOAD_FOLDER'],
            f"{job_id}_{filename}"
        )
        file.save(input_pdf)

        # =========================
        # Upload para S3
        # =========================
        upload_result = upload_pdf_to_s3(input_pdf, filename)

        # Remove o arquivo local após upload
        os.remove(input_pdf)
        input_pdf = None

        # =========================
        # Fallback síncrono (sem Redis)
        # =========================
        if redis_conn is None:
            logger.warning("⚠️ Redis indisponível — executando processamento síncrono")

            file_url = upload_result["file_url"]


            result = process_campaign_generation(
                job_id=job_id,
                file_url=file_url,
                filename=filename,
                target_language=target_language,
                campaign_complexity=campaign_complexity
            )

            if not result:
                return jsonify({'error': 'Falha ao processar campanha'}), 500

            return jsonify({
                'success': True,
                'job_id': job_id,
                'status': 'completed',
                'result': result
            }), 200

        # =========================
        # Modo assíncrono (Redis)
        # =========================
        job_key = f"rpg:job:{job_id}"

        redis_conn.hset(job_key, mapping={
            "job_id": job_id,
            "file_url": upload_result["file_url"],
            "s3_key": upload_result["s3_key"],
            "filename": filename,
            "language": target_language,
            "complexity": campaign_complexity,
            "status": "queued",
            "created_at": datetime.utcnow().isoformat()
        })

        # Enfileirar job
        redis_conn.rpush('rpg:pending_jobs', job_id)

        logger.info(f"📥 Job {job_id} adicionado à fila Redis")

        # =========================
        # Disparar worker (GitHub Actions)
        # =========================
        try:
            trigger_worker()
            logger.info("🚀 Workflow do worker disparado")
        except Exception as e:
            logger.error(f"⚠️ Falha ao disparar worker: {e}")

        return jsonify({
            'success': True,
            'job_id': job_id,
            'status': 'queued',
            'message': 'Job adicionado à fila de processamento'
        }), 202

    except Exception as e:
        logger.error(f"🚨 Erro ao iniciar geração de campanha: {e}")

        if input_pdf and os.path.exists(input_pdf):
            try:
                os.remove(input_pdf)
            except Exception:
                pass

        return jsonify({
            'error': f'Erro ao processar requisição: {str(e)}'
        }), 500


@app.route('/job-status/<job_id>', methods=['GET'])
def get_job_status_endpoint(job_id):
    """Endpoint para verificar status do job"""
    status_data = get_job_status(job_id)
    
    if not status_data:
        return jsonify({'error': 'Job não encontrado'}), 404
    
    response = {
        'job_id': job_id,
        'status': status_data['status'],
        'last_updated': status_data['last_updated']
    }
    
    # Incluir dados adicionais baseados no status
    if status_data.get('data'):
        response.update(status_data['data'])
    
    return jsonify(response)

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
        'gemini_configured': GEMINI_CONFIGURED,
        'queue_status': {
            'queued': len(task_queue.jobs),
            'workers': len(task_queue.get_workers())
        }
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

if __name__ == '__main__':
    cleanup_old_files()
    logger.info("🚀 Servidor iniciado - Gerador de Campanhas de RPG")
    print("""
    🎲 RPG CAMPAIGN GENERATOR 🎲
    ===========================
    Serviço: Transformação de livros de RPG em campanhas prontas
    Endpoints:
    - POST /generate-campaign   → Inicia geração assíncrona (retorna job_id)
    - GET  /job-status/:job_id  → Verifica status do processamento
    - GET  /example-campaign    → Exemplo sem upload
    - GET  /campaign-complexities → Tipos de campanha
    - GET  /supported-languages → Idiomas disponíveis
    
    ⚠️  Configure Redis em um worker separado:
    $ rq worker campaign_generation --url redis://localhost:6379/0
    """)
    app.run(host='0.0.0.0', port=5000, debug=False)