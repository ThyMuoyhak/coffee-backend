# test_deployed.py
import requests
import json

BASE_URL = "https://coffee-backend-1.onrender.com"

def test_deployment():
    endpoints = [
        ("GET", "/", "Root endpoint"),
        ("GET", "/health", "Health check"),
        ("GET", "/api/v1/products/", "Products list"),
        ("POST", "/api/v1/admin/login", "Admin login")
    ]
    
    login_data = {
        "email": "admin@gmail.com",
        "password": "11112222"
    }
    
    print(f"🧪 Testing deployed API at: {BASE_URL}")
    print("=" * 70)
    
    for method, endpoint, description in endpoints:
        print(f"\n📡 Testing: {description}")
        print(f"   Endpoint: {method} {endpoint}")
        
        try:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            elif method == "POST" and "login" in endpoint:
                response = requests.post(f"{BASE_URL}{endpoint}", json=login_data, timeout=10)
            else:
                response = requests.post(f"{BASE_URL}{endpoint}", timeout=10)
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                print("   ✅ SUCCESS")
                try:
                    data = response.json()
                    print(f"   Response: {json.dumps(data, indent=2)[:200]}...")
                except:
                    print(f"   Response: {response.text[:200]}")
            else:
                print("   ❌ ERROR")
                print(f"   Error: {response.text[:200]}")
                
        except requests.exceptions.Timeout:
            print("   ⏱️ TIMEOUT: Request took too long")
        except requests.exceptions.ConnectionError:
            print("   🔌 CONNECTION ERROR: Could not connect to server")
        except Exception as e:
            print(f"   ❌ EXCEPTION: {e}")
    
    print("\n" + "=" * 70)
    print("✅ Testing completed!")
    
    # Additional info
    print(f"\n📋 Important URLs:")
    print(f"   API Root: {BASE_URL}/")
    print(f"   API Docs: {BASE_URL}/docs")
    print(f"   Health: {BASE_URL}/health")
    print(f"   Admin Login: {BASE_URL}/api/v1/admin/login")
    
    print(f"\n🔑 Test credentials:")
    print(f"   Email: admin@gmail.com")
    print(f"   Password: 11112222")

if __name__ == "__main__":
    test_deployment()