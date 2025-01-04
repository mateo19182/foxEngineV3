import os
import io
import pandas as pd

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from bson.objectid import ObjectId

app = FastAPI()

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

client = MongoClient(MONGO_URI)
db = client["my_database"]
collection = db["records"]

# Pages
@app.get("/", response_class=HTMLResponse)
def home():
    """Home page with search/edit UI."""
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/upload", response_class=HTMLResponse)
def upload_page():
    """CSV upload page."""
    with open("templates/upload.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.post("/upload-csv")
async def upload_csv(request: Request):
    """
    Expects JSON like:
    {
      "rows": [ [col1, col2, ...], [col1, col2, ...], ... ],
      "columns": [ "FieldA", "FieldB", ... ]
    }
    First row was used as column names, so we skip it in 'rows' if user wants.
    But here, let's assume the 'rows' are strictly the data rows (excluding header).
    """
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

# The rest of the CRUD endpoints (search, list, delete, update) are similar to earlier examples:

@app.get("/list")
def list_records(skip: int = 0, limit: int = 50):
    data = []
    for doc in collection.find().skip(skip).limit(limit):
        doc["_id"] = str(doc["_id"])
        data.append(doc)
    return data

@app.delete("/record/{record_id}")
def delete_record(record_id: str):
    res = collection.delete_one({"_id": ObjectId(record_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": True}

@app.put("/record/{record_id}")
async def update_record(record_id: str, request: Request):
    body = await request.json()
    body.pop("_id", None)
    res = collection.update_one({"_id": ObjectId(record_id)}, {"$set": body})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"updated": True}

@app.get("/search")
def search_records(params: str = ""):
    if not params:
        data = []
        for doc in collection.find().limit(200):
            doc["_id"] = str(doc["_id"])
            data.append(doc)
        return data

    query_dict = {}
    for p in params.split("&"):
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        query_dict[k.strip()] = v.strip()
    data = []
    for doc in collection.find(query_dict).limit(200):
        doc["_id"] = str(doc["_id"])
        data.append(doc)
    return data

@app.get("/download-csv")
def download_csv(params: str = ""):
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