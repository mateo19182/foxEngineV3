from fastapi import APIRouter, Request, HTTPException, Depends
from datetime import datetime
import pymongo
from bson.objectid import ObjectId
import pandas as pd
import io
from fastapi.responses import StreamingResponse
from ..database.client import collection
from ..auth.jwt import get_current_user

router = APIRouter()

@router.post("/upload-csv")
async def upload_csv(request: Request):
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

    current_time = datetime.utcnow()
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

@router.get("/list")
async def list_records(skip: int = 0, limit: int = 50, current_user: str = Depends(get_current_user)):
    data = []
    for doc in collection.find().skip(skip).limit(limit):
        doc["_id"] = str(doc["_id"])
        data.append(doc)
    return data

@router.delete("/record/{record_id}")
async def delete_record(record_id: str, current_user: str = Depends(get_current_user)):
    res = collection.delete_one({"_id": ObjectId(record_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": True}

@router.put("/record/{record_id}")
async def update_record(record_id: str, request: Request, current_user: str = Depends(get_current_user)):
    body = await request.json()
    body.pop("_id", None)
    body["lastModified"] = datetime.utcnow()
    
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

@router.get("/search")
async def search_records(
    query: str = "",
    skip: int = 0,
    limit: int = 50,
    current_user: str = Depends(get_current_user)
):
    try:
        if not query:
            # Return all records if no search parameters
            data = []
            for doc in collection.find().skip(skip).limit(limit):
                doc["_id"] = str(doc["_id"])
                data.append(doc)
            return data

        # Parse query string into MongoDB query
        mongo_query = {}
        
        # Split query into individual conditions
        conditions = [cond.strip() for cond in query.split('AND')]
        
        for condition in conditions:
            # Handle different query operators
            if ':' in condition:
                field, value = condition.split(':', 1)
                field = field.strip()
                value = value.strip()

                # Handle regex queries
                if value.startswith('/') and value.endswith('/'):
                    pattern = value[1:-1]  # Remove slashes
                    mongo_query[field] = {'$regex': pattern, '$options': 'i'}
                
                # Handle numeric comparisons
                elif value.startswith('>'):
                    mongo_query[field] = {'$gt': float(value[1:])}
                elif value.startswith('<'):
                    mongo_query[field] = {'$lt': float(value[1:])}
                elif value.startswith('>='):
                    mongo_query[field] = {'$gte': float(value[2:])}
                elif value.startswith('<='):
                    mongo_query[field] = {'$lte': float(value[2:])}
                
                # Handle array contains
                elif value.startswith('[') and value.endswith(']'):
                    values = [v.strip() for v in value[1:-1].split(',')]
                    mongo_query[field] = {'$in': values}
                
                # Handle boolean values
                elif value.lower() in ['true', 'false']:
                    mongo_query[field] = value.lower() == 'true'
                
                # Default to case-insensitive partial match
                else:
                    mongo_query[field] = {'$regex': value, '$options': 'i'}

        print(f"MongoDB Query: {mongo_query}")  # Debug print

        # Execute query
        data = []
        for doc in collection.find(mongo_query).skip(skip).limit(limit):
            doc["_id"] = str(doc["_id"])
            data.append(doc)
        return data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download-csv")
async def download_csv(params: str = "", current_user: str = Depends(get_current_user)):
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

@router.get("/count")
async def count_records():
    """Return the total number of records in the collection."""
    total = collection.count_documents({})
    return {"total_records": total}
