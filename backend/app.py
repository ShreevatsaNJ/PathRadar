import os
import sqlite3
import json
import uuid
import unicodedata
from flask import Flask, request, jsonify, send_file, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import datetime

# Import our ML/NLP model logic
from model import (
    extract_text, analyze_resume_vs_jd, extract_skills_nlp,
    analyze_skill_clusters, calculate_transferability,
    detect_best_industries, detect_best_roles, analyze_multi_role,
    build_learning_path, filter_apply_jobs, generate_course_links,
    INDUSTRY_ROLES, INDUSTRY_SKILL_CLUSTERS, SKILL_CLUSTERS_MAP
)

# Import JSearch API integration
from job_fetcher import (
    fetch_jobs_by_role, get_combined_job_description,
    fetch_jobs_for_multiple_roles, fetch_jobs_for_industry
)

# Import dashboard chart generator
from dashboard_generator import (
    generate_role_match_chart, generate_skill_cluster_chart,
    generate_industry_fit_chart, generate_learning_mindmap_chart,
    generate_full_dashboard
)

# Import course fetcher (YouTube Data API + platform search links)
from course_fetcher import fetch_courses_for_skill

app = Flask(__name__, static_folder='../frontend', static_url_path='')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'pathradar_secret_key_9988')

# Session cookies on credentialed fetch:
# SameSite=Lax omits the cookie when the UI origin and API origin differ (e.g. :5500 vs :5000),
# so analyses save with user_id NULL and history stays empty. None fixes local cross-port dev;
# in production use HTTPS and set SESSION_COOKIE_SECURE=true (and keep SameSite=None or use one host).
_app_samesite = os.environ.get('SESSION_COOKIE_SAMESITE', 'None')
_app_secure = os.environ.get('SESSION_COOKIE_SECURE', '').lower() in ('1', 'true', 'yes')
app.config.update(
    SESSION_COOKIE_SAMESITE=_app_samesite,
    SESSION_COOKIE_SECURE=_app_secure,
    SESSION_COOKIE_HTTPONLY=True,
    PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=7)
)

CORS(app, supports_credentials=True, resources={r"/api/*": {
    "origins": [
        "http://localhost:5000", "http://127.0.0.1:5000",
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:5500", "http://127.0.0.1:5500",
        "http://localhost:8080", "http://127.0.0.1:8080",
        "null",
    ],
    "allow_headers": ["Content-Type", "Authorization"],
}})

# Paths relative to this file so DB/uploads are stable regardless of cwd
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)

# Configuration
UPLOAD_FOLDER = os.path.join(_PROJECT_ROOT, 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'txt', 'docx', 'doc'}
DATABASE = os.path.join(_PROJECT_ROOT, 'database.db')


def _normalize_upload_name(name):
    """Strip invisible Unicode / BOM so extensions like .doc are detected reliably."""
    if name is None:
        return ''
    s = unicodedata.normalize('NFKC', str(name))
    for ch in ('\x00', '\ufeff', '\u200b', '\u200c', '\u200d'):
        s = s.replace(ch, '')
    return s.strip()


def invalid_resume_file_type_response():
    kinds = ', '.join(sorted(ALLOWED_EXTENSIONS))
    return jsonify({
        'error': (
            f'Invalid resume file type. Allowed extensions: {kinds}. '
            'If this list looks wrong, stop all Flask/Python processes and start the app again from the PathRadar folder.'
        )
    }), 400


app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

_AUTH_TOKEN_MAX_AGE = int(datetime.timedelta(days=7).total_seconds())


def _auth_signer():
    return URLSafeTimedSerializer(app.secret_key, salt='pathradar-auth-v1')


def make_auth_token(user_id):
    return _auth_signer().dumps({'uid': user_id})


def read_auth_token(token):
    if not token or not isinstance(token, str):
        return None
    try:
        data = _auth_signer().loads(token, max_age=_AUTH_TOKEN_MAX_AGE)
        uid = data.get('uid')
        return int(uid) if uid is not None else None
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None


