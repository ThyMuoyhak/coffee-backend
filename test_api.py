# test_api.py
import requests
import json

BASE_URL = "http://localhost:10000"

def test_endpoint(endpoint, method="GET", data=None):
    try:
        if method == "GET":
            response = requests.get(f"{BASE_URL}{endpoint}")
        elif method == "POST":
            response = requests.post(f"{BASE_URL}{endpoint}", json=data)
        elif method == "DELETE":
            response = requests.delete(f"{BASE_URL}{endpoint}")
        
        print(f"{method} {endpoint}: Status {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {json.dumps(response.json(), indent=2)[:200]}...")
        else:
            print(f"Error: {response.text[:200]}")
        print("-" * 50)
        return response
    except Exception as e:
        print(f"Error testing {endpoint}: {e}")
        print("-" * 50)
        return None

print("Testing API Endpoints...")
print("=" * 50)

# Test 1: Root endpoint
test_endpoint("/")

# Test 2: Health endpoint
test_endpoint("/health")

# Test 3: Products endpoint
test_endpoint("/api/v1/products/")

# Test 4: Admin login
test_endpoint("/api/v1/admin/login", "POST", {
    "email": "admin@gmail.com",
    "password": "11112222"
})

print("All tests completed!")