# app.py
import os
import io
import pandas as pd
from fastapi import FastAPI, Request, HTTPException, Depends, status
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials, OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
from typing import Optional
import bcrypt
import secrets
import pymongo
import datetime
from datetime import datetime, timedelta
from jose import JWTError, jwt

app = FastAPI()
load_dotenv()  # Load environment variables from .env file
secret_key = os.getenv("SECRET_KEY")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Basic setup
MONGO_HOST = os.environ.get("MONGO_HOST", "mongo")
MONGO_USER = os.environ.get("MONGO_USER", "")
MONGO_PASS = os.environ.get("MONGO_PASS", "")

if MONGO_USER:
    MONGO_URI = f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}:27017"
else:
    MONGO_URI = f"mongodb://{MONGO_HOST}:27017"

client = MongoClient(MONGO_URI, server_api=ServerApi("1"))
db = client["my_database"]

# Create a collection with schema validation
try:
    db.create_collection("records", validator={
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["source", "username", "createdAt", "lastModified"],
            "properties": {
                "source": {
                    "bsonType": "string",
                    "description": "source must be a string and is required"
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
                # We don't define other fields to keep it flexible
            },
            "additionalProperties": True  # Allow additional fields
        }
    })
except Exception as e:
    print(e)
    # Collection might already exist
    pass

# Get collection after ensuring it exists
collection = db["records"]

# Create indexes for common queries
collection.create_index([("source", 1), ("username", 1)], unique=True)
# collection.create_index([("createdAt", 1)])
# collection.create_index([("lastModified", 1)])

users_collection = db["users"]

# Simple session storage (in production, use proper session management)
sessions = {}

security = HTTPBasic()

