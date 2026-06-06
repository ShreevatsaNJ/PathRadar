import requests
import time
import json
import os

BASE_URL = "http://127.0.0.1:5000"

# Locate dummy resume relative to this script
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DUMMY_RESUME_PATH = os.path.join(_SCRIPT_DIR, 'dummy_resume.txt')

def test_endpoints():
    print("Starting API Tests...\n")
    
    # Wait for server to start
    time.sleep(2)
    
    client = requests.Session()
    
    # 1. Test /api/analyze
    print("1. Testing /api/analyze...")
    try:
        with open(DUMMY_RESUME_PATH, 'rb') as f:
            files = {'resume': f}
            payload = {
                "roles": "Software / IT",
                "location": "India"
            }
            res = client.post(f"{BASE_URL}/api/analyze", files=files, data=payload)
        res.raise_for_status()
        analyze_data = res.json()
        print("OK /api/analyze success!")
        session_id = analyze_data.get("session_id")
        print(f"   Session ID: {session_id}")
        
        # Check roles analyzed
        roles = analyze_data.get("role_results", [])
        print(f"   Roles Analyzed: {len(roles)}")
        for role in roles:
            print(f"     - {role['role']}: {role['match_percentage']:.1f}% Match")
            
        if not session_id:
            print("X No session_id returned!")
            return
            
        # 1.1 Verify unauthorized access check
        print("1.1 Testing unauthorized session access (no cookies)...")
        unauth_res = requests.get(f"{BASE_URL}/api/apply-jobs/{session_id}", params={"threshold": 70})
        if unauth_res.status_code == 403:
            print("OK Unauthorized access correctly blocked (403)!")
        else:
            print(f"X Unauthorized access check failed: expected 403, got {unauth_res.status_code}")
            return
            
    except Exception as e:
        print(f"X /api/analyze failed: {e}")
        return

    # 2. Test /api/apply-jobs
    print("\n2. Testing /api/apply-jobs...")
    try:
        res = client.get(f"{BASE_URL}/api/apply-jobs/{session_id}", params={"threshold": 70})
        res.raise_for_status()
        jobs_data = res.json()
        print("OK /api/apply-jobs success!")
        print(f"   Roles matching threshold: {len(jobs_data.get('jobs', []))}")
            
    except Exception as e:
        print(f"X /api/apply-jobs failed: {e}")
        try:
            print(f"   Response: {res.text}")
        except:
            pass

    # 3. Test /api/learning-path
    print("\n3. Testing /api/learning-path...")
    try:
        target_role = roles[0]['role'] if roles else "Software Engineer"
        res = client.get(f"{BASE_URL}/api/learning-path/{session_id}", params={"role": target_role})
        res.raise_for_status()
        path_data = res.json()
        print("OK /api/learning-path success!")
        clusters = path_data.get("learning_path", {}).get("clusters", [])
        print(f"   Clusters: {[c.get('cluster') for c in clusters]}")
        if clusters:
            first_cluster = clusters[0]
            skills = first_cluster.get('skills', [])
            if skills:
                first_skill = skills[0]
                print(f"   First Skill in {first_cluster.get('cluster')}: {first_skill.get('skill')}")
                courses = first_skill.get('courses', {})
                print(f"   YouTube links: {len(courses.get('youtube_tutorials', [])) if courses else 0}")
    except Exception as e:
        print(f"X /api/learning-path failed: {e}")
        try:
            print(f"   Response: {res.text}")
        except:
            pass

    # 4. Test /api/dashboard-chart
    print("\n4. Testing /api/dashboard-chart...")
    try:
        res = client.get(f"{BASE_URL}/api/dashboard-chart/{session_id}", params={"type": "roles"})
        res.raise_for_status()
        print("OK /api/dashboard-chart success!")
        print(f"   Content-Type: {res.headers.get('Content-Type')}")
        print(f"   Image size: {len(res.content)} bytes")
        
        # Save image for verification
        with open("test_chart.png", "wb") as f:
            f.write(res.content)
        print("   Chart saved to test_chart.png")
    except Exception as e:
        print(f"X /api/dashboard-chart failed: {e}")
        try:
            print(f"   Response: {res.text}")
        except:
            pass

if __name__ == "__main__":
    test_endpoints()
