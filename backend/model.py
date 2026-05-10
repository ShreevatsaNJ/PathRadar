import pdfplumber
import re
import pytesseract
from PIL import Image
import os
import math
import json
from collections import Counter

# =============================================================================
# SKILL DATABASE — Organized by Cluster (Category)
# =============================================================================
SKILL_CLUSTERS_MAP = {
    "Programming Languages": [
        "python", "java", "c++", "c#", "ruby", "javascript", "typescript",
        "go", "rust", "php", "swift", "kotlin", "r", "scala", "perl", "matlab"
    ],
    "Web Frontend": [
        "html", "css", "react", "angular", "vue", "svelte", "next.js",
        "bootstrap", "sass", "webpack", "figma", "ui design", "ux design",
        "responsive design", "jquery"
    ],
    "Web Backend": [
        "node.js", "django", "flask", "spring boot", "express.js", "fastapi",
        "rest api", "graphql", "microservices", "laravel", "ruby on rails"
    ],
    "Cloud & DevOps": [
        "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "jenkins",
        "ci/cd", "linux", "bash", "ansible", "nginx", "heroku", "vercel"
    ],
    "Data & Analytics": [
        "sql", "nosql", "mongodb", "postgresql", "mysql", "redis", "pandas",
        "numpy", "power bi", "tableau", "excel", "data visualization",
        "data warehousing", "etl", "apache spark", "hadoop", "data modeling",
        "statistics", "google analytics", "data mining"
    ],
    "AI & Machine Learning": [
        "machine learning", "deep learning", "nlp", "artificial intelligence",
        "data science", "scikit-learn", "tensorflow", "keras", "pytorch",
        "computer vision", "neural networks", "reinforcement learning",
        "generative ai", "large language models"
    ],
    "Cybersecurity": [
        "network security", "penetration testing", "ethical hacking",
        "firewall", "encryption", "siem", "vulnerability assessment",
        "incident response", "compliance", "iso 27001", "soc", "threat analysis"
    ],
    "Management & Leadership": [
        "project management", "team leadership", "strategic planning",
        "operations management", "stakeholder management", "budgeting",
        "kpi tracking", "change management", "resource planning",
        "business development", "decision making", "risk management",
        "people management", "performance management", "agile", "scrum",
        "six sigma", "lean management", "pmp"
    ],
    "Marketing & Digital": [
        "digital marketing", "seo", "sem", "content marketing",
        "social media marketing", "email marketing", "copywriting",
        "brand management", "market research", "google ads",
        "facebook ads", "influencer marketing", "affiliate marketing",
        "marketing strategy", "public relations", "crm"
    ],
    "Sales & Business": [
        "negotiation", "lead generation", "cold calling", "account management",
        "sales forecasting", "pipeline management", "b2b sales", "b2c sales",
        "salesforce", "client relationship", "revenue growth",
        "business analysis", "contract negotiation", "retail sales"
    ],
    "Finance & Accounting": [
        "financial analysis", "accounting", "financial modeling",
        "investment banking", "auditing", "taxation", "bookkeeping",
        "tally", "sap", "bloomberg", "portfolio management",
        "credit analysis", "financial reporting", "cost accounting",
        "mutual funds", "stock market", "gst", "balance sheet"
    ],
    "Healthcare & Medical": [
        "patient care", "medical terminology", "electronic health records",
        "hipaa", "clinical research", "nursing", "pharmacology",
        "diagnostics", "telemedicine", "healthcare management",
        "medical coding", "first aid", "cpr", "anatomy", "physiology",
        "public health", "epidemiology"
    ],
    "Teaching & Education": [
        "curriculum development", "lesson planning", "classroom management",
        "educational technology", "student assessment", "online teaching",
        "tutoring", "mentoring", "special education", "pedagogy",
        "e-learning", "instructional design", "training and development"
    ],
    "Culinary & Food": [
        "food safety", "menu planning", "knife skills", "culinary arts",
        "baking", "food presentation", "nutrition", "haccp",
        "kitchen management", "food hygiene", "pastry", "catering",
        "food cost control", "recipe development", "cuisines"
    ],
    "Hospitality & Hotel": [
        "front desk", "guest relations", "housekeeping",
        "reservation management", "hospitality management", "event planning",
        "concierge", "food and beverage", "hotel operations",
        "customer satisfaction", "banquet management", "travel management"
    ],
    "Logistics & Delivery": [
        "logistics", "route optimization", "supply chain", "warehouse management",
        "inventory management", "fleet management", "gps navigation",
        "last mile delivery", "order fulfillment", "shipping",
        "transportation", "procurement", "vendor management"
    ],
    "Mechanical & Engineering": [
        "cad", "autocad", "solidworks", "mechanical design", "thermodynamics",
        "fluid mechanics", "manufacturing", "cnc", "quality control",
        "3d printing", "robotics", "plc", "hvac", "gd&t",
        "product design", "material science", "fea", "maintenance"
    ],
    "Soft Skills": [
        "communication", "leadership", "teamwork", "problem solving",
        "critical thinking", "time management", "adaptability",
        "creativity", "collaboration", "conflict resolution",
        "emotional intelligence", "presentation skills", "multitasking",
        "attention to detail", "work ethic", "customer service",
        "interpersonal skills", "analytical thinking"
    ]
}