def bearer_auth_token():
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return (auth[7:].strip() or None)
    return None


def effective_user_id():
    """Logged-in user from Bearer token (works cross-origin) or Flask session cookie."""
    uid = read_auth_token(bearer_auth_token())
    if uid is not None:
        return uid
    return session.get('user_id')


@app.route('/')
def index():
    """Serve the main frontend page."""
    return send_file('../frontend/index.html')


def allowed_file(filename):
    """Check if the uploaded file has a permitted extension (segment after the last dot)."""
    name = _normalize_upload_name(filename)
    if not name or '.' not in name:
        return False
    ext = name.rsplit('.', 1)[-1].lower().strip()
    return ext in ALLOWED_EXTENSIONS


def sanitize_display_filename(name, max_len=200):
    """Name shown in UI / stored in DB: keeps spaces, strips path junk."""
    if not name:
        return 'resume'
    base = os.path.basename(_normalize_upload_name(name))
    base = base.replace('\\', '').replace('/', '')
    if not base or base in ('.', '..'):
        return 'resume'
    return base[:max_len]


def unique_storage_path(upload_folder, display_name):
    """Filesystem path that is unique and safe (Werkzeug + short UUID prefix)."""
    safe = secure_filename(display_name)
    ext = display_name.rsplit('.', 1)[-1].lower() if '.' in display_name else 'dat'
    if not safe or safe == f'.{ext}' or not safe.strip('.'):
        safe = f'resume_{uuid.uuid4().hex[:16]}.{ext}'
    candidate = f'{uuid.uuid4().hex[:10]}_{safe}'
    return os.path.join(upload_folder, candidate)


