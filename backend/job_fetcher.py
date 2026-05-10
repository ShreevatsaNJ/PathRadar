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


def fetch_jobs_by_role(job_role, location="India", num_pages=1):
    """
    Fetches live job listings from JSearch API based on a job role.
    
    Args:
        job_role (str): The job role to search for (e.g., "Data Analyst")
        location (str): Location filter (default: "India")
        num_pages (int): Number of result pages to fetch (default: 1)
    
    Returns:
        list: A list of job dictionaries, or dict with error key on failure.
    """
    if not RAPIDAPI_KEY or RAPIDAPI_KEY == "your_api_key_here":
        return {"error": "API key not configured. Please set RAPIDAPI_KEY in backend/.env file."}
    
    query = f"{job_role} in {location}"
    
    params = {
        "query": query,
        "page": "1",
        "num_pages": str(num_pages),
        "date_posted": "month"  # Get recent postings only
    }
    
    try:
        response = requests.get(JSEARCH_URL, headers=HEADERS, params=params, timeout=10)
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
        return {"error": "JSearch API request timed out. Please try again."}
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            return {"error": "Invalid API key. Please check your RAPIDAPI_KEY in .env file."}
        elif e.response.status_code == 429:
            return {"error": "API rate limit exceeded. Free tier allows 200 requests/month."}
        return {"error": f"API error: {e.response.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to JSearch API. Check your internet connection."}
    except Exception as e:
        return {"error": f"Unexpected error fetching jobs: {str(e)}"}


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