# Flatten all skills
ALL_SKILLS = []
for cluster_skills in SKILL_CLUSTERS_MAP.values():
    ALL_SKILLS.extend(cluster_skills)
ALL_SKILLS = list(set(ALL_SKILLS))

# =============================================================================
# INDUSTRY → ROLES MAPPING
# =============================================================================
INDUSTRY_ROLES = {
    "Software / IT": [
        "Software Developer", "Full Stack Developer", "Backend Developer",
        "Frontend Developer", "Mobile App Developer", "DevOps Engineer",
        "QA Engineer", "System Administrator", "IT Support"
    ],
    "Data & Analytics": [
        "Data Analyst", "Data Scientist", "Data Engineer",
        "ML Engineer", "Business Intelligence Analyst", "Database Administrator"
    ],
    "Marketing": [
        "Digital Marketing Manager", "SEO Specialist", "Content Strategist",
        "Social Media Manager", "Brand Manager", "Marketing Analyst"
    ],
    "Sales": [
        "Sales Executive", "Account Manager", "Business Development Manager",
        "Sales Analyst", "Retail Sales Associate", "Key Account Manager"
    ],
    "Finance": [
        "Financial Analyst", "Accountant", "Auditor", "Tax Consultant",
        "Investment Analyst", "Credit Analyst", "Finance Manager"
    ],
    "Healthcare": [
        "Healthcare Administrator", "Medical Coder", "Clinical Research Associate",
        "Nurse", "Public Health Analyst", "Health Informatics Specialist"
    ],
    "Teaching": [
        "School Teacher", "Online Tutor", "Corporate Trainer",
        "Curriculum Designer", "Instructional Designer", "Education Consultant"
    ],
    "Cooking / Chef": [
        "Chef", "Sous Chef", "Pastry Chef", "Line Cook",
        "Kitchen Manager", "Food Safety Officer", "Catering Manager"
    ],
    "Hotel / Hospitality": [
        "Front Desk Manager", "Hotel Manager", "Event Coordinator",
        "Housekeeping Manager", "Guest Relations Manager", "Concierge"
    ],
    "Delivery / Logistics": [
        "Delivery Executive", "Logistics Coordinator", "Warehouse Manager",
        "Supply Chain Analyst", "Fleet Manager", "Operations Coordinator"
    ],
    "Mechanical / Engineering": [
        "Mechanical Engineer", "Design Engineer", "Manufacturing Engineer",
        "Quality Engineer", "Maintenance Engineer", "CAD Designer"
    ],
    "Cybersecurity": [
        "Security Analyst", "Penetration Tester", "SOC Analyst",
        "Security Engineer", "Compliance Analyst", "Incident Responder"
    ],
    "Management": [
        "Project Manager", "Operations Manager", "General Manager",
        "Product Manager", "Program Manager", "Business Consultant"
    ]
}