def get_db_connection():
    """Establish a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database with the required tables and schema updates."""
    conn = get_db_connection()
    
    # Users table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Main analysis sessions table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS analysis_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            filename TEXT NOT NULL,
            resume_skills TEXT,
            skill_cluster_distribution TEXT,
            industries_detected TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Check if user_id column exists (for backward compatibility if DB already exists)
    try:
        conn.execute('SELECT user_id FROM analysis_sessions LIMIT 1')
    except sqlite3.OperationalError:
        conn.execute('ALTER TABLE analysis_sessions ADD COLUMN user_id INTEGER')

    # Per-role results table (many per session)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS role_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            job_role TEXT NOT NULL,
            industry TEXT,
            match_percentage REAL NOT NULL,
            ai_semantic_similarity REAL NOT NULL,
            matched_skills TEXT,
            missing_skills TEXT,
            recommendations TEXT,
            transferability_data TEXT,
            apply_at TEXT,
            jobs_analyzed INTEGER DEFAULT 0,
            FOREIGN KEY (session_id) REFERENCES analysis_sessions(id)
        )
    ''')
    
    conn.commit()
    conn.close()


# Initialize DB when the app starts
init_db()
print(f'PathRadar: resume uploads accept extensions {sorted(ALLOWED_EXTENSIONS)}')


# =============================================================================
# Helper: Extract resume and validate
# =============================================================================
def _extract_resume(req):
    """Common resume upload + text extraction logic. Returns (filepath, filename, resume_text) or error response."""
    if 'resume' not in req.files:
        return None, None, None, (jsonify({'error': 'No resume part in the request'}), 400)
    
    file = req.files['resume']
    if not file.filename or str(file.filename).strip() == '':
        return None, None, None, (jsonify({'error': 'No selected file'}), 400)
    
    if not file or not allowed_file(file.filename):
        return None, None, None, invalid_resume_file_type_response()

    display_name = sanitize_display_filename(file.filename)
    if not allowed_file(display_name):
        return None, None, None, invalid_resume_file_type_response()

    filepath = unique_storage_path(app.config['UPLOAD_FOLDER'], display_name)
    file.save(filepath)

    resume_text = extract_text(filepath)
    ext = os.path.splitext(display_name)[1].lower()
    if not resume_text or len(resume_text.strip()) < 10:
        try:
            os.unlink(filepath)
        except OSError:
            pass
        if ext == '.doc':
            return None, None, None, (jsonify({
                'error': 'Could not read this .doc file. Open it in Microsoft Word and use File → Save As → Word Document (.docx), or install LibreOffice so PathRadar can convert it.'
            }), 400)
        return None, None, None, (jsonify({'error': 'Could not extract text. Please upload a clearer image, PDF, or DOCX.'}), 400)

    return filepath, display_name, resume_text, None


# =============================================================================
# AUTHENTICATION ROUTES
# =============================================================================

@app.route('/api/signup', methods=['POST'])
def signup():
    """Register a new user."""
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    full_name = data.get('full_name', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    conn = get_db_connection()
    try:
        password_hash = generate_password_hash(password)
        conn.execute(
            'INSERT INTO users (email, password_hash, full_name) VALUES (?, ?, ?)',
            (email, password_hash, full_name)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Email already exists'}), 400
    finally:
        conn.close()

    return jsonify({'status': 'success', 'message': 'User registered successfully'}), 201


@app.route('/api/login', methods=['POST'])
def login():
    """Authenticate user and start session."""
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()

    if user and check_password_hash(user['password_hash'], password):
        session.clear()
        session.permanent = True
        session['user_id'] = user['id']
        session['email'] = user['email']
        session['full_name'] = user['full_name']
        return jsonify({
            'status': 'success',
            'token': make_auth_token(user['id']),
            'user': {
                'id': user['id'],
                'email': user['email'],
                'full_name': user['full_name']
            }
        }), 200

    return jsonify({'error': 'Invalid email or password'}), 401


@app.route('/api/logout', methods=['POST'])
def logout():
    """Clear user session."""
    session.clear()
    return jsonify({'status': 'success', 'message': 'Logged out successfully'}), 200


@app.route('/api/user', methods=['GET'])
def get_current_user():
    """Get current logged in user (session cookie or Authorization: Bearer token)."""
    uid = effective_user_id()
    if not uid:
        return jsonify({'status': 'guest'}), 200
    conn = get_db_connection()
    user = conn.execute(
        'SELECT id, email, full_name FROM users WHERE id = ?', (uid,)
    ).fetchone()
    conn.close()
    if not user:
        return jsonify({'status': 'guest'}), 200
    return jsonify({
        'status': 'success',
        'user': {
            'id': user['id'],
            'email': user['email'],
            'full_name': user['full_name']
        }
    }), 200


# =============================================================================
# POST /api/analyze — Main endpoint: multi-role analysis via API
# =============================================================================
@app.route('/api/analyze', methods=['POST'])
def analyze():
    """
    Upload resume + specify roles and location.
    Fetches live JDs from JSearch API, compares resume against each role,
    returns per-role results with skill clustering and transferability.
    
    Form data:
        resume (file): Resume file (PDF/DOCX/PNG/JPG/TXT)
        roles (str): Comma-separated roles, OR leave empty for auto-detection
        location (str): Location filter (default: India)
    """
    filepath, filename, resume_text, error = _extract_resume(request)
    if error:
        return error
    
    location = request.form.get('location', 'India')
    roles_input = request.form.get('roles', '').strip()
    
    # Extract resume skills first
    resume_skills = extract_skills_nlp(resume_text)
    
    # Determine roles to analyze
    if roles_input:
        # User specified roles manually
        role_names = [r.strip() for r in roles_input.split(',') if r.strip()]
        roles_list = [{"role": r, "industry": "User Specified"} for r in role_names]
    else:
        # Auto-detect best roles from resume skills
        suggested = detect_best_roles(resume_skills)
        if not suggested:
            return jsonify({'error': 'Could not detect suitable roles from your resume. Please specify roles manually.'}), 400
        roles_list = suggested[:6]  # Top 6 roles
    
    # Fetch JDs from API for all roles
    fetch_result = fetch_jobs_for_multiple_roles(roles_list, location)
    roles_data = fetch_result["roles_data"]
    
    if not roles_data:
        errors_msg = "; ".join([e["error"] for e in fetch_result.get("errors", [])])
        return jsonify({'error': f'Could not fetch jobs for any role. {errors_msg}'}), 500
    
    # Run multi-role analysis
    analysis = analyze_multi_role(resume_text, roles_data)
    
    # Detect best industries
    industries = detect_best_industries(resume_skills)
    
    # Store session in DB
    user_id = effective_user_id()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO analysis_sessions (user_id, filename, resume_skills, skill_cluster_distribution, industries_detected)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        user_id,
        filename,
        json.dumps(analysis["resume_skills"]),
        json.dumps(analysis["skill_clusters"]),
        json.dumps(industries)
    ))
    session_id = cursor.lastrowid
    
    # Store each role result
    for role_result in analysis["role_results"]:
        cursor.execute('''
            INSERT INTO role_results 
            (session_id, job_role, industry, match_percentage, ai_semantic_similarity,
             matched_skills, missing_skills, recommendations, transferability_data, apply_at, jobs_analyzed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session_id,
            role_result["role"],
            role_result["industry"],
            role_result["match_percentage"],
            role_result["ai_semantic_similarity"],
            ', '.join(role_result["matched_skills"]),
            ', '.join(role_result["missing_skills"]),
            ' | '.join(role_result["recommendations"]),
            json.dumps(role_result["transferability"]),
            json.dumps(role_result["apply_at"]),
            role_result["jobs_analyzed"]
        ))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'status': 'success',
        'session_id': session_id,
        'resume_skills': analysis["resume_skills"],
        'skill_clusters': analysis["skill_clusters"],
        'best_industries': industries[:5],
        'roles_analyzed': len(analysis["role_results"]),
        'fetch_errors': fetch_result.get("errors", []),
        'role_results': analysis["role_results"]
    }), 201


