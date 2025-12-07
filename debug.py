# debug.py
import traceback
import sys

print("🔍 Debugging application startup...")

try:
    # Test basic imports
    print("1. Testing imports...")
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    print("   ✅ FastAPI imports OK")
    
    # Test database imports
    from sqlalchemy import create_engine
    print("   ✅ SQLAlchemy imports OK")
    
    # Test your specific imports
    print("2. Testing your specific imports...")
    try:
        from database import database, engine, Base
        print("   ✅ Database imports OK")
    except Exception as e:
        print(f"   ❌ Database import error: {e}")
        traceback.print_exc()
    
    try:
        import models
        print("   ✅ Models import OK")
    except Exception as e:
        print(f"   ❌ Models import error: {e}")
        traceback.print_exc()
    
    try:
        import schemas
        print("   ✅ Schemas import OK")
    except Exception as e:
        print(f"   ❌ Schemas import error: {e}")
        traceback.print_exc()
    
    try:
        import crud
        print("   ✅ CRUD import OK")
    except Exception as e:
        print(f"   ❌ CRUD import error: {e}")
        traceback.print_exc()
    
    try:
        from admin_api import router as admin_router
        print("   ✅ Admin router import OK")
    except Exception as e:
        print(f"   ❌ Admin router import error: {e}")
        traceback.print_exc()
    
    print("3. Creating FastAPI app...")
    app = FastAPI()
    print("   ✅ FastAPI app created")
    
    print("4. Testing CORS middleware...")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    print("   ✅ CORS middleware added")
    
    print("\n🎉 All imports and setup passed!")
    print("\nNext steps:")
    print("1. Run: python main.py")
    print("2. Or run: python simple_server.py (see below)")
    
except Exception as e:
    print(f"\n❌ Critical error: {e}")
    traceback.print_exc()
    print("\n💡 Try installing missing packages:")
    print("pip install fastapi uvicorn sqlalchemy databases python-jose passlib python-multipart")