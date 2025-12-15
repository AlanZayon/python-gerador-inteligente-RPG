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

# Logging configuration
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
MAX_PAGES = 500  # Increased for larger books

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CAMPAIGN_FOLDER'] = CAMPAIGN_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Configure Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_CONFIGURED = bool(GEMINI_API_KEY and GEMINI_API_KEY != 'your_key_here' and len(GEMINI_API_KEY) > 10)

if GEMINI_CONFIGURED:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("✅ Gemini configured successfully")
else:
    logger.warning("❌ Gemini API key not configured")

# Create directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CAMPAIGN_FOLDER, exist_ok=True)

def rate_limit(max_calls=5, window=60):
    """Decorator to limit request rate"""
    calls = []
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            calls[:] = [call_time for call_time in calls if now - call_time < window]
            
            if len(calls) >= max_calls:
                return jsonify({'error': 'Too many requests. Try again in a few seconds.'}), 429
            
            calls.append(now)
            return func(*args, **kwargs)
        return wrapper
    return decorator

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_pdf(file_path):
    """Validates if PDF is processable"""
    try:
        doc = fitz.open(file_path)
        page_count = len(doc)
        doc.close()
        
        if page_count == 0:
            return False, "Empty PDF"
        if page_count > MAX_PAGES:
            return False, f"PDF too large (maximum {MAX_PAGES} pages)"
        
        logger.info(f"PDF validated: {page_count} pages")
        return True, "OK"
    except Exception as e:
        logger.error(f"Error validating PDF: {e}")
        return False, "Corrupted or unreadable PDF"

def extract_text_from_pdf(file_path):
    """Extracts complete text from PDF"""
    try:
        full_text = ""
        with fitz.open(file_path) as doc:
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text()
                full_text += f"\n--- Page {page_num + 1} ---\n{text}"
        
        logger.info(f"Text extracted: {len(full_text)} characters")
        return full_text
    except Exception as e:
        logger.error(f"Error extracting text: {e}")
        return ""

def translate_text(text, target_lang):
    """Translates text using Google Translator"""
    try:
        if not text.strip() or len(text.strip()) < 10:
            return text
            
        # Split text into smaller chunks to avoid API limits
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        translated_chunks = []
        
        for chunk in chunks:
            try:
                translated = GoogleTranslator(source='auto', target=target_lang).translate(chunk)
                translated_chunks.append(translated)
                time.sleep(0.5)  # Rate limiting
            except Exception as e:
                logger.warning(f"Error translating chunk: {e}")
                translated_chunks.append(chunk)  # Keep original on error
        
        return " ".join(translated_chunks)
        
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return text

def analyze_rpg_book_with_gemini(book_text, target_language, campaign_complexity):
    """Analyzes RPG book and generates campaign using Gemini"""
    if not GEMINI_CONFIGURED:
        return generate_fallback_campaign(campaign_complexity, target_language)
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash-lite')
        
        prompt = f"""
        YOU ARE A SPECIALIST RPG GAME MASTER expert in creating complete, ready-to-play campaigns.

        **PROVIDED RPG BOOK:**
        {book_text[:15000]}... [text truncated for analysis]

        **INSTRUCTIONS:**
        1. Analyze the RPG book above and UNDERSTAND its system, setting, mechanics, and style
        2. Create a **{campaign_complexity.upper()}** campaign in language: {target_language}
        3. The campaign must be COMPLETE - the game master should be able to pick it up and play WITHOUT additional preparation

        **CAMPAIGN FORMAT ({campaign_complexity}):**
        {get_complexity_guidelines(campaign_complexity)}

        **MANDATORY STRUCTURE:**
        ```yaml
        Title: [Creative campaign title]
        Complexity: {campaign_complexity}
        Sessions: [number based on complexity]
        Character Level: [recommended range]
        System: [based on analyzed book]
        ```

        **DETAILED CONTENT:**
        - **OVERVIEW**: Engaging campaign summary
        - **STARTING HOOK**: How to begin the first session
        - **CHARACTER ARCHETYPES**: Suggestions fitting the campaign
        - **DETAILED SESSIONS**: Each session with objectives, encounters, NPCs, treasures
        - **IMPORTANT NPCS**: Complete statistics or references
        - **ENEMIES AND CREATURES**: Balanced encounters
        - **REWARDS AND TREASURES**: Magic items, equipment, rewards
        - **CHALLENGES AND PUZZLES**: Non-combat puzzles and challenges
        - **POSSIBLE ENDINGS**: Multiple outcomes based on choices
        - **MAPS AND LOCATIONS**: Detailed descriptions or creation instructions

        **STYLE:**
        - Use markdown for formatting
        - Be specific and detailed
        - Provide statistics or clear system references
        - Include NPC dialogues when relevant
        - Balance combat, exploration, and roleplay

        Generate the complete campaign in {target_language}:
        """

        response = model.generate_content(prompt)
        campaign_content = response.text
        
        # Ensure content is in correct language
        if target_language != 'en':
            campaign_content = translate_text(campaign_content, target_language)
        
        return format_campaign_output(campaign_content, campaign_complexity, target_language)
        
    except Exception as e:
        logger.error(f"Error generating campaign with Gemini: {e}")
        return generate_fallback_campaign(campaign_complexity, target_language)

