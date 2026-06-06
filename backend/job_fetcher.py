"""
JSearch API Integration Module
Fetches live job descriptions from LinkedIn, Indeed, Glassdoor, etc.
via the JSearch API (RapidAPI).

Supports multi-role and multi-industry batch fetching.
"""
import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
JSEARCH_URL = "https://jsearch.p.rapidapi.com/search"

HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
}


def get_mock_jobs(job_role, location="India"):
    """
    Generates comprehensive mock job descriptions when the external API key
    is not configured, invalid, or rate-limited.

    Uses the full skills database from model.py to build role-aware JDs so
    that resume skill matching works correctly even without the live API.
    """
    from model import SKILL_CLUSTERS_MAP, INDUSTRY_ROLES

    # Determine which skill clusters are most relevant for this role
    role_lower = job_role.lower()

    # Map role keywords to relevant skill clusters
    _ROLE_CLUSTER_MAP = {
        # Software / IT roles
        "software": ["Programming Languages", "Web Frontend", "Web Backend", "Cloud & DevOps", "Data & Analytics", "Soft Skills"],
        "full stack": ["Programming Languages", "Web Frontend", "Web Backend", "Cloud & DevOps", "Data & Analytics"],
        "frontend": ["Web Frontend", "Programming Languages", "Soft Skills"],
        "backend": ["Web Backend", "Programming Languages", "Cloud & DevOps", "Data & Analytics"],
        "devops": ["Cloud & DevOps", "Programming Languages", "Web Backend"],
        "mobile": ["Programming Languages", "Web Frontend", "Cloud & DevOps"],
        "qa": ["Programming Languages", "Web Backend", "Soft Skills"],
        # Data roles
        "data analyst": ["Data & Analytics", "Programming Languages", "AI & Machine Learning", "Soft Skills"],
        "data scientist": ["AI & Machine Learning", "Data & Analytics", "Programming Languages"],
        "data engineer": ["Data & Analytics", "Cloud & DevOps", "Programming Languages"],
        "ml engineer": ["AI & Machine Learning", "Programming Languages", "Cloud & DevOps"],
        "business intelligence": ["Data & Analytics", "Programming Languages", "Soft Skills"],
        # Management roles
        "project manager": ["Management & Leadership", "Soft Skills", "Data & Analytics"],
        "operations manager": ["Management & Leadership", "Soft Skills", "Finance & Accounting"],
        "product manager": ["Management & Leadership", "Soft Skills", "Data & Analytics"],
        # Marketing roles
        "marketing": ["Marketing & Digital", "Soft Skills", "Data & Analytics"],
        "seo": ["Marketing & Digital", "Web Frontend", "Data & Analytics"],
        "content": ["Marketing & Digital", "Soft Skills"],
        # Sales roles
        "sales": ["Sales & Business", "Soft Skills", "Marketing & Digital"],
        # Finance roles
        "financial": ["Finance & Accounting", "Data & Analytics", "Soft Skills"],
        "accountant": ["Finance & Accounting", "Soft Skills"],
        # Healthcare roles
        "nurse": ["Healthcare & Medical", "Soft Skills"],
        "doctor": ["Healthcare & Medical", "Soft Skills"],
        "healthcare": ["Healthcare & Medical", "Soft Skills", "Management & Leadership"],
        # Education roles
        "teacher": ["Teaching & Education", "Soft Skills"],
        "instructor": ["Teaching & Education", "Soft Skills"],
        # Engineering roles
        "mechanical": ["Mechanical & Engineering", "Soft Skills"],
        "engineer": ["Programming Languages", "Web Backend", "Cloud & DevOps", "Data & Analytics", "Soft Skills"],
        # Cybersecurity roles
        "security": ["Cybersecurity", "Cloud & DevOps", "Programming Languages"],
        "cyber": ["Cybersecurity", "Cloud & DevOps", "Programming Languages"],
    }

    # Find matching clusters for the role
    relevant_clusters = []
    for keyword, clusters in _ROLE_CLUSTER_MAP.items():
        if keyword in role_lower:
            relevant_clusters = clusters
            break

    # Default: use a broad set of clusters
    if not relevant_clusters:
        relevant_clusters = ["Programming Languages", "Web Frontend", "Web Backend",
                             "Cloud & DevOps", "Data & Analytics", "AI & Machine Learning",
                             "Management & Leadership", "Soft Skills"]

    # Build a comprehensive skills list from the matching clusters
    all_relevant_skills = []
    for cluster_name in relevant_clusters:
        if cluster_name in SKILL_CLUSTERS_MAP:
            all_relevant_skills.extend(SKILL_CLUSTERS_MAP[cluster_name])

    # Build a rich job description that mentions the skills explicitly
    skills_text = ", ".join(all_relevant_skills)

    desc = f"""
    Job Title: {job_role}
    Location: {location}

    About the Role:
    We are looking for a talented {job_role} to join our growing team in {location}.
    This role requires a strong combination of technical and soft skills.

    Responsibilities:
    - Collaborate with cross-functional teams to design and build scalable solutions.
    - Work with tools and technologies such as {skills_text}.
    - Write clean, maintainable, and efficient code/reports.
    - Participate in code reviews and agile team ceremonies.
    - Troubleshoot, debug, and optimize application/workflow performance.
    - Perform data visualization, data analysis, and reporting tasks.
    - Lead and mentor junior team members on best practices.

    Required Skills & Qualifications:
    - Professional experience working as a {job_role} or similar role.
    - Strong proficiency in: {skills_text}.
    - Solid understanding of software development, data analysis, or management workflows.
    - Excellent communication, leadership, and collaboration skills.
    - Experience with project management, strategic planning, and stakeholder management.
    - Familiarity with cloud platforms (AWS, Azure, GCP) and containerization (Docker, Kubernetes).

    Preferred Qualifications:
    - Experience with {', '.join(all_relevant_skills[:10])}.
    - Knowledge of {', '.join(all_relevant_skills[10:20]) if len(all_relevant_skills) > 10 else 'related technologies'}.
    """

    return [
        {
            "job_title": f"Senior {job_role}",
            "employer_name": "TechGlobal Solutions",
            "job_city": "Bengaluru" if location == "India" else "New York",
            "job_state": "Karnataka" if location == "India" else "NY",
            "job_country": "IN" if location == "India" else "US",
            "job_employment_type": "FULLTIME",
            "job_description": desc,
            "job_required_skills": all_relevant_skills[:15],
            "job_apply_link": "https://example.com/apply/senior-" + job_role.lower().replace(" ", "-"),
            "job_posted_at": "2026-06-05T12:00:00.000Z",
        },
        {
            "job_title": f"{job_role}",
            "employer_name": "InnoTech Systems",
            "job_city": "Mumbai" if location == "India" else "San Francisco",
            "job_state": "Maharashtra" if location == "India" else "CA",
            "job_country": "IN" if location == "India" else "US",
            "job_employment_type": "FULLTIME",
            "job_description": desc,
            "job_required_skills": all_relevant_skills[5:20],
            "job_apply_link": "https://example.com/apply/" + job_role.lower().replace(" ", "-"),
            "job_posted_at": "2026-06-06T09:00:00.000Z",
        }
    ]