# Which skill clusters are most relevant to each industry
INDUSTRY_SKILL_CLUSTERS = {
    "Software / IT": ["Programming Languages", "Web Frontend", "Web Backend", "Cloud & DevOps", "Soft Skills", "Management & Leadership"],
    "Data & Analytics": ["Data & Analytics", "AI & Machine Learning", "Programming Languages", "Soft Skills"],
    "Marketing": ["Marketing & Digital", "Data & Analytics", "Soft Skills", "Management & Leadership"],
    "Sales": ["Sales & Business", "Marketing & Digital", "Soft Skills", "Management & Leadership"],
    "Finance": ["Finance & Accounting", "Data & Analytics", "Soft Skills", "Management & Leadership"],
    "Healthcare": ["Healthcare & Medical", "Data & Analytics", "Soft Skills", "Management & Leadership"],
    "Teaching": ["Teaching & Education", "Soft Skills", "Management & Leadership"],
    "Cooking / Chef": ["Culinary & Food", "Management & Leadership", "Soft Skills"],
    "Hotel / Hospitality": ["Hospitality & Hotel", "Management & Leadership", "Soft Skills", "Sales & Business"],
    "Delivery / Logistics": ["Logistics & Delivery", "Management & Leadership", "Soft Skills"],
    "Mechanical / Engineering": ["Mechanical & Engineering", "Programming Languages", "Soft Skills", "Management & Leadership"],
    "Cybersecurity": ["Cybersecurity", "Cloud & DevOps", "Programming Languages", "Soft Skills"],
    "Management": ["Management & Leadership", "Sales & Business", "Soft Skills", "Finance & Accounting"],
}

