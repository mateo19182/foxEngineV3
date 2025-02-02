import sys
from pymongo import MongoClient
import requests
from app.database.client import client, db, users_collection
from app.auth.utils import get_password_hash
from app.config import API_URL, MONGO_URI
import json
import os
import csv
from typing import List, Dict

# MongoDB connection settings
DATABASE_NAME = "my_database"
COLLECTION_NAME = "users"
URL = "http://localhost:8000/"

def get_db_connection():
    """Connect to MongoDB and return the database and collection."""
    client = MongoClient(MONGO_URI)
    db = client["my_database"]
    collection = db["users"]
    return collection

def list_users():
    """List all users in the database."""
    collection = get_db_connection()
    users = collection.find({}, {"_id": 0, "username": 1, "password": 1})
    if users:
        print("\nList of Users:")
        for user in users:
            print(f"Username: {user['username']}, Password: {user['password']}")
    else:
        print("No users found.")

def add_user(username, password):
    """Add a new user to the database."""
    try:
        response = requests.post(
            API_URL + "register",
            params={"username": username, "password": password}
        )
        if response.status_code == 200:
            print(f"User '{username}' added successfully.")
        else:
            print(f"Error: Could not add user '{username}'. Status code: {response.status_code}, Response: {response.text}")
    except Exception as e:
        print(f"Error: Could not add user '{username}'. {e}")

         
def remove_user(username):
    """Remove a user from the database."""
    collection = get_db_connection()
    result = collection.delete_one({"username": username})
    if result.deleted_count > 0:
        print(f"User '{username}' removed successfully.")
    else:
        print(f"Error: User '{username}' not found.")

def list_databases_and_collections():
    client = MongoClient(MONGO_URI)
    db_names = client.list_database_names()
    for db_name in db_names:
        print(f"\nDatabase: {db_name}")
        col_names = client[db_name].list_collection_names()
        for col_name in col_names:
            print(f"  Collection: {col_name}")


def add_collection(db_name, collection_name):
    """Add a new collection to a specified database."""
    try:
        client = MongoClient(MONGO_URI)
        db = client[db_name]
        db.create_collection(collection_name)
        print(f"Collection '{collection_name}' created successfully in database '{db_name}'.")
    except Exception as e:
        print(f"Error creating collection: {e}")

def get_collection_schema(db_name, collection_name):
    """Display the schema of a specified collection by analyzing its documents."""
    try:
        client = MongoClient(MONGO_URI)
        db = client[db_name]
        collection = db[collection_name]
        
        # Get a sample document
        sample = collection.find_one()
        
        if not sample:
            print(f"Collection '{collection_name}' is empty.")
            return
            
        def analyze_value(value):
            if isinstance(value, dict):
                return {k: type(v).__name__ for k, v in value.items()}
            return type(value).__name__
            
        schema = {k: analyze_value(v) for k, v in sample.items()}
        
        print(f"\nSchema for collection '{collection_name}' in database '{db_name}':")
        for field, type_info in schema.items():
            if isinstance(type_info, dict):
                print(f"{field}: {{")
                for sub_field, sub_type in type_info.items():
                    print(f"  {sub_field}: {sub_type}")
                print("}")
            else:
                print(f"{field}: {type_info}")
                
    except Exception as e:
        print(f"Error getting collection schema: {e}")


def load_test_data() -> List[Dict]:
    """Load test data from both JSON and CSV files."""
    test_data = []
    
    # Load JSON data
    json_path = os.path.join(os.path.dirname(__file__), 'app', 'data', 'test_data.json')
    try:
        with open(json_path, 'r') as f:
            test_data.extend(json.load(f)['records'])
    except Exception as e:
        print(f"Warning: Could not load JSON test data: {e}")

    # Load CSV data
    csv_path = os.path.join(os.path.dirname(__file__), 'app', 'data', 'test_data.csv')
    try:
        with open(csv_path, 'r') as f:
            csv_reader = csv.DictReader(f)
            for row in csv_reader:
                # Convert string values to appropriate types
                if 'age' in row:
                    row['age'] = int(row['age'])
                if 'active' in row:
                    row['active'] = row['active'].lower() == 'true'
                if 'tags' in row:
                    row['tags'] = [tag.strip() for tag in row['tags'].split(',')]
                test_data.append(row)
    except Exception as e:
        print(f"Warning: Could not load CSV test data: {e}")

    return test_data