def fetch_jobs_by_role(job_role, location="India", num_pages=1):
    """
    Fetches live job listings from JSearch API based on a job role.
    Falls back to mock job descriptions if the API is offline or rate-limited.
    
    Args:
        job_role (str): The job role to search for (e.g., "Data Analyst")
        location (str): Location filter (default: "India")
        num_pages (int): Number of result pages to fetch (default: 1)
    
    Returns:
        list: A list of job dictionaries.
    """
    if not RAPIDAPI_KEY or RAPIDAPI_KEY == "your_api_key_here":
        print("INFO: RAPIDAPI_KEY not configured. Falling back to local mock jobs.")
        return get_mock_jobs(job_role, location)
    
    query = f"{job_role} in {location}"
    
    params = {
        "query": query,
        "page": "1",
        "num_pages": str(num_pages),
        "date_posted": "month"  # Get recent postings only
    }
    
    try:
        response = requests.get(JSEARCH_URL, headers=HEADERS, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        jobs = []
        for job in data.get("data", []):
            jobs.append({
                "job_title": job.get("job_title", "N/A"),
                "employer_name": job.get("employer_name", "N/A"),
                "job_city": job.get("job_city", "N/A"),
                "job_state": job.get("job_state", "N/A"),
                "job_country": job.get("job_country", "N/A"),
                "job_employment_type": job.get("job_employment_type", "N/A"),
                "job_description": job.get("job_description", ""),
                "job_required_skills": job.get("job_required_skills") or [],
                "job_apply_link": job.get("job_apply_link", ""),
                "job_posted_at": job.get("job_posted_at_datetime_utc", "N/A"),
            })
        
        return jobs
    
    except requests.exceptions.Timeout:
        print("WARNING: JSearch API request timed out. Falling back to local mock jobs.")
        return get_mock_jobs(job_role, location)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            print("WARNING: Invalid API key (403). Falling back to local mock jobs.")
            return get_mock_jobs(job_role, location)
        elif e.response.status_code == 429:
            print("WARNING: API rate limit exceeded (429). Falling back to local mock jobs.")
            return get_mock_jobs(job_role, location)
        print(f"WARNING: API error {e.response.status_code}. Falling back to local mock jobs.")
        return get_mock_jobs(job_role, location)
    except requests.exceptions.ConnectionError:
        print("WARNING: Could not connect to JSearch API. Falling back to local mock jobs.")
        return get_mock_jobs(job_role, location)
    except Exception as e:
        print(f"WARNING: Unexpected error fetching jobs: {str(e)}. Falling back to local mock jobs.")
        return get_mock_jobs(job_role, location)


def get_combined_job_description(job_role, location="India"):
    """
    Fetches multiple job listings for a role and combines their descriptions
    into a single comprehensive job description for better skill matching.
    """
    result = fetch_jobs_by_role(job_role, location)
    
    # If error was returned
    if isinstance(result, dict) and "error" in result:
        return result
    
    if not result:
        return {"error": f"No job listings found for '{job_role}'. Try a different role."}
    
    # Combine descriptions from multiple jobs
    combined_description = "\n\n".join(
        job["job_description"] for job in result if job["job_description"]
    )
    
    # Collect explicitly listed required skills
    all_required_skills = set()
    for job in result:
        for skill in job.get("job_required_skills", []):
            if skill:
                all_required_skills.add(skill.lower())
    
    return {
        "combined_description": combined_description,
        "required_skills_from_api": list(all_required_skills),
        "jobs_analyzed": len(result),
        "source_jobs": [
            {
                "title": job["job_title"],
                "company": job["employer_name"],
                "location": f"{job['job_city']}, {job['job_country']}",
                "apply_link": job.get("job_apply_link", "")
            }
            for job in result
        ]
    }


def fetch_jobs_for_multiple_roles(roles, location="India"):
    """
    Fetch JDs for multiple roles in one call.
    
    Args:
        roles: list of dicts like [{"role": "Data Analyst", "industry": "Data & Analytics"}, ...]
        location: location filter
    
    Returns:
        dict keyed by role name → {combined_description, source_jobs, industry, ...}
    """
    roles_data = {}
    errors = []
    
    for role_entry in roles:
        role_name = role_entry["role"]
        industry = role_entry.get("industry", "General")
        
        result = get_combined_job_description(role_name, location)
        
        if isinstance(result, dict) and "error" in result:
            errors.append({"role": role_name, "error": result["error"]})
            continue
        
        result["industry"] = industry
        roles_data[role_name] = result
    
    return {
        "roles_data": roles_data,
        "errors": errors
    }


def fetch_jobs_for_industry(industry, industry_roles, location="India"):
    """
    Fetch JDs for all roles within a given industry.
    
    Args:
        industry: industry name (e.g. "Software / IT")
        industry_roles: list of role names for this industry
        location: location filter
    
    Returns:
        dict keyed by role name → {combined_description, source_jobs, ...}
    """
    roles = [{"role": r, "industry": industry} for r in industry_roles]
    return fetch_jobs_for_multiple_roles(roles, location)