# =============================================================================
# SKILL TRANSFERABILITY MATRIX
# =============================================================================
SKILL_TRANSFERABILITY = {
    "python": {"related": ["java", "r", "c++", "javascript"], "score": 0.7, "note": "OOP and scripting foundations transfer well across languages"},
    "java": {"related": ["c#", "kotlin", "c++", "python"], "score": 0.75, "note": "Strong OOP skills transfer to most enterprise languages"},
    "javascript": {"related": ["typescript", "python", "php"], "score": 0.7, "note": "Web scripting skills are broadly transferable"},
    "react": {"related": ["angular", "vue", "svelte", "next.js"], "score": 0.85, "note": "Component-based architecture shared across all modern frontend frameworks"},
    "angular": {"related": ["react", "vue", "typescript"], "score": 0.8, "note": "MVC patterns transfer to other frontend frameworks"},
    "vue": {"related": ["react", "angular", "svelte"], "score": 0.85, "note": "Reactive patterns transfer across frontend ecosystem"},
    "django": {"related": ["flask", "fastapi", "ruby on rails", "laravel"], "score": 0.8, "note": "MVC web framework patterns are universal"},
    "flask": {"related": ["django", "fastapi", "express.js"], "score": 0.8, "note": "Micro-framework patterns transfer to similar tools"},
    "node.js": {"related": ["express.js", "django", "flask"], "score": 0.7, "note": "Server-side JS transfers to other backend stacks"},
    "aws": {"related": ["azure", "gcp", "heroku"], "score": 0.8, "note": "Cloud concepts (compute, storage, networking) transfer across providers"},
    "azure": {"related": ["aws", "gcp"], "score": 0.8, "note": "Cloud platform skills are highly transferable"},
    "gcp": {"related": ["aws", "azure"], "score": 0.8, "note": "Cloud platform skills are highly transferable"},
    "docker": {"related": ["kubernetes", "terraform"], "score": 0.75, "note": "Containerization is foundational for orchestration"},
    "kubernetes": {"related": ["docker", "terraform", "ansible"], "score": 0.7, "note": "Orchestration builds on container knowledge"},
    "sql": {"related": ["nosql", "mongodb", "postgresql", "mysql"], "score": 0.7, "note": "Database querying is a core transferable skill"},
    "mongodb": {"related": ["sql", "redis", "nosql"], "score": 0.6, "note": "NoSQL paradigm differs from SQL but data concepts transfer"},
    "machine learning": {"related": ["deep learning", "data science", "statistics", "artificial intelligence"], "score": 0.8, "note": "ML foundations transfer to all AI subfields"},
    "deep learning": {"related": ["machine learning", "neural networks", "computer vision", "nlp"], "score": 0.75, "note": "DL specialization builds on ML knowledge"},
    "pandas": {"related": ["numpy", "excel", "sql", "data visualization"], "score": 0.7, "note": "Data manipulation skills transfer across tools"},
    "excel": {"related": ["google analytics", "power bi", "tableau", "pandas"], "score": 0.6, "note": "Spreadsheet skills form the base of data analysis"},
    "power bi": {"related": ["tableau", "google analytics", "data visualization"], "score": 0.85, "note": "BI tools share very similar concepts and workflows"},
    "tableau": {"related": ["power bi", "google analytics", "data visualization"], "score": 0.85, "note": "Visualization tools have near-identical patterns"},
    "digital marketing": {"related": ["seo", "sem", "social media marketing", "content marketing"], "score": 0.8, "note": "Digital marketing channels share strategy fundamentals"},
    "seo": {"related": ["sem", "content marketing", "google analytics", "digital marketing"], "score": 0.75, "note": "Search optimization skills complement paid search"},
    "negotiation": {"related": ["sales forecasting", "client relationship", "account management"], "score": 0.7, "note": "Negotiation is a core transferable business skill"},
    "project management": {"related": ["agile", "scrum", "operations management", "resource planning"], "score": 0.8, "note": "PM methodologies transfer across all industries"},
    "agile": {"related": ["scrum", "project management", "lean management"], "score": 0.9, "note": "Agile and Scrum are near-synonymous in practice"},
    "financial analysis": {"related": ["accounting", "financial modeling", "budgeting"], "score": 0.8, "note": "Financial skills form a tightly connected cluster"},
    "patient care": {"related": ["nursing", "first aid", "cpr", "diagnostics"], "score": 0.75, "note": "Patient-facing skills are interconnected"},
    "curriculum development": {"related": ["lesson planning", "instructional design", "pedagogy"], "score": 0.85, "note": "Education design skills are highly transferable"},
    "food safety": {"related": ["haccp", "food hygiene", "kitchen management", "nutrition"], "score": 0.8, "note": "Food safety knowledge applies across all culinary roles"},
    "kitchen management": {"related": ["food cost control", "menu planning", "food safety"], "score": 0.75, "note": "Kitchen ops skills transfer to any food service role"},
    "front desk": {"related": ["guest relations", "customer service", "reservation management"], "score": 0.8, "note": "Guest-facing hospitality skills transfer across hotel roles"},
    "logistics": {"related": ["supply chain", "warehouse management", "inventory management"], "score": 0.8, "note": "Supply chain skills form a tightly connected domain"},
    "cad": {"related": ["autocad", "solidworks", "mechanical design", "3d printing"], "score": 0.8, "note": "CAD tools share design paradigms"},
    "autocad": {"related": ["cad", "solidworks", "mechanical design"], "score": 0.85, "note": "2D/3D design tools are closely related"},
    "communication": {"related": ["presentation skills", "interpersonal skills", "collaboration"], "score": 0.8, "note": "Communication skills transfer to every industry"},
    "leadership": {"related": ["team leadership", "people management", "decision making"], "score": 0.85, "note": "Leadership is universally transferable"},
    "customer service": {"related": ["guest relations", "client relationship", "communication"], "score": 0.8, "note": "Customer-facing skills are universal across industries"},
}


# =============================================================================
# TEXT EXTRACTION
# =============================================================================
def extract_text_from_pdf(pdf_path):
    """Extracts text from a given PDF file using pdfplumber."""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + " "
    except Exception as e:
        print(f"Error reading PDF: {e}")
    return text.strip()

