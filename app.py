# app.py
import os
import io
import pandas as pd
from fastapi import FastAPI, Request, HTTPException, Depends, status
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
from typing import Optional
import bcrypt
import secrets

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
MONGO_HOST = os.environ.get("MONGO_HOST", "localhost")
MONGO_USER = os.environ.get("MONGO_USER", "")
MONGO_PASS = os.environ.get("MONGO_PASS", "")

if MONGO_USER:
    MONGO_URI = f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}:27017"
else:
    MONGO_URI = f"mongodb://{MONGO_HOST}:27017"

client = MongoClient(MONGO_URI, server_api=ServerApi("1"))
db = client["my_database"]
collection = db["records"]
users_collection = db["users"]

# Simple session storage (in production, use proper session management)
sessions = {}

security = HTTPBasic()

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

@app.post("/login")
async def login(request: Request):
    form_data = await request.form()
    username = form_data.get("username")
    password = form_data.get("password")
    
    user = users_collection.find_one({"username": username})
    
    if not user or not verify_password(password, user['password']):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create session
    session_id = secrets.token_hex(16)  # More secure than os.urandom
    sessions[session_id] = username
    
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,  # Prevents JavaScript access
        secure=False,    # Only sends over HTTPS todo change when real!!!!
        samesite="lax"  # Prevents CSRF
    )
    return response

async def get_current_user(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        return None
    
    # Validate that the user still exists
    username = sessions[session_id]
    user = users_collection.find_one({"username": username})
    if not user:
        # Clear invalid session
        sessions.pop(session_id, None)
        return None
        
    return username

# Update the logout endpoint for better security
@app.get("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id in sessions:
        del sessions[session_id]
    
    response = RedirectResponse(url="/login")
    response.delete_cookie(
        key="session_id",
        httponly=True,
        secure=True,
        samesite="lax"
    )
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

@app.post("/login")
async def login(request: Request):
    form_data = await request.form()
    username = form_data.get("username")
    password = form_data.get("password")
    
    user = users_collection.find_one({"username": username, "password": password})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create session
    session_id = os.urandom(16).hex()
    sessions[session_id] = username
    
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="session_id", value=session_id)
    return response

# Add this to all protected routes
async def protected_route(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

# Example of protected route
@app.post("/upload-csv")
async def upload_csv(request: Request, user: str = Depends(protected_route)):
    data = await request.json()
    rows = data.get("rows", [])
    columns = data.get("columns", [])
    if not rows or not columns:
        raise HTTPException(status_code=400, detail="No data provided")

    records = []
    for r in rows:
        rec = {}
        for i, col in enumerate(columns):
            if i < len(r):
                rec[col] = r[i]
        records.append(rec)

    res = collection.insert_many(records)
    return {"inserted_count": len(res.inserted_ids)}

@app.post("/register")
async def register_user(request: Request, secret_key: str, username: str, password: str):
    if secret_key != os.environ.get("SECRET_KEY"):
        raise HTTPException(status_code=403, detail="Invalid secret key")
    
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
    res = collection.update_one({"_id": ObjectId(record_id)}, {"$set": body})
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