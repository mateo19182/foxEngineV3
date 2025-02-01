from fastapi import APIRouter, Request, HTTPException, Depends, Path, Query
from datetime import datetime
import pymongo
from bson.objectid import ObjectId
import pandas as pd
import io
from fastapi.responses import StreamingResponse
from ..database.client import collection
from ..auth.jwt import get_current_user
from ..utils.logging import logs_collection, log_api_call
from typing import Optional, List
import logging

router = APIRouter()

# Set up logging
logger = logging.getLogger("uvicorn.error")

@router.post("/upload-csv", summary="Upload CSV data", 
    description="Upload CSV data with required 'source' and 'username' columns")
async def upload_csv(request: Request, current_user: str = Depends(get_current_user)):
    try:
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
                    # Strip whitespace from string values
                    value = r[i]
                    if isinstance(value, str):
                        value = value.strip()
                    rec[col] = value
            
            # Add required fields
            rec["createdAt"] = current_time
            rec["lastModified"] = current_time
            records.append(rec)

        try:
            res = collection.insert_many(records, ordered=False)
            inserted_count = len(res.inserted_ids)
            log_api_call("/upload-csv", "POST", current_user, 
                        additional_info=f"Records inserted: {inserted_count}")
            return {"inserted_count": inserted_count}
        except pymongo.errors.BulkWriteError as bwe:
            # Handle partial success case
            inserted_count = bwe.details.get('nInserted', 0)
            duplicates = len([err for err in bwe.details.get('writeErrors', []) 
                            if err.get('code') == 11000])
            log_api_call("/upload-csv", "POST", current_user, 
                        status_code=207, 
                        error="Partial success",
                        additional_info=f"Records inserted: {inserted_count}, Duplicates: {duplicates}")
            return {
                "inserted_count": inserted_count,
                "duplicate_count": duplicates,
                "message": "Some records were duplicates and were skipped"
            }
    except Exception as e:
        log_api_call("/upload-csv", "POST", current_user, 500, str(e))
        raise

@router.get("/list", summary="List records", 
    description="Get paginated list of records")
async def list_records(
    skip: int = Query(0, description="Number of records to skip"),
    limit: int = Query(50, description="Number of records to return"),
    current_user: str = Depends(get_current_user)
):
    try:
        data = []
        for doc in collection.find().skip(skip).limit(limit):
            doc["_id"] = str(doc["_id"])
            data.append(doc)
        log_api_call("/list", "GET", current_user)
        return data
    except Exception as e:
        log_api_call("/list", "GET", current_user, 500, str(e))
        raise

@router.delete("/record/{record_id}", summary="Delete record",
    description="Delete a record by ID")
async def delete_record(
    record_id: str = Path(..., description="The ID of the record to delete"),
    current_user: str = Depends(get_current_user)
):
    try:
        res = collection.delete_one({"_id": ObjectId(record_id)})
        if res.deleted_count == 0:
            log_api_call(f"/record/{record_id}", "DELETE", current_user, 404)
            raise HTTPException(status_code=404, detail="Not found")
        log_api_call(f"/record/{record_id}", "DELETE", current_user)
        return {"deleted": True}
    except Exception as e:
        log_api_call(f"/record/{record_id}", "DELETE", current_user, 500, str(e))
        raise

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
    skip: int = Query(0, description="Number of records to skip"),
    limit: int = Query(50, description="Number of records to return"),
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

        logger.info(f"MongoDB Query: {mongo_query}")  # Use logger instead of print

        # Execute query with pagination
        data = []
        for doc in collection.find(mongo_query).skip(skip).limit(limit):
            doc["_id"] = str(doc["_id"])
            data.append(doc)
        return data

    except Exception as e:
        logger.error(f"Error in search_records: {str(e)}")  # Log the error
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

@router.get("/logs")
async def get_logs(
    limit: int = 100,
    status_code: Optional[int] = None,
    current_user: str = Depends(get_current_user)
):
    """Get recent API logs."""
    query = {}
    if status_code:
        query["status_code"] = status_code
    
    logs = []
    for log in logs_collection.find(query).sort("timestamp", -1).limit(limit):
        log["_id"] = str(log["_id"])
        log["timestamp"] = log["timestamp"].isoformat()
        logs.append(log)
    return logs
