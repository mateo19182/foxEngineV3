from datetime import datetime
from ..database.client import db

# Create a new collection for logs
logs_collection = db.logs

def log_api_call(endpoint: str, method: str, user: str = None, status_code: int = 200, error: str = None, additional_info: str = None):
    """Log API calls to MongoDB"""
    log_entry = {
        "timestamp": datetime.utcnow(),
        "endpoint": endpoint,
        "method": method,
        "user": user,
        "status_code": status_code,
        "error": error,
        "additional_info": additional_info
    }
    logs_collection.insert_one(log_entry) 