# =============================================================================
# POST /api/analyze-industry — Analyze resume across entire industries
# =============================================================================
@app.route('/api/analyze-industry', methods=['POST'])
def analyze_industry():
    """
    Upload resume + specify industries. Auto-maps to roles, fetches JDs,
    runs analysis per industry+role.
    
    Form data:
        resume (file): Resume file
        industries (str): Comma-separated industries (from INDUSTRY_ROLES keys)
        location (str): Location filter (default: India)
    """
    filepath, filename, resume_text, error = _extract_resume(request)
    if error:
        return error
    
    location = request.form.get('location', 'India')
    industries_input = request.form.get('industries', '').strip()
    
    resume_skills = extract_skills_nlp(resume_text)
    
    if industries_input:
        selected_industries = [i.strip() for i in industries_input.split(',') if i.strip()]
    else:
        # Auto-detect top industries
        detected = detect_best_industries(resume_skills)
        selected_industries = [d["industry"] for d in detected[:4]]
    
    if not selected_industries:
        return jsonify({'error': 'No industries detected. Please specify industries manually.'}), 400
    
    # Build roles list from industries (limit to 2 roles per industry to save API calls)
    roles_list = []
    for industry in selected_industries:
        industry_role_list = INDUSTRY_ROLES.get(industry, [])
        for role in industry_role_list[:2]:
            roles_list.append({"role": role, "industry": industry})
    
    # Fetch and analyze
    fetch_result = fetch_jobs_for_multiple_roles(roles_list, location)
    roles_data = fetch_result["roles_data"]
    
    if not roles_data:
        return jsonify({'error': 'Could not fetch jobs for any industry role.'}), 500
    
    analysis = analyze_multi_role(resume_text, roles_data)
    industries_detected = detect_best_industries(resume_skills)
    
    # Store in DB
    user_id = effective_user_id()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO analysis_sessions (user_id, filename, resume_skills, skill_cluster_distribution, industries_detected)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        user_id,
        filename,
        json.dumps(analysis["resume_skills"]),
        json.dumps(analysis["skill_clusters"]),
        json.dumps(industries_detected)
    ))
    session_id = cursor.lastrowid
    
    for role_result in analysis["role_results"]:
        cursor.execute('''
            INSERT INTO role_results 
            (session_id, job_role, industry, match_percentage, ai_semantic_similarity,
             matched_skills, missing_skills, recommendations, transferability_data, apply_at, jobs_analyzed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session_id,
            role_result["role"],
            role_result["industry"],
            role_result["match_percentage"],
            role_result["ai_semantic_similarity"],
            ', '.join(role_result["matched_skills"]),
            ', '.join(role_result["missing_skills"]),
            ' | '.join(role_result["recommendations"]),
            json.dumps(role_result["transferability"]),
            json.dumps(role_result["apply_at"]),
            role_result["jobs_analyzed"]
        ))
    
    conn.commit()
    conn.close()
    
    # Group results by industry for cleaner output
    industry_grouped = {}
    for r in analysis["role_results"]:
        ind = r["industry"]
        if ind not in industry_grouped:
            industry_grouped[ind] = []
        industry_grouped[ind].append(r)
    
    return jsonify({
        'status': 'success',
        'session_id': session_id,
        'resume_skills': analysis["resume_skills"],
        'skill_clusters': analysis["skill_clusters"],
        'best_industries': industries_detected[:5],
        'industry_results': industry_grouped,
        'fetch_errors': fetch_result.get("errors", [])
    }), 201


# =============================================================================
# POST /api/suggest-roles — Auto-detect best roles from resume
# =============================================================================
@app.route('/api/suggest-roles', methods=['POST'])
def suggest_roles():
    """
    Upload resume, returns auto-detected best-fit roles and industries.
    No API calls — purely skill-based matching against our internal database.
    """
    filepath, filename, resume_text, error = _extract_resume(request)
    if error:
        return error
    
    resume_skills = extract_skills_nlp(resume_text)
    skill_clusters = analyze_skill_clusters(resume_skills)
    best_industries = detect_best_industries(resume_skills)
    best_roles = detect_best_roles(resume_skills)
    
    return jsonify({
        'status': 'success',
        'resume_skills': resume_skills,
        'skill_clusters': skill_clusters,
        'best_industries': best_industries,
        'suggested_roles': best_roles
    }), 200


# =============================================================================
# GET /api/industry-skills — List industries and their required skills
# =============================================================================
@app.route('/api/industry-skills', methods=['GET'])
def get_industry_skills():
    """Returns the mapping of industries to their required skills."""
    return jsonify({
        'status': 'success',
        'industry_clusters': INDUSTRY_SKILL_CLUSTERS,
        'skill_clusters': SKILL_CLUSTERS_MAP
    }), 200


# =============================================================================
# GET /api/fetch-jobs — Preview live job listings
# =============================================================================
@app.route('/api/fetch-jobs', methods=['GET'])
def fetch_jobs():
    """
    Fetch live job listings from LinkedIn, Indeed, Glassdoor etc.
    
    Query params:
        role (str): Job role to search (required)
        location (str): Location filter (default: India)
    """
    job_role = request.args.get('role', '')
    location = request.args.get('location', 'India')
    
    if not job_role:
        return jsonify({'error': 'Please provide a role. Example: /api/fetch-jobs?role=Data Analyst'}), 400

    jobs = fetch_jobs_by_role(job_role, location)
    
    if isinstance(jobs, dict) and "error" in jobs:
        return jsonify(jobs), 500
    
    return jsonify({
        'status': 'success',
        'count': len(jobs),
        'job_role': job_role,
        'location': location,
        'data': jobs
    }), 200


# =============================================================================
# GET /api/result/<session_id> — Fetch full analysis session
# =============================================================================
@app.route('/api/result/<int:session_id>', methods=['GET'])
def get_result(session_id):
    """Fetch the complete analysis results for a session."""
    conn = get_db_connection()
    
    session = conn.execute('SELECT * FROM analysis_sessions WHERE id = ?', (session_id,)).fetchone()
    if session is None:
        conn.close()
        return jsonify({'error': 'Session not found!'}), 404
    
    roles = conn.execute('SELECT * FROM role_results WHERE session_id = ? ORDER BY match_percentage DESC', (session_id,)).fetchall()
    conn.close()
    
    session_data = dict(session)
    session_data['resume_skills'] = json.loads(session_data['resume_skills']) if session_data['resume_skills'] else []
    session_data['skill_cluster_distribution'] = json.loads(session_data['skill_cluster_distribution']) if session_data['skill_cluster_distribution'] else {}
    session_data['industries_detected'] = json.loads(session_data['industries_detected']) if session_data['industries_detected'] else []
    
    role_results = []
    for role in roles:
        rd = dict(role)
        rd['matched_skills'] = rd['matched_skills'].split(', ') if rd['matched_skills'] else []
        rd['missing_skills'] = rd['missing_skills'].split(', ') if rd['missing_skills'] else []
        rd['recommendations'] = rd['recommendations'].split(' | ') if rd['recommendations'] else []
        rd['transferability_data'] = json.loads(rd['transferability_data']) if rd['transferability_data'] else []
        rd['apply_at'] = json.loads(rd['apply_at']) if rd['apply_at'] else []
        role_results.append(rd)
    
    return jsonify({
        'status': 'success',
        'session': session_data,
        'role_results': role_results
    }), 200


# =============================================================================
# GET /api/skill-clusters/<session_id> — Skill clustering breakdown
# =============================================================================
@app.route('/api/skill-clusters/<int:session_id>', methods=['GET'])
def get_skill_clusters(session_id):
    """Returns the skill clustering breakdown for a specific session."""
    conn = get_db_connection()
    session = conn.execute('SELECT skill_cluster_distribution, resume_skills FROM analysis_sessions WHERE id = ?', (session_id,)).fetchone()
    conn.close()
    
    if session is None:
        return jsonify({'error': 'Session not found!'}), 404
    
    return jsonify({
        'status': 'success',
        'resume_skills': json.loads(session['resume_skills']) if session['resume_skills'] else [],
        'skill_clusters': json.loads(session['skill_cluster_distribution']) if session['skill_cluster_distribution'] else {}
    }), 200


# =============================================================================
# GET /api/transferability/<session_id> — Skill transferability for a session
# =============================================================================
@app.route('/api/transferability/<int:session_id>', methods=['GET'])
def get_transferability(session_id):
    """Returns skill transferability analysis for all roles in a session."""
    conn = get_db_connection()
    
    session = conn.execute('SELECT * FROM analysis_sessions WHERE id = ?', (session_id,)).fetchone()
    if session is None:
        conn.close()
        return jsonify({'error': 'Session not found!'}), 404
    
    roles = conn.execute('SELECT job_role, industry, transferability_data, missing_skills FROM role_results WHERE session_id = ?', (session_id,)).fetchall()
    conn.close()
    
    results = []
    for role in roles:
        rd = dict(role)
        rd['transferability_data'] = json.loads(rd['transferability_data']) if rd['transferability_data'] else []
        rd['missing_skills'] = rd['missing_skills'].split(', ') if rd['missing_skills'] else []
        results.append(rd)
    
    return jsonify({
        'status': 'success',
        'session_id': session_id,
        'resume_skills': json.loads(session['resume_skills']) if session['resume_skills'] else [],
        'role_transferability': results
    }), 200


# =============================================================================
# POST /api/claim-session — Link a guest session to the current user
# =============================================================================
@app.route('/api/claim-session', methods=['POST'])
def claim_session():
    """Link an anonymous analysis session to the logged-in user."""
    user_id = effective_user_id()
    if not user_id:
        return jsonify({'error': 'Login required to claim history'}), 401

    data = request.json
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({'error': 'session_id is required'}), 400

    conn = get_db_connection()
    # Only allow claiming if it doesn't already belong to someone else
    existing = conn.execute('SELECT user_id FROM analysis_sessions WHERE id = ?', (session_id,)).fetchone()
    
    if not existing:
        conn.close()
        return jsonify({'error': 'Session not found'}), 404
        
    if existing['user_id'] is not None and existing['user_id'] != user_id:
        conn.close()
        return jsonify({'error': 'Session already belongs to another user'}), 403

    conn.execute('UPDATE analysis_sessions SET user_id = ? WHERE id = ?', (user_id, session_id))
    conn.commit()
    conn.close()

    return jsonify({'status': 'success', 'message': 'Session linked to your account'}), 200


# =============================================================================
# GET /api/dashboard — History of all analysis sessions
# =============================================================================
@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    """Fetch a history of past analysis sessions for the logged-in user."""
    user_id = effective_user_id()
    if not user_id:
        return jsonify({
            'status': 'success',
            'count': 0,
            'data': [],
            'message': 'Login to see your analysis history'
        }), 200

    conn = get_db_connection()
    sessions = conn.execute(
        'SELECT * FROM analysis_sessions WHERE user_id = ? ORDER BY created_at DESC',
        (user_id,)
    ).fetchall()
    
    dashboard = []
    for row in sessions:
        sd = dict(row)
        sd['resume_skills'] = json.loads(sd['resume_skills']) if sd['resume_skills'] else []
        sd['industries_detected'] = json.loads(sd['industries_detected']) if sd['industries_detected'] else []
        
        # Get role results summary
        roles = conn.execute(
            'SELECT job_role, industry, match_percentage FROM role_results WHERE session_id = ? ORDER BY match_percentage DESC',
            (sd['id'],)
        ).fetchall()
        sd['roles_summary'] = [dict(r) for r in roles]
        sd['best_match'] = dict(roles[0]) if roles else None
        
        dashboard.append(sd)
    
    conn.close()
    
    return jsonify({
        'status': 'success',
        'count': len(dashboard),
        'data': dashboard
    }), 200


# =============================================================================
# GET /api/apply-jobs/<session_id> — Jobs with ≥70% match, ascending order
# =============================================================================
@app.route('/api/apply-jobs/<int:session_id>', methods=['GET'])
def get_apply_jobs(session_id):
    """
    Returns roles where match ≥ 70% with apply links in ascending order.
    Roles below 70% are listed separately as 'need_upskilling'.
    """
    conn = get_db_connection()
    session = conn.execute('SELECT * FROM analysis_sessions WHERE id = ?', (session_id,)).fetchone()
    if session is None:
        conn.close()
        return jsonify({'error': 'Session not found!'}), 404
    
    roles = conn.execute('SELECT * FROM role_results WHERE session_id = ?', (session_id,)).fetchall()
    conn.close()
    
    role_list = []
    for role in roles:
        rd = dict(role)
        rd['matched_skills'] = rd['matched_skills'].split(', ') if rd['matched_skills'] else []
        rd['missing_skills'] = rd['missing_skills'].split(', ') if rd['missing_skills'] else []
        rd['apply_at'] = json.loads(rd['apply_at']) if rd['apply_at'] else []
        role_list.append(rd)
    
    threshold = int(request.args.get('threshold', 70))
    result = filter_apply_jobs(role_list, threshold)
    
    return jsonify({
        'status': 'success',
        'session_id': session_id,
        **result
    }), 200


# =============================================================================
# GET /api/learning-path/<session_id> — Learning mindmap with course links
# =============================================================================
@app.route('/api/learning-path/<int:session_id>', methods=['GET'])
def get_learning_path(session_id):
    """
    Returns a structured learning path for missing skills.
    Groups skills by cluster, orders by difficulty (easy first),
    and provides course links (Coursera, Udemy, YouTube) for each skill.
    
    Optional query param: role (filter to a specific role's missing skills)
    """
    conn = get_db_connection()
    session = conn.execute('SELECT * FROM analysis_sessions WHERE id = ?', (session_id,)).fetchone()
    if session is None:
        conn.close()
        return jsonify({'error': 'Session not found!'}), 404
    
    resume_skills = json.loads(session['resume_skills']) if session['resume_skills'] else []
    
    # Get missing skills — either for a specific role or all roles combined
    role_filter = request.args.get('role', '')
    
    if role_filter:
        roles = conn.execute(
            'SELECT missing_skills FROM role_results WHERE session_id = ? AND job_role = ?',
            (session_id, role_filter)
        ).fetchall()
    else:
        roles = conn.execute(
            'SELECT missing_skills FROM role_results WHERE session_id = ?',
            (session_id,)
        ).fetchall()
    conn.close()
    
    # Combine all missing skills (deduplicated)
    all_missing = set()
    for role in roles:
        if role['missing_skills']:
            for skill in role['missing_skills'].split(', '):
                if skill.strip():
                    all_missing.add(skill.strip())
    
    learning_path = build_learning_path(list(all_missing), resume_skills)
    
    return jsonify({
        'status': 'success',
        'session_id': session_id,
        'role_filter': role_filter or 'all_roles',
        'learning_path': learning_path
    }), 200


# =============================================================================
# GET /api/dashboard-chart/<session_id> — Matplotlib generated charts
# =============================================================================
@app.route('/api/dashboard-chart/<int:session_id>', methods=['GET'])
def get_dashboard_chart(session_id):
    """
    Generate and return a matplotlib chart.
    
    Query param 'type': 
        'roles' — match % bar chart
        'clusters' — skill cluster pie chart
        'industries' — industry fit bar chart
        'mindmap' — learning roadmap visualization
        'full' — combined 2x2 dashboard (default)
    """
    conn = get_db_connection()
    session = conn.execute('SELECT * FROM analysis_sessions WHERE id = ?', (session_id,)).fetchone()
    if session is None:
        conn.close()
        return jsonify({'error': 'Session not found!'}), 404
    
    roles = conn.execute(
        'SELECT * FROM role_results WHERE session_id = ? ORDER BY match_percentage DESC',
        (session_id,)
    ).fetchall()
    conn.close()
    
    role_results = [dict(r) for r in roles]
    skill_clusters = json.loads(session['skill_cluster_distribution']) if session['skill_cluster_distribution'] else {}
    industries = json.loads(session['industries_detected']) if session['industries_detected'] else []
    resume_skills = json.loads(session['resume_skills']) if session['resume_skills'] else []
    
    chart_type = request.args.get('type', 'full')
    
    # Build learning path for mindmap/full charts
    all_missing = set()
    for role in role_results:
        if role.get('missing_skills'):
            for skill in role['missing_skills'].split(', '):
                if skill.strip():
                    all_missing.add(skill.strip())
    learning_path = build_learning_path(list(all_missing), resume_skills)
    
    # Generate requested chart
    if chart_type == 'roles':
        path = generate_role_match_chart(session_id, role_results)
    elif chart_type == 'clusters':
        path = generate_skill_cluster_chart(session_id, skill_clusters)
    elif chart_type == 'industries':
        path = generate_industry_fit_chart(session_id, industries)
    elif chart_type == 'mindmap':
        path = generate_learning_mindmap_chart(session_id, learning_path)
    else:  # 'full' — combined dashboard
        path = generate_full_dashboard(session_id, role_results, skill_clusters, industries, learning_path)
    
    if path is None:
        return jsonify({'error': 'Not enough data to generate chart.'}), 400
    
    return send_file(path, mimetype='image/png')


# =============================================================================
# GET /api/course-links — Fetch real YouTube video + platform search links for a skill
# =============================================================================
@app.route('/api/course-links', methods=['GET'])
def get_course_links():
    """
    Returns a real YouTube video URL (via YouTube Data API) and platform search
    links for Udemy, Coursera, freeCodeCamp for a given skill.

    Query param:
        skill (str): The skill to search for (required)
    """
    skill = request.args.get('skill', '').strip()
    if not skill:
        return jsonify({'error': 'Please provide a skill. Example: /api/course-links?skill=Python'}), 400

    try:
        links = fetch_courses_for_skill(skill)
        return jsonify({
            'status': 'success',
            'skill': skill,
            'links': links
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Use the PORT environment variable if available (for cloud deployment)
    port = int(os.environ.get("PORT", 5000))
    # In production, debug should be False. host='0.0.0.0' allows external access.
    app.run(debug=False, host='0.0.0.0', port=port)