def extract_text_from_image(image_path):
    """Extracts text from an image file using pytesseract OCR."""
    text = ""
    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
    except Exception as e:
        print(f"Error reading Image: {e}")
    return text.strip()

def extract_text_from_txt(txt_path):
    """Extracts text from a simple text file (mostly for testing)."""
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        print(f"Error reading TXT: {e}")
        return ""

def extract_text(file_path):
    """Determines file type and extracts text accordingly."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf':
        return extract_text_from_pdf(file_path)
    elif ext in ['.png', '.jpg', '.jpeg']:
        return extract_text_from_image(file_path)
    elif ext == '.txt':
        return extract_text_from_txt(file_path)
    return ""


# =============================================================================
# NLP SKILL EXTRACTION & MATCHING
# =============================================================================
def clean_text(text):
    """Cleans text by lowercasing and removing special characters."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s/\.\+\#]', ' ', text)
    return text

def extract_skills_nlp(text):
    """Extracts skills from text using predefined dictionaries and regex NLP."""
    cleaned_text = clean_text(text)
    found_skills = set()
    for skill in ALL_SKILLS:
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, cleaned_text):
            found_skills.add(skill)
    return list(found_skills)

def calculate_match_percentage(resume_text, jd_text):
    """Calculates cosine similarity between resume and job description text."""
    if not resume_text or not jd_text:
        return 0.0
    resume_words = clean_text(resume_text).split()
    jd_words = clean_text(jd_text).split()
    stop_words = {'and', 'or', 'the', 'is', 'in', 'to', 'a', 'of', 'for', 'with', 'on', 'at', 'by', 'an', 'be', 'as', 'are', 'was', 'were', 'been', 'has', 'have', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'shall', 'this', 'that', 'these', 'those', 'it', 'its', 'we', 'our', 'you', 'your', 'they', 'their', 'he', 'she', 'his', 'her', 'not', 'no', 'but', 'if', 'so', 'from', 'about', 'up', 'out'}
    resume_words = [w for w in resume_words if w not in stop_words and len(w) > 1]
    jd_words = [w for w in jd_words if w not in stop_words and len(w) > 1]
    resume_counter = Counter(resume_words)
    jd_counter = Counter(jd_words)
    words = list(set(resume_words + jd_words))
    dot_product = sum(resume_counter[w] * jd_counter[w] for w in words)
    mag_r = math.sqrt(sum(resume_counter[w]**2 for w in words))
    mag_j = math.sqrt(sum(jd_counter[w]**2 for w in words))
    if not mag_r or not mag_j:
        return 0.0
    similarity = dot_product / (mag_r * mag_j)
    return round(similarity * 100, 2)


# =============================================================================
# CORE ANALYSIS — Single Role
# =============================================================================
def analyze_resume_vs_jd(resume_text, jd_text):
    """Core analysis function: compares resume against a single job description."""
    resume_skills = set(extract_skills_nlp(resume_text))
    jd_skills = set(extract_skills_nlp(jd_text))
    matched_skills = resume_skills.intersection(jd_skills)
    missing_skills = jd_skills.difference(resume_skills)
    ai_match = calculate_match_percentage(resume_text, jd_text)
    if len(jd_skills) > 0:
        skill_match = round((len(matched_skills) / len(jd_skills)) * 100, 2)
    else:
        skill_match = ai_match
    final_score = round((ai_match * 0.4) + (skill_match * 0.6), 2)
    recommendations = generate_recommendations(list(missing_skills))
    return {
        "match_percentage": final_score,
        "matched_skills": list(matched_skills),
        "missing_skills": list(missing_skills),
        "recommendations": recommendations,
        "ai_semantic_similarity": ai_match
    }


