from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from ..auth.jwt import get_current_user
from ..database.client import files_collection
from bson import ObjectId
import os

router = APIRouter()

@router.get("/list")
async def get_files(
    current_user: str = Depends(get_current_user),
    skip: int = 0,
    limit: int = 10
):
    """Get metadata for uploaded files"""
    cursor = files_collection.find().skip(skip).limit(limit)
    files = []
    for file in cursor:
        file['_id'] = str(file['_id'])
        file['uploaded_at'] = file['uploaded_at'].isoformat()
        files.append(file)
    return files

@router.get("/{file_id}/download")
async def download_file(file_id: str, current_user: str = Depends(get_current_user)):
    """Download a file by its ID"""
    file_doc = files_collection.find_one({"_id": ObjectId(file_id)})
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path = file_doc["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    return FileResponse(
        file_path,
        filename=file_doc["original_filename"],
        media_type=file_doc["content_type"]
    )

@router.delete("/{file_id}")
async def delete_file(file_id: str, current_user: str = Depends(get_current_user)):
    """Delete a file by its ID"""
    file_doc = files_collection.find_one({"_id": ObjectId(file_id)})
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete from filesystem
    try:
        if os.path.exists(file_doc["file_path"]):
            os.remove(file_doc["file_path"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")
    
    # Delete from database
    files_collection.delete_one({"_id": ObjectId(file_id)})
    
    return {"status": "success"}