import sys
from pymongo import MongoClient
import requests

# MongoDB connection settings
MONGO_URI = "mongodb://root:example@localhost:27017"
DATABASE_NAME = "my_database"
COLLECTION_NAME = "users"
URL = "http://localhost:8000/"

def get_db_connection():
    """Connect to MongoDB and return the database and collection."""
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    collection = db[COLLECTION_NAME]
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
    params = {"username": username, "password": password, "secret_key": "shh"}
    try:
        response = requests.post(URL + "register", params=params)
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

def print_usage():
    """Print usage instructions."""
    print("\nUser Manager CLI Tool")
    print("Usage:")
    print("  python user_manager.py list               - List all users")
    print("  python user_manager.py add <username> <password> - Add a new user")
    print("  python user_manager.py remove <username>  - Remove a user")

def main():
    if len(sys.argv) < 2:
        print_usage()
        return

    command = sys.argv[1]

    if command == "list":
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
    else:
        print(f"Error: Unknown command '{command}'.")
        print_usage()

if __name__ == "__main__":
    main()