# =============================================================================
# SKILL CLUSTERING — Map user's skills into clusters
# =============================================================================
def analyze_skill_clusters(resume_skills):
    """Maps the user's skills into clusters and returns a distribution."""
    distribution = {}
    for cluster_name, cluster_skills in SKILL_CLUSTERS_MAP.items():
        matched = [s for s in resume_skills if s in cluster_skills]
        if matched:
            distribution[cluster_name] = {
                "skills": matched,
                "count": len(matched),
                "total_in_cluster": len(cluster_skills),
                "coverage_pct": round((len(matched) / len(cluster_skills)) * 100, 1)
            }
    return distribution


# =============================================================================
# SKILL TRANSFERABILITY ANALYZER
# =============================================================================
def calculate_transferability(user_skills, missing_skills):
    """For each missing skill, find related skills the user already has."""
    transferability_results = []
    user_skills_set = set(s.lower() for s in user_skills)

    for skill in missing_skills:
        skill_lower = skill.lower()
        entry = SKILL_TRANSFERABILITY.get(skill_lower, None)
        if entry:
            # Check which related skills the user already has
            user_has_related = [s for s in entry["related"] if s in user_skills_set]
            if user_has_related:
                transferability_results.append({
                    "missing_skill": skill,
                    "you_already_know": user_has_related,
                    "transferability_score": entry["score"],
                    "difficulty": "Easy" if entry["score"] >= 0.8 else "Medium" if entry["score"] >= 0.6 else "Hard",
                    "note": entry["note"]
                })
            else:
                transferability_results.append({
                    "missing_skill": skill,
                    "you_already_know": [],
                    "transferability_score": 0.0,
                    "difficulty": "Hard",
                    "note": f"No related skills found in your resume. Start learning '{skill}' from scratch."
                })
        else:
            transferability_results.append({
                "missing_skill": skill,
                "you_already_know": [],
                "transferability_score": 0.0,
                "difficulty": "Unknown",
                "note": f"Consider adding '{skill}' to your skillset."
            })

    # Sort by transferability score (easiest to learn first)
    transferability_results.sort(key=lambda x: x["transferability_score"], reverse=True)
    return transferability_results


# =============================================================================
# AUTO-DETECT BEST-FIT INDUSTRIES & ROLES
# =============================================================================
def detect_best_industries(resume_skills):
    """Auto-detect which industries a resume is best suited for."""
    resume_skills_set = set(s.lower() for s in resume_skills)
    industry_scores = []

    for industry, relevant_clusters in INDUSTRY_SKILL_CLUSTERS.items():
        # Gather all skills for this industry's clusters
        industry_skills = set()
        for cluster_name in relevant_clusters:
            industry_skills.update(SKILL_CLUSTERS_MAP.get(cluster_name, []))

        matched = resume_skills_set.intersection(industry_skills)
        if industry_skills:
            score = round((len(matched) / len(industry_skills)) * 100, 1)
        else:
            score = 0.0

        if matched:  # Only include industries where user has at least 1 skill
            industry_scores.append({
                "industry": industry,
                "match_score": score,
                "matched_skills": list(matched),
                "matched_count": len(matched),
                "total_skills_needed": len(industry_skills),
                "roles": INDUSTRY_ROLES.get(industry, [])
            })

    industry_scores.sort(key=lambda x: x["match_score"], reverse=True)
    return industry_scores


def detect_best_roles(resume_skills):
    """Suggest which specific roles to search for based on resume skills."""
    industries = detect_best_industries(resume_skills)
    suggested_roles = []
    seen_roles = set()

    for ind in industries[:5]:  # Top 5 industries
        for role in ind["roles"][:3]:  # Top 3 roles per industry
            if role not in seen_roles:
                suggested_roles.append({
                    "role": role,
                    "industry": ind["industry"],
                    "industry_match_score": ind["match_score"]
                })
                seen_roles.add(role)

    return suggested_roles