def get_complexity_guidelines(complexity):
    """Returns guidelines based on complexity"""
    guidelines = {
        'simple': """
        - 1-2 sessions of 3-4 hours each
        - Linear and objective story
        - 2-3 main encounters (combat/roleplay)
        - 1-2 important NPCs
        - 1 main location
        - Direct resolution
        """,
        'medium': """
        - 3-4 sessions of 3-4 hours each  
        - Story with some branches and choices
        - 4-6 diverse encounters
        - 3-5 NPCs with distinct personalities
        - 2-3 interconnected locations
        - Multiple problem-solving approaches
        """,
        'complex': """
        - 5+ sessions of 3-4 hours each
        - Non-linear story with multiple arcs
        - 8+ varied encounters (combat, social, exploration)
        - 6+ NPCs with complex motivations
        - 4+ detailed locations
        - Consequence system for choices
        - Multiple possible endings
        """
    }
    return guidelines.get(complexity, guidelines['medium'])

def generate_fallback_campaign(complexity, language):
    """Generates fallback campaign if Gemini fails"""
    base_campaigns = {
        'simple': {
            'title': 'The Sleeping Dragon Tavern',
            'sessions': 2,
            'overview': 'An isolated tavern hides a deadly secret beneath its cellar.',
            'content': """
# The Sleeping Dragon Tavern

## Overview
The players arrive at "The Sleeping Dragon" tavern during a storm. The place seems ordinary, but hides a cult performing rituals beneath the establishment.

## Session 1: The Arrival
**Objective**: Investigate disappearances at the tavern

**Scene 1**: Arrival during storm
- NPCs: Thorin (owner), Liana (waitress), Travelers
- Event: A traveler disappears during the night

**Scene 2**: Investigation
- Clues: Strange stains in the cellar, hidden symbols
- Encounter: Cult guards (2 humans, 1 spellcaster)

## Session 2: The Ritual
**Objective**: Prevent the summoning ritual

**Scene 1**: Secret tunnels
- Puzzle: Elemental symbols to open doors

**Scene 2**: Ritual chamber
- Boss: Cult leader and acolytes
- Reward: Dragon magical artifact

## Main NPCs
- **Thorin**: Human warrior Level 3 (possible alliance)
- **Cult Leader**: Spellcaster Level 4

## Rewards
- 500 GP + Protection Amulet (magic resistance)
            """
        },
        'medium': {
            'title': 'The Curse of the Ancient Forest',
            'sessions': 4,
            'overview': 'A cursed forest is expanding and corrupting everything around it.',
            'content': """
# The Curse of the Ancient Forest

## Overview
An ancient forest has begun magically expanding, corrupting nearby lands. The players must discover the source of the curse.

## Session 1: Frontier Village
**Objective**: Investigate forest expansion

**Scene 1**: Oakhaven village
- NPCs: Worried mayor, Reclusive druid
- Quests: Rescue missing people, collect samples

**Scene 2**: Forest edge
- Encounter: Corrupted creatures (wolves, bears)

## Session 2: Heart of the Forest
**Objective**: Find the elder druid

**Scene 1**: Dangerous navigation
- Challenges: Natural maze, carnivorous plants

**Scene 2**: Druid clearing
- NPC: Elowen (druid Level 5), reveals curse origin

## Session 3: Forgotten Temple
**Objective**: Retrieve purification artifact

**Scene 1**: Submerged ruins
- Puzzle: Celestial alignment

**Scene 2**: Temple guardians
- Combat: Nature elementals

## Session 4: Final Confrontation
**Objective**: Purify corruption source

**Scene 1**: Corrupted spring
- Boss: Corrupted Spirit (CR 6)
- Rewards: Druidic treasure

## Character Development
Archetype suggestions: Forest ranger, Druid, Nature cleric
            """
        }
    }
    
    campaign = base_campaigns.get(complexity, base_campaigns['medium'])
    
    if language != 'en':
        campaign['content'] = translate_text(campaign['content'], language)
        campaign['title'] = translate_text(campaign['title'], language)
        campaign['overview'] = translate_text(campaign['overview'], language)
    
    return format_campaign_output(campaign['content'], complexity, language, campaign['title'])

