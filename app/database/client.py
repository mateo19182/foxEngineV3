from pymongo import MongoClient
from pymongo.server_api import ServerApi
from ..config import MONGO_URI

client = MongoClient(MONGO_URI, server_api=ServerApi("1"))
db = client["my_database"]
collection = db["records"]
users_collection = db["users"]
files_collection = db["files"]
# Initialize collections and indexes
def init_db():
    try:
        db.create_collection("records", validator={
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["createdAt", "lastModified", "file_source", "created_by"],
                "properties": {
                    "file_source": {
                        "bsonType": "string",
                        "description": "file_source must be a string and is required"
                    },
                    "createdAt": {
                        "bsonType": "date",
                        "description": "createdAt must be a date and is required"
                    },
                    "lastModified": {
                        "bsonType": "date",
                        "description": "lastModified must be a date and is required"
                    },
                    "created_by": {
                        "bsonType": "string",
                        "description": "created_by must be a string and is required"
                    }
                },
                "additionalProperties": True
            }
        })
        
        # Initialize files collection
        db.create_collection("files")
        
    except Exception as e:
        print(f"Collection might already exist: {e}")

    # Create indexes
    collection.create_index([("username", 1)], unique=True)
    collection.create_index([("createdAt", 1)])
    collection.create_index([("lastModified", 1)])
    
    # Create indexes for files collection
    files_collection.create_index([("file_hash", 1)])
    files_collection.create_index([("uploaded_by", 1)])
    files_collection.create_index([("uploaded_at", -1)])