# =============================================================================
# MULTI-ROLE ANALYSIS
# =============================================================================
def analyze_multi_role(resume_text, roles_data):
    """
    Analyze resume against multiple roles.
    roles_data: dict keyed by role name, value is {combined_description, source_jobs, ...}
    Returns a list of per-role analysis results.
    """
    resume_skills = set(extract_skills_nlp(resume_text))
    skill_clusters = analyze_skill_clusters(list(resume_skills))
    results = []

    for role_name, role_info in roles_data.items():
        jd_text = role_info.get("combined_description", "")
        if not jd_text or len(jd_text.strip()) < 10:
            continue

        analysis = analyze_resume_vs_jd(resume_text, jd_text)

        # Add transferability for missing skills
        transferability = calculate_transferability(
            list(resume_skills), analysis["missing_skills"]
        )

        # Extract companies from source_jobs for "apply at" suggestions
        companies = []
        for job in role_info.get("source_jobs", []):
            companies.append({
                "company": job.get("company", "N/A"),
                "title": job.get("title", role_name),
                "location": job.get("location", "N/A"),
                "apply_link": job.get("apply_link", "")
            })

        results.append({
            "role": role_name,
            "industry": role_info.get("industry", "General"),
            "match_percentage": analysis["match_percentage"],
            "ai_semantic_similarity": analysis["ai_semantic_similarity"],
            "matched_skills": analysis["matched_skills"],
            "missing_skills": analysis["missing_skills"],
            "recommendations": analysis["recommendations"],
            "transferability": transferability,
            "jobs_analyzed": role_info.get("jobs_analyzed", 0),
            "apply_at": companies
        })

    # Sort by match percentage (best fit first)
    results.sort(key=lambda x: x["match_percentage"], reverse=True)
    return {
        "resume_skills": list(resume_skills),
        "skill_clusters": skill_clusters,
        "role_results": results
    }


# =============================================================================
# RECOMMENDATIONS GENERATOR
# =============================================================================
def generate_recommendations(missing_skills):
    """Generates personalized recommendations based on missing skills."""
    recommendations = []
    if not missing_skills:
        return ["Your resume matches the job description perfectly!"]

    recommendations.append(f"You are missing {len(missing_skills)} key skills for this role.")

    for skill in missing_skills:
        entry = SKILL_TRANSFERABILITY.get(skill.lower())
        if entry:
            related = ", ".join(entry["related"][:3])
            recommendations.append(
                f"Learn '{skill.title()}' — {entry['note']} (Related: {related})"
            )
        else:
            recommendations.append(f"Consider learning '{skill.title()}' to improve your chances.")

    return recommendations


# =============================================================================
# COURSE LINK GENERATOR (with real YouTube links via API)
# =============================================================================
def generate_course_links(skill):
    """
    Generate learning resource URLs for a given skill.
    Uses YouTube Data API v3 for direct video links (free).
    Falls back to search URLs if API key is not set.
    """
    try:
        from course_fetcher import fetch_courses_for_skill
        return fetch_courses_for_skill(skill)
    except ImportError:
        # Fallback if course_fetcher is not available
        skill_query = skill.replace(' ', '+')
        return {
            "youtube_tutorials": [{
                "title": f"Search YouTube for '{skill}' tutorials",
                "url": f"https://www.youtube.com/results?search_query={skill_query}+full+course+tutorial",
                "channel": "YouTube Search",
                "thumbnail": ""
            }],
            "coursera": f"https://www.coursera.org/search?query={skill_query}",
            "udemy": f"https://www.udemy.com/courses/search/?q={skill_query}",
            "google": f"https://www.google.com/search?q=learn+{skill_query}+free+course",
            "freecodecamp": f"https://www.freecodecamp.org/news/search/?query={skill_query}"
        }


