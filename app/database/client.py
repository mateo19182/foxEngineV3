from pymongo import MongoClient
from pymongo.server_api import ServerApi
from ..config import MONGO_URI

client = MongoClient(MONGO_URI, server_api=ServerApi("1"))
db = client["my_database"]
collection = db["records"]
users_collection = db["users"]

# Initialize collections and indexes
def init_db():
    try:
        db.create_collection("records", validator={
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["username", "createdAt", "lastModified"],
                "properties": {
                    "source": {
                        "bsonType": "string",
                        "description": "source must be a string if present"
                    },
                    "username": {
                        "bsonType": "string",
                        "description": "username must be a string and is required"
                    },
                    "createdAt": {
                        "bsonType": "date",
                        "description": "createdAt must be a date and is required"
                    },
                    "lastModified": {
                        "bsonType": "date",
                        "description": "lastModified must be a date and is required"
                    }
                },
                "additionalProperties": True
            }
        })
    except Exception as e:
        print(f"Collection might already exist: {e}")

    # Create indexes
    collection.create_index([("username", 1)], unique=True)
    collection.create_index([("createdAt", 1)])
    collection.create_index([("lastModified", 1)])
