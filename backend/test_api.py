import requests
import time
import json
import os

BASE_URL = "http://127.0.0.1:5000"

def test_endpoints():
    print("Starting API Tests...\n")
    
    # Wait for server to start
    time.sleep(2)
    
    # 1. Test /api/analyze
    print("1. Testing /api/analyze...")
    try:
        with open('dummy_resume.txt', 'rb') as f:
            files = {'resume': f}
            payload = {
                "roles": "Software / IT",
                "location": "India"
            }
            res = requests.post(f"{BASE_URL}/api/analyze", files=files, data=payload)
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
            
    except Exception as e:
        print(f"X /api/analyze failed: {e}")
        return

    # 2. Test /api/apply-jobs
    print("\n2. Testing /api/apply-jobs...")
    try:
        # We'll use the first role from the previous step
        target_role = roles[0]['role'] if roles else "Software Engineer"
        res = requests.get(f"{BASE_URL}/api/apply-jobs", params={"session_id": session_id, "role": target_role})
        res.raise_for_status()
        jobs_data = res.json()
        print("OK /api/apply-jobs success!")
        print(f"   Jobs Found: {len(jobs_data.get('jobs', []))}")
        if jobs_data.get('jobs'):
            print(f"   First Job: {jobs_data['jobs'][0].get('job_title')} at {jobs_data['jobs'][0].get('employer_name')}")
            
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
        res = requests.get(f"{BASE_URL}/api/learning-path", params={"session_id": session_id, "role": target_role})
        res.raise_for_status()
        path_data = res.json()
        print("OK /api/learning-path success!")
        clusters = path_data.get("learning_path", {}).get("skill_clusters", {})
        print(f"   Clusters: {list(clusters.keys())}")
        if clusters:
            first_cluster = list(clusters.keys())[0]
            if clusters[first_cluster]:
                first_skill = clusters[first_cluster][0]
                print(f"   First Skill in {first_cluster}: {first_skill.get('skill')}")
                print(f"   YouTube links: {len(first_skill.get('resources', {}).get('youtube_tutorials', []))}")
    except Exception as e:
        print(f"X /api/learning-path failed: {e}")
        try:
            print(f"   Response: {res.text}")
        except:
            pass

    # 4. Test /api/dashboard-chart
    print("\n4. Testing /api/dashboard-chart...")
    try:
        res = requests.get(f"{BASE_URL}/api/dashboard-chart", params={"session_id": session_id, "chart_type": "role_match"})
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
