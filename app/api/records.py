from fastapi import APIRouter, Request, HTTPException, Depends, Path, Query, UploadFile, File, Form
from datetime import datetime
import pymongo
from bson.objectid import ObjectId
import pandas as pd
import io
from fastapi.responses import StreamingResponse
from ..database.client import collection, files_collection
from ..auth.jwt import get_current_user
from ..utils.logging import logs_collection, log_api_call
from typing import Optional, List
import logging
from ..services.ingestion_service import DataIngestionService
import json
from bson import ObjectId

router = APIRouter()

# Set up logging
logger = logging.getLogger("uvicorn.error")

@router.post("/upload-data", summary="Upload CSV or JSON data", 
    description="Upload data in CSV or JSON format with required 'source' and 'username' fields")
async def upload_data(request: Request, current_user: str = Depends(get_current_user)):
    try:
        content_type = request.headers.get('Content-Type')
        if content_type == 'application/json':
            data = await request.json()
            rows = data.get("rows", [])
            columns = data.get("columns", [])
        elif content_type == 'text/csv':
            body = await request.body()
            # Assuming CSV data is sent as a string
            data = io.StringIO(body.decode('utf-8'))
            df = pd.read_csv(data)
            rows = df.values.tolist()
            columns = df.columns.tolist()
        else:
            raise HTTPException(status_code=400, detail="Unsupported media type. Use application/json or text/csv.")

        if not rows or not columns:
            raise HTTPException(status_code=400, detail="No data provided")

        # Verify required fields are present
        if "source" not in columns or "username" not in columns:
            raise HTTPException(
                status_code=400, 
                detail="Data must contain 'source' and 'username' fields"
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
            res = await collection.insert_many(records, ordered=False)
            inserted_count = len(res.inserted_ids)
            await log_api_call("/upload-data", "POST", current_user, 
                        additional_info=f"Records inserted: {inserted_count}")
            return {"inserted_count": inserted_count}
        except pymongo.errors.BulkWriteError as bwe:
            # Handle partial success case
            inserted_count = bwe.details.get('nInserted', 0)
            duplicates = len([err for err in bwe.details.get('writeErrors', []) 
                            if err.get('code') == 11000])
            await log_api_call("/upload-data", "POST", current_user, 
                        status_code=207, 
                        error="Partial success",
                        additional_info=f"Records inserted: {inserted_count}, Duplicates: {duplicates}")
            return {
                "inserted_count": inserted_count,
                "duplicate_count": duplicates,
                "message": "Some records were duplicates and were skipped"
            }
    except Exception as e:
        await log_api_call("/upload-data", "POST", current_user, 500, str(e))
        raise

@router.get("/list", summary="List records", 
    description="Get paginated list of records")
async def list_records(
    skip: int = Query(0, description="Number of records to skip"),
    limit: int = Query(50, description="Number of records to return"),
    current_user: str = Depends(get_current_user)
):
    try:
        cursor = collection.find().skip(skip).limit(limit)
        data = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            data.append(doc)
        await log_api_call("/list", "GET", current_user)
        return data
    except Exception as e:
        await log_api_call("/list", "GET", current_user, 500, str(e))
        raise

@router.delete("/record/{record_id}", summary="Delete record",
    description="Delete a record by ID")
async def delete_record(
    record_id: str = Path(..., description="The ID of the record to delete"),
    current_user: str = Depends(get_current_user)
):
    try:
        res = await collection.delete_one({"_id": ObjectId(record_id)})
        if res.deleted_count == 0:
            await log_api_call(f"/record/{record_id}", "DELETE", current_user, 404)
            raise HTTPException(status_code=404, detail="Not found")
        await log_api_call(f"/record/{record_id}", "DELETE", current_user)
        return {"deleted": True}
    except Exception as e:
        await log_api_call(f"/record/{record_id}", "DELETE", current_user, 500, str(e))
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
    
    res = await collection.update_one(
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
        # Build the query
        if not query:
            mongo_query = {}
        else:
            mongo_query = {}
            conditions = [cond.strip() for cond in query.split('AND')]
            
            for condition in conditions:
                if ':' in condition:
                    field, value = condition.split(':', 1)
                    field = field.strip()
                    value = value.strip()

                    # Handle _id field specially
                    if field == '_id':
                        try:
                            mongo_query[field] = ObjectId(value)
                            continue
                        except:
                            # If invalid ObjectId, return no results
                            mongo_query[field] = None
                            continue

                    # Handle regex queries
                    if value.startswith('/') and value.endswith('/'):
                        pattern = value[1:-1]
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

        # Get total count for the query
        total_count = await collection.count_documents(mongo_query)

        # If limit is 0, return only the total count
        if limit == 0:
            return {
                "total": total_count,
                "records": []
            }

        # Get paginated results with consistent sorting
        cursor = collection.find(mongo_query).sort("createdAt", -1).skip(skip).limit(limit)
        data = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            data.append(doc)

        return {
            "total": total_count,
            "records": data
        }

    except Exception as e:
        logger.error(f"Error in search_records: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download-csv")
async def download_csv(
    query: str = "",
    fields: str = "",
    limit: int = 0,
    current_user: str = Depends(get_current_user)
):
    try:
        # Parse the query string into MongoDB query
        if not query:
            mongo_query = {}
        else:
            mongo_query = {}
            conditions = [cond.strip() for cond in query.split('AND')]
            
            for condition in conditions:
                if ':' in condition:
                    field, value = condition.split(':', 1)
                    field = field.strip()
                    value = value.strip()

                    # Handle _id field specially
                    if field == '_id':
                        try:
                            mongo_query[field] = ObjectId(value)
                            continue
                        except:
                            # If invalid ObjectId, return no results
                            mongo_query[field] = None
                            continue

                    # Handle regex queries
                    if value.startswith('/') and value.endswith('/'):
                        pattern = value[1:-1]
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

        # Parse fields to export
        field_list = [f.strip() for f in fields.split(',')] if fields else []
        projection = {field: 1 for field in field_list} if field_list else None
        
        # Add _id field to projection if not explicitly included
        if projection:
            projection['_id'] = 1

        # Query MongoDB with limit and consistent sorting
        cursor = collection.find(mongo_query, projection).sort("createdAt", -1)
        if limit > 0:
            cursor = cursor.limit(limit)
            
        # Convert cursor to list
        rows = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            rows.append(doc)
            
        df = pd.DataFrame(rows)
        
        if not df.empty:
            # Only include requested fields in the order specified
            if field_list:
                # Ensure all requested fields exist (some might be missing in the data)
                existing_fields = [f for f in field_list if f in df.columns]
                df = df[existing_fields]

        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)

        # Generate filename with current datetime
        current_time = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"records_{current_time}.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Error in download_csv: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/count")