def format_campaign_output(content, complexity, language, title=None):
    """Formats campaign output in standardized way"""
    
    session_counts = {'simple': '1-2', 'medium': '3-4', 'complex': '5+'}
    
    formatted = f"""
# 🎲 RPG CAMPAIGN - {complexity.upper()}
{'#' if not title else f'# {title}'}
**Duration**: {session_counts.get(complexity, '3-4')} sessions  
**Language**: {language}  
**Generated on**: {datetime.now().strftime('%d/%m/%Y %H:%M')}  
**Complexity**: {complexity.capitalize()}

---

{content}

---

*Campaign automatically generated from RPG book analysis.  
Balancing may need adjustments for your specific group.*
"""
    return formatted

def save_campaign_to_file(campaign_content, filename, language):
    """Saves campaign to markdown file"""
    try:
        safe_filename = secure_filename(filename)
        campaign_file = f"campaign_{safe_filename}_{int(time.time())}.md"
        campaign_path = os.path.join(app.config['CAMPAIGN_FOLDER'], campaign_file)
        
        with open(campaign_path, 'w', encoding='utf-8') as f:
            f.write(campaign_content)
        
        logger.info(f"Campaign saved: {campaign_path}")
        return campaign_file
    except Exception as e:
        logger.error(f"Error saving campaign: {e}")
        return None

@app.route('/generate-campaign', methods=['POST'])
@rate_limit(max_calls=3, window=60)  # 3 campaigns per minute
def generate_campaign():
    """Main endpoint to generate RPG campaigns"""
    logger.info("🎲 Receiving campaign generation request...")
    
    try:
        # Validations
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not file or not allowed_file(file.filename):
            return jsonify({'error': 'File type not supported. Use PDF only.'}), 400

        # Campaign parameters
        target_language = request.form.get('target_language', 'en')
        campaign_complexity = request.form.get('complexity', 'medium')
        
        if campaign_complexity not in ['simple', 'medium', 'complex']:
            return jsonify({'error': 'Complexity must be: simple, medium, or complex'}), 400

        logger.info(f"Parameters: Language={target_language}, Complexity={campaign_complexity}")

        # Save file
        filename = secure_filename(file.filename)
        input_pdf = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(input_pdf)

        # Validate PDF
        is_valid, validation_msg = validate_pdf(input_pdf)
        if not is_valid:
            os.remove(input_pdf)
            return jsonify({'error': validation_msg}), 400

        # Process
        logger.info("Extracting text from RPG book...")
        book_text = extract_text_from_pdf(input_pdf)
        
        if not book_text or len(book_text.strip()) < 100:
            os.remove(input_pdf)
            return jsonify({'error': 'Insufficient text extracted from PDF. File may be image-scanned.'}), 400

        logger.info("Analyzing book and generating campaign...")
        campaign_content = analyze_rpg_book_with_gemini(book_text, target_language, campaign_complexity)

        # Save campaign
        base_name = os.path.splitext(filename)[0]
        campaign_filename = save_campaign_to_file(campaign_content, base_name, target_language)

        # Clean temporary file
        try:
            os.remove(input_pdf)
        except:
            pass

        if campaign_filename:
            return jsonify({
                'success': True,
                'campaign_url': f'/download-campaign/{campaign_filename}',
                'message': f'{campaign_complexity.capitalize()} campaign generated successfully!',
                'preview': campaign_content[:500] + '...' if len(campaign_content) > 500 else campaign_content
            }), 200
        else:
            return jsonify({'error': 'Error saving campaign'}), 500

    except Exception as e:
        logger.error(f"Error generating campaign: {e}")
        # Clean file if exists
        if 'input_pdf' in locals() and os.path.exists(input_pdf):
            try:
                os.remove(input_pdf)
            except:
                pass
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500

