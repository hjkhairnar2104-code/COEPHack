from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "edi_parser"

client = AsyncIOMotorClient(MONGO_URL)
database = client[DB_NAME]
users_collection = database["users"]