async def count_records():
    """Return the total number of records in the collection."""
    total = await collection.count_documents({})
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
    
    cursor = logs_collection.find(query).sort("timestamp", -1).limit(limit)
    logs = []
    async for log in cursor:
        log["_id"] = str(log["_id"])
        log["timestamp"] = log["timestamp"].isoformat()
        logs.append(log)
    return logs

@router.post("/upload-file", summary="Upload data file")
async def upload_file(
    file: UploadFile = File(...),
    delimiter: str = Form(","),
    column_mappings: str = Form(None),
    included_columns: str = Form(None),
    fixed_fields: str = Form(None),
    current_user: str = Depends(get_current_user)
):
    try:
        # Parse the JSON strings into Python objects
        column_mappings_dict = json.loads(column_mappings) if column_mappings else None
        included_columns_list = json.loads(included_columns) if included_columns else None
        fixed_fields_dict = json.loads(fixed_fields) if fixed_fields else None

        # Validate included_columns format
        if included_columns_list is not None:
            if not isinstance(included_columns_list, list) or not all(isinstance(x, int) for x in included_columns_list):
                raise HTTPException(status_code=400, detail="included_columns must be a list of integers")

        # Read the first line to get total number of columns
        content = await file.read()
        await file.seek(0)  # Reset file pointer
        
        total_columns = 0
        if file.content_type in ['text/csv', 'application/vnd.ms-excel', 'csv']:
            first_line = content.decode('utf-8').split('\n')[0]
            total_columns = len(first_line.split(','))
        elif file.content_type in ['application/json', 'json']:
            data = json.loads(content.decode('utf-8'))
            if isinstance(data, dict) and 'rows' in data:
                total_columns = len(data['rows'][0]) if data['rows'] else 0
            elif isinstance(data, list):
                total_columns = len(data[0]) if data else 0
        
        await file.seek(0)  # Reset file pointer again

        ingestion_service = DataIngestionService(collection, files_collection)
        result = await ingestion_service.process_file(
            file, 
            current_user,
            column_mappings_dict,
            included_columns_list,
            fixed_fields_dict
        )
        
        # Calculate dropped columns
        included_count = len(included_columns_list) if included_columns_list is not None else total_columns
        dropped_columns = total_columns - included_count if total_columns > 0 else 0
        
        log_message = (
            f"Records inserted: {result['inserted_count']}, "
            f"Total columns: {total_columns}, "
            f"Columns included: {included_count}, "
            f"Columns dropped: {dropped_columns}"
        )
        
        if 'duplicate_count' in result:
            log_message += f", Duplicates: {result['duplicate_count']}"
            
        if 'updated_count' in result:
            log_message += f", Updated: {result['updated_count']}"
            
        if 'error_message' in result:
            log_message += f", Error: {result['error_message']}"
            
        if 'validation_errors' in result:
            log_message += f", Validation errors: {'; '.join(result['validation_errors'])}"
        
        status_code = 200 if result.get('inserted_count', 0) > 0 or result.get('updated_count', 0) > 0 else 400
        
        await log_api_call(
            "/upload-file", 
            "POST", 
            current_user,
            status_code=status_code,
            error=result.get('error_message'),
            additional_info=log_message
        )
        
        # Add column statistics to result
        result.update({
            "total_columns": total_columns,
            "included_columns": included_count,
            "dropped_columns": dropped_columns
        })
        
        if status_code != 200:
            raise HTTPException(status_code=status_code, detail=result)
            
        return result
    except Exception as e:
        await log_api_call("/upload-file", "POST", current_user, 500, str(e))
        raise HTTPException(status_code=500, detail=str(e))

