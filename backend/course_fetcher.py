"""
Course Fetcher Module
====================
Fetches real, direct course/tutorial links using the YouTube Data API v3.
This is 100% FREE — YouTube Data API gives 10,000 quota units/day.
A search costs 100 units, so you get ~100 searches/day for free.

Setup:
    1. Go to https://console.cloud.google.com/apis/library/youtube.googleapis.com
    2. Enable "YouTube Data API v3"
    3. Create an API key (no OAuth needed)
    4. Add YOUTUBE_API_KEY=your_key to your .env file

Falls back to search-page URLs if the API key is missing.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

# Curated map: skill → best YouTube video/playlist ID (guaranteed direct video links)
# Used as fallback when API key is missing or quota exceeded
SKILL_VIDEO_MAP = {
    # Programming Languages
    "python":           "rfscVS0vtbw",  # freeCodeCamp — Python full course
    "java":             "GoXwIVyNvX0",  # freeCodeCamp — Java full course
    "javascript":       "PkZNo7MFNFg",  # freeCodeCamp — JavaScript full course
    "typescript":       "BwuLxPH8IDs",  # Fireship — TypeScript in 100 seconds (full)
    "c++":              "vLnPwxZdW4Y",  # freeCodeCamp — C++ full course
    "c#":               "GhQdlIFylQ8",  # freeCodeCamp — C# full course
    "go":               "YS4e4q8oBco",  # freeCodeCamp — Go full course
    "rust":             "BpPEoZX5l2Q",  # freeCodeCamp — Rust programming
    "kotlin":           "F9UC9DY-vIU",  # freeCodeCamp — Kotlin full course
    "swift":            "comQ1-x2a1Q",  # freeCodeCamp — Swift for beginners
    "php":              "OK_JCtrrv-c",  # freeCodeCamp — PHP full course
    "ruby":             "t_ispmWmdjY",  # freeCodeCamp — Ruby full course
    "scala":            "i9G4_s7FvLM",  # Rock the JVM — Scala beginners
    "r":                "_V8eKsto3Ug",  # freeCodeCamp — R programming
    # Web & Frontend
    "html":             "pQN-pnXPaVg",  # freeCodeCamp — HTML full course
    "css":              "1Rs2ND1ryYc",  # freeCodeCamp — CSS full course
    "react":            "bMknfKXIFA8",  # freeCodeCamp — React full course
    "react.js":         "bMknfKXIFA8",
    "vue.js":           "FXpIoQ_rT_c",  # freeCodeCamp — Vue.js full course
    "angular":          "3qBXWUpoPHo",  # freeCodeCamp — Angular full course
    "next.js":          "1WmNXex__i4",  # freeCodeCamp — Next.js course
    "svelte":           "ujbE0mzX-CU",  # freeCodeCamp — Svelte
    "tailwind css":     "dFgzHOX84xQ",  # freeCodeCamp — Tailwind CSS
    "bootstrap":        "4sosXZsdy-s",  # freeCodeCamp — Bootstrap 5
    "graphql":          "ed8SHL5nYhU",  # freeCodeCamp — GraphQL
    # Backend / Frameworks
    "node.js":          "Oe421EPjeBE",  # freeCodeCamp — Node.js full course
    "django":           "F5mRW0jo-U4",  # freeCodeCamp — Django
    "flask":            "Z1RJmh_OqeA",  # freeCodeCamp — Flask
    "fastapi":          "0sOvCWFmrtA",  # freeCodeCamp — FastAPI
    "spring boot":      "vtPkZShrvXQ",  # Amigoscode — Spring Boot 3
    "express.js":       "qwfE7fSVaZM",  # freeCodeCamp — Express.js
    # Databases
    "sql":              "HXV3zeQKqGY",  # freeCodeCamp — SQL full course
    "mysql":            "HXV3zeQKqGY",
    "postgresql":       "qw--VYLpxG4",  # freeCodeCamp — PostgreSQL
    "mongodb":          "GzIRya29ccQ",  # Traversy Media — MongoDB crash course
    "redis":            "jgpVdJB2sKQ",  # freeCodeCamp — Redis
    "sqlite":           "byHcYRpMgI4",  # CS50 SQLite
    "firebase":         "9kRgVxULbag",  # freeCodeCamp — Firebase
    # Data Science & ML
    "machine learning": "NWONeJKn6kc",  # Simplilearn — Machine learning full course
    "deep learning":    "VyWAvY2CF9c",  # freeCodeCamp — Deep Learning
    "data science":     "ua-CiDNNj30",  # freeCodeCamp — Data Science
    "pandas":           "2uvysYbKdjM",  # freeCodeCamp — Pandas
    "numpy":            "QUT1VHiLmmI",  # freeCodeCamp — NumPy
    "tensorflow":       "tPYj3fFJGjk",  # freeCodeCamp — TensorFlow
    "pytorch":          "V_xro1bzAYk",  # freeCodeCamp — PyTorch
    "scikit-learn":     "0B5eIE_1vpU",  # freeCodeCamp — Scikit-learn
    "nlp":              "X2vAabgKiWM",  # freeCodeCamp — NLP
    "computer vision":  "01sAkU_NvOY",  # freeCodeCamp — Computer Vision
    "data analysis":    "r-uOLxNrNk8",  # freeCodeCamp — Data Analysis Python
    # DevOps & Cloud
    "docker":           "fqMOX6JJhGo",  # freeCodeCamp — Docker
    "kubernetes":       "X48VuDVv0do",  # TechWorld — Kubernetes
    "aws":              "ubCNZFQjYmI",  # freeCodeCamp — AWS cloud
    "azure":            "NKEFWyqJ5XA",  # freeCodeCamp — Azure
    "google cloud":     "M988_fsOSWo",  # freeCodeCamp — Google Cloud
    "ci/cd":            "R8_veQiYBjI",  # freeCodeCamp — CI/CD
    "terraform":        "SLB_c5HN5r0",  # freeCodeCamp — Terraform
    "ansible":          "w9eCU4bGgjQ",  # freeCodeCamp — Ansible
    "linux":            "sWbUDq4S6Y8",  # freeCodeCamp — Linux
    "git":              "RGOj5yH7evk",  # freeCodeCamp — Git & GitHub
    "github":           "RGOj5yH7evk",
    # Networking & Security
    "networking":       "IPvYjXCsTg8",  # freeCodeCamp — CompTIA Network+
    "cybersecurity":    "hXSFdwIIsNU",  # freeCodeCamp — Ethical Hacking
    "ethical hacking":  "hXSFdwIIsNU",
    # Product & Design
    "product management": "JkMOXDyTMTQ",  # Google PM course
    "ux design":          "c9Wg6Cb_YlU",  # freeCodeCamp — UX Design
    "figma":              "jwCmIBJ8Jtc",  # freeCodeCamp — Figma
    # Business & Soft Skills
    "excel":              "Vl0H-qTclOg",  # freeCodeCamp — Excel
    "power bi":           "AGrl-H87pRU",  # freeCodeCamp — Power BI
    "tableau":            "TPMlZxRRaBQ",  # freeCodeCamp — Tableau
    "agile":              "Z9QbYZh1YXY",  # freeCodeCamp — Agile
    "scrum":              "2Vt7Ik8Ublw",  # Scrum explained
}


def _curated_video(skill):
    """Return curated video info for a skill, or None."""
    import re
    key = skill.lower().strip()
    
    # 1. Try Exact Match first (Fastest/Safest)
    vid_id = SKILL_VIDEO_MAP.get(key)
    
    # 2. Try Whole-Word Match if no exact match
    if not vid_id:
        for k, v in SKILL_VIDEO_MAP.items():
            # Check if the map key exists as a whole word in the search skill
            # or if the search skill exists as a whole word in the map key
            pattern_k = r'\b' + re.escape(k) + r'\b'
            pattern_key = r'\b' + re.escape(key) + r'\b'
            if re.search(pattern_k, key) or re.search(pattern_key, k):
                vid_id = v
                break
    if vid_id:
        return [{
            "title": f"Top Tutorial — {skill}",
            "url": f"https://www.youtube.com/watch?v={vid_id}",
            "channel": "Curated Pick",
            "thumbnail": f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg"
        }]
    return None

def fetch_youtube_tutorials(skill, max_results=1):
    """
    Fetch the BEST YouTube resource for a skill.
    Priority 1: YouTube Data API (uses engagement scoring).
    Priority 2: Curated SKILL_VIDEO_MAP (guaranteed direct watch?v= links).
    Priority 3: YouTube search page fallback.
    """
    if not YOUTUBE_API_KEY:
        # No API key — try curated map first, then fall back to search
        curated = _curated_video(skill)
        if curated:
            return curated
        query = skill.replace(' ', '+')
        return [{"title": f"Search YouTube for '{skill}'",
                 "url": f"https://www.youtube.com/results?search_query={query}+full+course+tutorial",
                 "channel": "YouTube Search", "thumbnail": ""}]

    try:
        # Step 1: Search for both videos and playlists
        search_params = {
            "part": "snippet",
            "q": f"{skill} full course tutorial for beginners",
            "type": "video,playlist",
            "order": "relevance",
            "maxResults": 5,
            "key": YOUTUBE_API_KEY
        }
        search_res = requests.get(YOUTUBE_SEARCH_URL, params=search_params, timeout=10)

        if search_res.status_code != 200:
            curated = _curated_video(skill)
            return curated or [{"title": f"Search YouTube for '{skill}'",
                                "url": f"https://www.youtube.com/results?search_query={skill.replace(' ', '+')}+full+course+tutorial",
                                "channel": "YouTube Search", "thumbnail": ""}]

        items = search_res.json().get("items", [])
        if not items:
            return _curated_video(skill) or []

        # Step 2: Check for Playlists first (they're usually full courses)
        for item in items:
            if item["id"].get("kind") == "youtube#playlist":
                playlist_id = item["id"]["playlistId"]
                snippet = item.get("snippet", {})
                return [{
                    "title": "[PLAYLIST] " + snippet.get("title", ""),
                    "url": f"https://www.youtube.com/playlist?list={playlist_id}",
                    "channel": snippet.get("channelTitle", ""),
                    "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", "")
                }]

        # Step 3: Score videos by engagement (views × likes × comments)
        video_ids = [item["id"]["videoId"] for item in items if item["id"].get("kind") == "youtube#video"]
        if not video_ids:
            return _curated_video(skill) or []

        stats_url = "https://www.googleapis.com/youtube/v3/videos"
        stats_params = {"part": "statistics,snippet", "id": ",".join(video_ids), "key": YOUTUBE_API_KEY}
        stats_res = requests.get(stats_url, params=stats_params, timeout=10)

        if stats_res.status_code != 200:
            snippet = items[0].get("snippet", {})
            return [{
                "title": snippet.get("title", ""),
                "url": f"https://www.youtube.com/watch?v={video_ids[0]}",
                "channel": snippet.get("channelTitle", ""),
                "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", "")
            }]

        videos = stats_res.json().get("items", [])
        best_video, best_score = None, -1
        for vid in videos:
            stats = vid.get("statistics", {})
            score = (int(stats.get("viewCount",   0))
                   + int(stats.get("likeCount",   0)) * 10
                   + int(stats.get("commentCount",0)) * 50)
            if score > best_score:
                best_score = score
                best_video = vid

        if best_video:
            snippet = best_video.get("snippet", {})
            return [{
                "title":     snippet.get("title", ""),
                "url":       f"https://www.youtube.com/watch?v={best_video['id']}",
                "channel":   snippet.get("channelTitle", ""),
                "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
                "metrics":   f"{int(best_video.get('statistics',{}).get('viewCount',0)):,} views"
            }]

        return _curated_video(skill) or []

    except Exception as e:
        print(f"[course_fetcher] YouTube API error for '{skill}': {e}")
        return _curated_video(skill) or [{
            "title": f"Search YouTube for '{skill}'",
            "url": f"https://www.youtube.com/results?search_query={skill.replace(' ', '+')}+full+course+tutorial",
            "channel": "YouTube Search", "thumbnail": ""
        }]



def fetch_courses_for_skill(skill):
    """
    Fetch all course links for a given skill.
    Combines YouTube API results with direct search links for other platforms.
    
    Returns:
      {
        "youtube_tutorials": [ ... direct video links ... ],
        "coursera": "https://www.coursera.org/search?query=python",
        "udemy": "https://www.udemy.com/courses/search/?q=python",
        "google": "https://www.google.com/search?q=learn+python+free+course",
        "freecodecamp": "https://www.freecodecamp.org/news/search/?query=python"
      }
    """
    skill_query = skill.replace(' ', '+')
    
    return {
        "youtube_tutorials": fetch_youtube_tutorials(skill),
        "coursera": f"https://www.coursera.org/search?query={skill_query}",
        "udemy": f"https://www.udemy.com/courses/search/?q={skill_query}",
        "google": f"https://www.google.com/search?q=learn+{skill_query}+free+course",
        "freecodecamp": f"https://www.freecodecamp.org/news/search/?query={skill_query}"
    }


def fetch_courses_for_skills_batch(skills, max_youtube_per_skill=2):
    """
    Fetch courses for multiple skills at once.
    Returns a dict keyed by skill name.
    
    Note: Each YouTube search costs 100 quota units.
    With 10,000 units/day free, you can search ~100 skills/day.
    """
    results = {}
    for skill in skills:
        results[skill] = {
            "youtube_tutorials": fetch_youtube_tutorials(skill, max_results=max_youtube_per_skill),
            "coursera": f"https://www.coursera.org/search?query={skill.replace(' ', '+')}",
            "udemy": f"https://www.udemy.com/courses/search/?q={skill.replace(' ', '+')}",
            "google": f"https://www.google.com/search?q=learn+{skill.replace(' ', '+')}+free+course",
            "freecodecamp": f"https://www.freecodecamp.org/news/search/?query={skill.replace(' ', '+')}"
        }
    return results
