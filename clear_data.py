"""
Clean All Data Script
Clears all collections in the EmoGo database
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URI = "mongodb+srv://Rafa-612:eQ8IOESaO4lyLnm2@rafa-612.qiobhis.mongodb.net/?appName=Rafa-612"
DB_NAME = "emogo_db"

async def clear_all_data():
    print("🧹 Starting database cleanup...")
    
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DB_NAME]
    
    try:
        # Clear sentiments
        result = await db["sentiments"].delete_many({})
        print(f"✅ Deleted {result.deleted_count} sentiments")
        
        # Clear vlogs
        result = await db["vlogs"].delete_many({})
        print(f"✅ Deleted {result.deleted_count} vlogs")
        
        # Clear GPS
        result = await db["gps"].delete_many({})
        print(f"✅ Deleted {result.deleted_count} GPS records")
        
        # Clear items (if any)
        result = await db["items"].delete_many({})
        print(f"✅ Deleted {result.deleted_count} items")
        
        print("\n🎉 All data cleared successfully!")
        print("📅 Data collection restart time: ", end="")
        from datetime import datetime
        print(datetime.utcnow().isoformat() + "Z")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(clear_all_data())
