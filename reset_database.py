# reset_database.py
import asyncio
import os
import sys

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import database, engine, Base
from models import CoffeeProduct, CartItem, Order, AdminUser
import hashlib
from datetime import datetime

async def reset_database():
    print("🧨 RESETTING DATABASE...")
    
    try:
        # Connect to database
        await database.connect()
        print("✅ Connected to database")
        
        # Drop all tables
        print("🗑️ Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        
        # Create all tables fresh
        print("🔨 Creating tables...")
        Base.metadata.create_all(bind=engine)
        
        # Create admin with SHA256 hash
        print("👤 Creating admin user...")
        salt = "brewhaven-coffee-shop-salt"
        password = "11112222"
        hashed_password = hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
        
        insert_query = """
        INSERT INTO admin_users (email, hashed_password, full_name, role, is_active, created_at)
        VALUES (:email, :hashed_password, :full_name, :role, :is_active, :created_at)
        """
        
        await database.execute(
            query=insert_query,
            values={
                "email": "admin@gmail.com",
                "hashed_password": hashed_password,
                "full_name": "System Administrator",
                "role": "super_admin",
                "is_active": True,
                "created_at": datetime.utcnow()
            }
        )
        
        print("✅ Admin created successfully!")
        print(f"   Email: admin@gmail.com")
        print(f"   Password: 11112222")
        print(f"   Hash (SHA256): {hashed_password}")
        print(f"   Hash length: {len(hashed_password)} characters")
        
        # Create sample products
        print("📦 Creating sample products...")
        sample_products = [
            {
                "name": "Mondulkiri Arabica",
                "price": 4.50,
                "image": "https://images.unsplash.com/photo-1587734195503-904fca47e0e9?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=80",
                "description": "Single origin from Cambodian highlands with rich flavor notes",
                "category": "Hot Coffee",
                "rating": 4.8,
                "brew_time": "4-5 min",
                "is_available": True,
                "stock": 100
            },
            {
                "name": "Phnom Penh Cold Brew",
                "price": 5.25,
                "image": "https://images.unsplash.com/photo-1461023058943-07fcbe16d735?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=80",
                "description": "Smooth 12-hour cold extraction with chocolate undertones",
                "category": "Cold Brew",
                "rating": 4.9,
                "brew_time": "12 hours",
                "is_available": True,
                "stock": 85
            }
        ]
        
        for product in sample_products:
            query = CoffeeProduct.__table__.insert().values(**product)
            await database.execute(query)
        
        print(f"✅ Created {len(sample_products)} sample products")
        
        print("\n🎉 DATABASE RESET COMPLETE!")
        print("\n🔑 Login credentials:")
        print("   Email: admin@gmail.com")
        print("   Password: 11112222")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await database.disconnect()
        print("✅ Database disconnected")

if __name__ == "__main__":
    asyncio.run(reset_database())