@app.route('/download-campaign/<filename>')
def download_campaign(filename):
    """Download generated campaign"""
    try:
        return send_from_directory(app.config['CAMPAIGN_FOLDER'], filename, 
                                 as_attachment=True, 
                                 download_name=f"rpg_campaign_{filename}")
    except Exception as e:
        logger.error(f"Error downloading campaign: {e}")
        return jsonify({'error': 'Campaign not found'}), 404

@app.route('/campaign-complexities', methods=['GET'])
def get_campaign_complexities():
    """Returns available campaign complexities"""
    complexities = {
        'simple': {
            'name': 'Simple Campaign',
            'sessions': '1-2 sessions',
            'description': 'Direct and objective story, perfect for oneshots or introductions',
            'duration': '3-8 hours total',
            'focus': 'Combat and clear objectives'
        },
        'medium': {
            'name': 'Medium Campaign', 
            'sessions': '3-4 sessions',
            'description': 'Balance between combat, exploration and character development',
            'duration': '9-16 hours total',
            'focus': 'Story with branches and choices'
        },
        'complex': {
            'name': 'Complex Campaign',
            'sessions': '5+ sessions',
            'description': 'Epic arc with multiple paths and consequences',
            'duration': '17+ hours total', 
            'focus': 'Deep narrative and character development'
        }
    }
    return jsonify(complexities)

@app.route('/supported-languages', methods=['GET'])
def get_supported_languages():
    """Returns supported languages for campaigns"""
    languages = {
        'en': 'English',
        'pt': 'Português', 
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
    """API status"""
    return jsonify({
        'status': 'online',
        'service': 'RPG Campaign Generator',
        'supported_formats': list(ALLOWED_EXTENSIONS),
        'max_file_size_mb': MAX_FILE_SIZE // (1024 * 1024),
        'gemini_configured': GEMINI_CONFIGURED
    })

@app.route('/example-campaign', methods=['GET'])
def get_example_campaign():
    """Returns a campaign example without upload"""
    try:
        complexity = request.args.get('complexity', 'medium')
        language = request.args.get('language', 'en')
        
        example = generate_fallback_campaign(complexity, language)
        
        return jsonify({
            'success': True,
            'complexity': complexity,
            'language': language,
            'content': example,
            'message': 'Example campaign generated'
        })
        
    except Exception as e:
        logger.error(f"Error generating example: {e}")
        return jsonify({'error': 'Error generating example'}), 500

def cleanup_old_files():
    """Removes old files (older than 24 hours)"""
    try:
        now = time.time()
        for folder in [UPLOAD_FOLDER, CAMPAIGN_FOLDER]:
            if os.path.exists(folder):
                for filename in os.listdir(folder):
                    file_path = os.path.join(folder, filename)
                    if os.path.isfile(file_path):
                        if now - os.path.getmtime(file_path) > 86400:  # 24 hours
                            os.remove(file_path)
                            logger.info(f"Old file removed: {file_path}")
    except Exception as e:
        logger.warning(f"Cleanup error: {e}")

if __name__ == '__main__':
    cleanup_old_files()
    logger.info("🚀 Server started - RPG Campaign Generator")
    print("""
    🎲 RPG CAMPAIGN GENERATOR 🎲
    ===========================
    Service: Transforming RPG books into ready-to-play campaigns
    Endpoints:
    - POST /generate-campaign   → Generate campaign from PDF
    - GET  /example-campaign    → Example without upload
    - GET  /campaign-complexities → Campaign types
    - GET  /supported-languages → Available languages
    """)
    app.run(host='0.0.0.0', port=5000, debug=False)