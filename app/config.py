import os
from dotenv import load_dotenv

load_dotenv()

# MongoDB settings
MONGO_HOST = os.environ.get("MONGO_HOST", "localhost")
MONGO_USER = os.environ.get("MONGO_USER", "root")
MONGO_PASS = os.environ.get("MONGO_PASS", "example")

if MONGO_USER:
    MONGO_URI = f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}:27017"
else:
    MONGO_URI = f"mongodb://{MONGO_HOST}:27017"

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

# API settings
API_URL = os.environ.get("API_URL", "http://localhost:8000/")