# Add these settings at the top with other configs
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")  # Change in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def authenticate_user(credentials: HTTPBasicCredentials = Depends(security)):
    user = users_collection.find_one({"username": credentials.username})
    
    if not user or not verify_password(credentials.password, user['password']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Add these new functions
def create_access_token(data: dict):
    """Create a JWT token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Verify JWT token and return user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = users_collection.find_one({"username": username})
    if user is None:
        raise credentials_exception
    return username

# Replace the login endpoint
@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = users_collection.find_one({"username": form_data.username})
    if not user or not verify_password(form_data.password, user['password']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user["username"]})
    return {"access_token": access_token, "token_type": "bearer"}

# Replace the login endpoint
@app.post("/login")
async def login(request: Request):
    form_data = await request.form()
    username = form_data.get("username")
    password = form_data.get("password")
    
    user = users_collection.find_one({"username": username})
    if not user or not verify_password(password, user['password']):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token(data={"sub": username})
    
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax"
    )
    return response

# Update the current user middleware
async def get_current_user(request: Request):
    """Get current user from JWT token in cookie or header."""
    # Try to get token from cookie first (for web interface)
    token = request.cookies.get("access_token")
    if token and token.startswith("Bearer "):
        token = token.split(" ")[1]
    else:
        # Try to get token from Authorization header (for API)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            return None
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError:
        return None

# Update logout to handle JWT
@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with search/edit UI."""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    """CSV upload page."""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    with open("templates/upload.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# Authentication routes
@app.get("/login", response_class=HTMLResponse)
def login_page():
    """Login page."""
    with open("templates/login.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# Add this to all protected routes
async def protected_route(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

# Update the upload_csv endpoint
@app.post("/upload-csv")
async def upload_csv(request: Request): # , user: str = Depends(protected_route)
    data = await request.json()
    rows = data.get("rows", [])
    columns = data.get("columns", [])
    if not rows or not columns:
        raise HTTPException(status_code=400, detail="No data provided")

    # Verify required fields are present
    if "source" not in columns or "username" not in columns:
        raise HTTPException(
            status_code=400, 
            detail="CSV must contain 'source' and 'username' columns"
        )

    current_time = datetime.datetime.utcnow()
    records = []
    for r in rows:
        rec = {}
        for i, col in enumerate(columns):
            if i < len(r):
                rec[col] = r[i]
        
        # Add required fields
        rec["createdAt"] = current_time
        rec["lastModified"] = current_time
        records.append(rec)

    try:
        res = collection.insert_many(records, ordered=False)
        return {"inserted_count": len(res.inserted_ids)}
    except pymongo.errors.BulkWriteError as e:
        # Handle duplicate key errors
        return {
            "inserted_count": e.details['nInserted'],
            "duplicate_count": len(e.details['writeErrors'])
        }

@app.post("/register")
async def register_user(request: Request, username: str, password: str):
    
    if users_collection.find_one({"username": username}):
        raise HTTPException(status_code=400, detail="Username already exists")
    
    users_collection.insert_one({
        "username": username,
        "password": get_password_hash(password) 
    })
    return {"message": "User created"}

# The rest of the CRUD endpoints (search, list, delete, update) are similar to earlier examples:

@app.get("/list")
def list_records(skip: int = 0, limit: int = 50, current_user: dict = Depends(get_current_user)):
    data = []
    for doc in collection.find().skip(skip).limit(limit):
        doc["_id"] = str(doc["_id"])
        data.append(doc)
    return data

@app.delete("/record/{record_id}")
def delete_record(record_id: str, current_user: dict = Depends(get_current_user)):
    res = collection.delete_one({"_id": ObjectId(record_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": True}

@app.put("/record/{record_id}")
async def update_record(record_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    body = await request.json()
    body.pop("_id", None)
    body["lastModified"] = datetime.datetime.utcnow()  # Update lastModified
    
    # Prevent modification of source, username, and createdAt
    body.pop("source", None)
    body.pop("username", None)
    body.pop("createdAt", None)
    
    res = collection.update_one(
        {"_id": ObjectId(record_id)}, 
        {"$set": body}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"updated": True}

@app.get("/search")
def search_records(
    params: str = "",
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    try:
        if not params:
            # Return all records if no search parameters are provided
            data = []
            for doc in collection.find().skip(skip).limit(limit):
                doc["_id"] = str(doc["_id"])
                data.append(doc)
            return data

        # Parse the query parameters
        query_dict = {}
        for p in params.split("&"):
            if "=" not in p:
                continue
            k, v = p.split("=", 1)
            k = k.strip()
            v = v.strip()
            
            # Check if the value is a regex pattern
            if v.startswith("/") and v.endswith("/"):
                # Extract the regex pattern (remove the leading and trailing slashes)
                regex_pattern = v[1:-1]
                query_dict[k] = {"$regex": regex_pattern, "$options": "i"}  # Case-insensitive regex
            else:
                # Treat it as a literal search (allow partial matches)
                query_dict[k] = {"$regex": v, "$options": "i"}  # Partial match (case-insensitive)

        print(f"Query Dict: {query_dict}")  # Debugging: Print the query dictionary

        # Execute the query
        data = []
        for doc in collection.find(query_dict).skip(skip).limit(limit):
            doc["_id"] = str(doc["_id"])
            data.append(doc)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download-csv")
def download_csv(params: str = "", current_user: dict = Depends(get_current_user)):
    if not params:
        cursor = collection.find()
    else:
        query_dict = {}
        for p in params.split("&"):
            if "=" not in p:
                continue
            k, v = p.split("=", 1)
            query_dict[k.strip()] = v.strip()
        cursor = collection.find(query_dict)

    rows = list(cursor)
    df = pd.DataFrame(rows)
    if not df.empty and "_id" in df.columns:
        df["_id"] = df["_id"].astype(str)

    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=records.csv"}
    )
    
@app.get("/count")
def count_records():
    """Return the total number of records in the collection."""
    total = collection.count_documents({})
    return {"total_records": total}

# Example protected route
@app.get("/protected")
async def protected_route(username: str = Depends(authenticate_user)):
    return {"message": f"Hello {username}"}