def add_test_data():
    """Add test data through the API."""
    try:
        # First get JWT token
        response = requests.post(
            API_URL + "token",
            data={"username": "admin", "password": "admin"}
        )
        if response.status_code != 200:
            print(f"Failed to authenticate: {response.text}")
            return
        
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Load and send JSON test data
        json_path = os.path.join(os.path.dirname(__file__), 'app', 'data', 'test_data.json')
        with open(json_path, 'r') as f:
            json_data = json.load(f)
            # Changed to handle direct list of records instead of nested structure
            records = json_data  # Now expecting direct list of records
            columns = list(records[0].keys()) if records else []
            rows = [
                [record[col] for col in columns]
                for record in records
            ]
            payload = {
                "rows": rows,
                "columns": columns
            }
            response = requests.post(
                API_URL + "upload-data",
                json=payload,
                headers=headers
            )
            if response.status_code == 200:
                print("Added test records from JSON file.")
            else:
                print(f"Error adding test records from JSON: {response.text}")
    
        # Load and send CSV test data
        csv_path = os.path.join(os.path.dirname(__file__), 'app', 'data', 'test_data.csv')
        with open(csv_path, 'r') as f:
            csv_data = f.read()
            response = requests.post(
                API_URL + "upload-data",
                data=csv_data,
                headers={**headers, "Content-Type": "text/csv"}
            )
            if response.status_code == 200:
                print("Added test records from CSV file.")
            else:
                print(f"Error adding test records from CSV: {response.text}")
    
    except Exception as e:
        print(f"Operation failed: {e}")

def delete_collection(db_name, collection_name):
    """Delete a collection from a specified database."""
    try:
        client = MongoClient(MONGO_URI)
        db = client[db_name]
        
        # Check if collection exists
        if collection_name not in db.list_collection_names():
            print(f"Error: Collection '{collection_name}' does not exist in database '{db_name}'.")
            return
            
        # Drop the collection
        db[collection_name].drop()
        print(f"Collection '{collection_name}' deleted successfully from database '{db_name}'.")
    except Exception as e:
        print(f"Error deleting collection: {e}")

def print_usage():
    """Print usage instructions."""
    print("\nUser Manager CLI Tool")
    print("Usage:")
    print("  python user_manager.py list               - List all users")
    print("  python user_manager.py add <username> <password> - Add a new user")
    print("  python user_manager.py remove <username>  - Remove a user")
    print("  python user_manager.py info               - List all databases and collections")
    print("  python user_manager.py add_collection <db_name> <collection_name> - Add a new collection")
    print("  python user_manager.py del_collection <db_name> <collection_name> - Delete a collection")
    print("  python user_manager.py schema <db_name> <collection_name> - Show collection schema")
    print("  python user_manager.py test_data          - Add test data through API")

def main():
    if len(sys.argv) < 2:
        print_usage()
        return

    command = sys.argv[1]

    if command == "test_data":
        add_test_data()
    elif command == "list":
        list_users()
    elif command == "add":
        if len(sys.argv) != 4:
            print("Error: Missing username or password.")
            print_usage()
        else:
            username = sys.argv[2]
            password = sys.argv[3]
            add_user(username, password)
    elif command == "remove":
        if len(sys.argv) != 3:
            print("Error: Missing username.")
            print_usage()
        else:
            username = sys.argv[2]
            remove_user(username)
    elif command == "info":
        list_databases_and_collections()
    elif command == "add_collection":
        if len(sys.argv) != 4:
            print("Error: Missing database name or collection name.")
            print_usage()
        else:
            db_name = sys.argv[2]
            collection_name = sys.argv[3]
            add_collection(db_name, collection_name)
    elif command == "del_col":
        if len(sys.argv) != 4:
            print("Error: Missing database name or collection name.")
            print_usage()
        else:
            db_name = sys.argv[2]
            collection_name = sys.argv[3]
            delete_collection(db_name, collection_name)
    elif command == "schema":
        if len(sys.argv) != 4:
            print("Error: Missing database name or collection name.")
            print_usage()
        else:
            db_name = sys.argv[2]
            collection_name = sys.argv[3]
            get_collection_schema(db_name, collection_name)
    else:
        print(f"Error: Unknown command '{command}'.")
        print_usage()

if __name__ == "__main__":
    main()