# =============================================================================
# LEARNING PATH / MINDMAP BUILDER
# =============================================================================
def build_learning_path(missing_skills, user_skills):
    """
    Build a structured learning path for missing skills.
    Groups skills by cluster, orders by difficulty (easy first),
    and attaches course links for each skill.
    
    Returns a mindmap-style data structure.
    """
    if not missing_skills:
        return {"message": "No missing skills! You're fully qualified.", "clusters": []}
    
    # Get transferability info for each missing skill
    transferability = calculate_transferability(user_skills, missing_skills)
    transfer_map = {t["missing_skill"].lower(): t for t in transferability}
    
    # Group missing skills by their cluster
    cluster_groups = {}
    uncategorized = []
    
    for skill in missing_skills:
        skill_lower = skill.lower()
        found_cluster = None
        for cluster_name, cluster_skills in SKILL_CLUSTERS_MAP.items():
            if skill_lower in cluster_skills:
                found_cluster = cluster_name
                break
        
        transfer_info = transfer_map.get(skill_lower, {})
        skill_entry = {
            "skill": skill,
            "difficulty": transfer_info.get("difficulty", "Unknown"),
            "transferability_score": transfer_info.get("transferability_score", 0),
            "you_already_know": transfer_info.get("you_already_know", []),
            "note": transfer_info.get("note", ""),
            "courses": generate_course_links(skill)
        }
        
        if found_cluster:
            if found_cluster not in cluster_groups:
                cluster_groups[found_cluster] = []
            cluster_groups[found_cluster].append(skill_entry)
        else:
            uncategorized.append(skill_entry)
    
    # Sort skills within each cluster by difficulty (Easy first)
    difficulty_order = {"Easy": 0, "Medium": 1, "Hard": 2, "Unknown": 3}
    
    clusters_list = []
    for cluster_name, skills in cluster_groups.items():
        skills.sort(key=lambda x: difficulty_order.get(x["difficulty"], 3))
        clusters_list.append({
            "cluster": cluster_name,
            "skills_count": len(skills),
            "skills": skills
        })
    
    if uncategorized:
        uncategorized.sort(key=lambda x: difficulty_order.get(x["difficulty"], 3))
        clusters_list.append({
            "cluster": "Other Skills",
            "skills_count": len(uncategorized),
            "skills": uncategorized
        })
    
    # Sort clusters by number of missing skills (most gaps first)
    clusters_list.sort(key=lambda x: x["skills_count"], reverse=True)
    
    # Summary stats
    easy_count = sum(1 for c in clusters_list for s in c["skills"] if s["difficulty"] == "Easy")
    medium_count = sum(1 for c in clusters_list for s in c["skills"] if s["difficulty"] == "Medium")
    hard_count = sum(1 for c in clusters_list for s in c["skills"] if s["difficulty"] == "Hard")
    
    return {
        "total_missing": len(missing_skills),
        "summary": {
            "easy_to_learn": easy_count,
            "medium_effort": medium_count,
            "hard_requires_training": hard_count
        },
        "clusters": clusters_list
    }


# =============================================================================
# FILTER JOBS FOR APPLICATION (≥70% match)
# =============================================================================
def filter_apply_jobs(role_results, threshold=70):
    """
    Filter roles where match_percentage >= threshold.
    Returns apply-at jobs in ASCENDING order of match (closest to threshold first,
    best match last — so user reads from good to best).
    """
    qualified_roles = []
    not_qualified_roles = []
    
    for role in role_results:
        match_pct = role.get("match_percentage", 0)
        role_entry = {
            "role": role.get("role", role.get("job_role", "")),
            "industry": role.get("industry", "General"),
            "match_percentage": match_pct,
            "matched_skills": role.get("matched_skills", []),
            "missing_skills": role.get("missing_skills", []),
            "apply_at": role.get("apply_at", [])
        }
        
        if match_pct >= threshold:
            qualified_roles.append(role_entry)
        else:
            not_qualified_roles.append(role_entry)
    
    # Ascending order (70% first, 100% last)
    qualified_roles.sort(key=lambda x: x["match_percentage"])
    # Not qualified sorted descending (closest to threshold first)
    not_qualified_roles.sort(key=lambda x: x["match_percentage"], reverse=True)
    
    return {
        "threshold": threshold,
        "qualified_count": len(qualified_roles),
        "not_qualified_count": len(not_qualified_roles),
        "apply_now": qualified_roles,
        "need_upskilling": not_qualified_roles
    }
