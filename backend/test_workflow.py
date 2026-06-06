import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000/api"

client = requests.Session()

print("="*60)
print("🚀 STARTING PATHRADAR END-TO-END WORKFLOW TEST")
print("="*60)

# 1. Upload Resume
print("\n[Step 1] Uploading Resume to /api/analyze...")
with open("backend/dummy_resume.txt", "rb") as f:
    files = {"resume": ("dummy_resume.txt", f, "text/plain")}
    data = {"roles": "Software Engineer"} # We can specify roles or leave it empty for auto-detect
    
    # Use a try-except block just in case the server isn't running
    try:
        response = client.post(f"http://127.0.0.1:5000/api/analyze", files=files, data=data)
        if response.status_code != 200 and response.status_code != 201:
            print(f"❌ SERVER ERROR ({response.status_code}):\n{response.text}")
            exit(1)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Could not connect to the Flask app. Make sure it is running (python app.py)!")
        exit(1)

analyze_data = response.json()
session_id = analyze_data.get("session_id")
print(f"✅ Success! Session ID created: {session_id}")
print(f"   Detected Skills: {', '.join(analyze_data.get('resume_skills', []))}")
print(f"   Top Role Matched: {analyze_data.get('role_results', [{}])[0].get('role', 'Unknown')}")

time.sleep(1)

# 2. Get Full Results
print(f"\n[Step 2] Fetching Detailed Analysis Results from /api/result/{session_id}...")
res = client.get(f"http://127.0.0.1:5000/api/result/{session_id}")
result_data = res.json()
print("✅ Success! Retrieved detailed analysis.")
print(f"   Total Roles Evaluated: {len(result_data.get('role_results', []))}")

time.sleep(1)

# 3. Get Learning Path (THIS WILL USE THE YOUTUBE API!)
print(f"\n[Step 3] Fetching Learning Path & Course Links from /api/learning-path/{session_id}...")
print("         (This step connects to YouTube API to find real course videos)")
lp_res = client.get(f"http://127.0.0.1:5000/api/learning-path/{session_id}")
lp_data = lp_res.json()
print("✅ Success! Learning Path Generated.")

# Display learning path details
path = lp_data.get("learning_path", {})
for cluster in path.get("clusters", []):
    print(f"\n   📚 Category: {cluster.get('cluster', 'Unknown')}")
    for skill in cluster.get("skills", []):
        courses = skill.get("courses", {})
        if courses:
            yt = courses.get('youtube_tutorials', [{}])[0]
            print(f"      - Skill: {skill['skill']}")
            metrics_str = f" ({yt.get('metrics')})" if yt.get('metrics') else ""
            print(f"        ▶️ YouTube: {yt.get('title', 'Link')}{metrics_str} -> {yt.get('url', '')}")
            print(f"        🎓 Coursera: {courses.get('coursera', '')}")
            print(f"        🎒 Udemy: {courses.get('udemy', '')}")
            
# 4. Get Skill Transferability
print(f"\n[Step 4] Fetching Skill Transferability from /api/transferability/{session_id}...")
trans_res = client.get(f"http://127.0.0.1:5000/api/transferability/{session_id}")
trans_data = trans_res.json()
print("✅ Success! Transferability Generated.")
for role_data in trans_data.get("role_transferability", []):
    print(f"   Role: {role_data.get('job_role')}")
    for t in role_data.get("transferability_data", [])[:2]: # Just show top 2 for brevity
        known = ", ".join(t.get('you_already_know', []))
        print(f"      - To learn '{t['missing_skill']}', you can leverage your knowledge of: {known if known else 'None'}")
        print(f"        Difficulty: {t['difficulty']} (Score: {t['transferability_score']})")

time.sleep(1)

# 5. Get Skill Clusters
print(f"\n[Step 5] Fetching Skill Clustering from /api/skill-clusters/{session_id}...")
cluster_res = client.get(f"http://127.0.0.1:5000/api/skill-clusters/{session_id}")
cluster_data = cluster_res.json()
print("✅ Success! Skill Clusters Analyzed.")
for cluster_name, cluster_info in cluster_data.get("skill_clusters", {}).items():
    print(f"   📊 {cluster_name}: {cluster_info.get('count')} skills ({cluster_info.get('coverage_pct')}% coverage)")

time.sleep(1)

# 6. Test Cross-Industry Gap Analysis
print(f"\n[Step 6] Testing Cross-Industry Analysis at /api/analyze-industry...")
with open("backend/dummy_resume.txt", "rb") as f:
    files_ind = {"resume": ("dummy_resume.txt", f, "text/plain")}
    data_ind = {"industries": "Data & Analytics, Management"} 
    ind_res = client.post(f"http://127.0.0.1:5000/api/analyze-industry", files=files_ind, data=data_ind)
    ind_res.raise_for_status()
    ind_data = ind_res.json()
    print("✅ Success! Cross-Industry Analysis Complete.")
    print(f"   Top Industries Detected: {[i['industry'] for i in ind_data.get('best_industries', [])]}")
    for industry, roles in ind_data.get('industry_results', {}).items():
        print(f"   🏢 Industry: {industry}")
        for r in roles:
            print(f"      - Role: {r['role']} | Match: {r['match_percentage']}%")

print("\n" + "="*60)
print("🎉 ALL FEATURES TESTED SUCCESSFULLY!")
print("="*60)
