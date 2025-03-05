from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from pydantic import BaseModel, Field
import logging
from app.database.client import get_database

router = APIRouter()
logger = logging.getLogger("uvicorn.error")

class RegistrationUpdateRequest(BaseModel):
    search_query: Dict[str, Any] = Field(..., description="MongoDB query to find records to update")
    service: str = Field(..., description="Service name to update (e.g., 'facebook', 'twitter')")
    value: bool = Field(..., description="Registration status to set (true/false)")

def _convert_to_flexible_search(query: Dict[str, Any]) -> Dict[str, Any]:
    """Convert simple text searches into case-insensitive regex patterns"""
    converted_query = {}
    for key, value in query.items():
        if isinstance(value, str):
            # Convert simple string matches to case-insensitive regex
            converted_query[key] = {"$regex": value, "$options": "i"}
        else:
            converted_query[key] = value
    return converted_query

@router.post("/bulk-update-registration")
async def update_registration_status(
    request: RegistrationUpdateRequest
) -> Dict[str, int]:
    """
    Update registration status for all records matching the search query.
    
    Example request:
    {
        "search_query": {"email": "alex@gmail.com"},
        "service": "facebook",
        "value": true
    }
    """
    try:
        # Validate service name (optional: add allowed services list)
        if not request.service.strip():
            raise HTTPException(status_code=400, detail="Service name cannot be empty")
            
        # Get database collection
        db = get_database()
        collection = db.records
            
        # Convert the search query to be more flexible
        flexible_query = _convert_to_flexible_search(request.search_query)
        logger.info(f"Original query: {request.search_query}")
        logger.info(f"Converted query: {flexible_query}")
            
        # Construct the update query
        update_field = f"registered_in.{request.service}"
        update_query = {"$set": {update_field: request.value}}
        
        # Perform the update
        result = collection.update_many(
            filter=flexible_query,
            update=update_query
        )
        
        return {
            "matched_count": result.matched_count,
            "modified_count": result.modified_count
        }
        
    except Exception as e:
        logger.error(f"Error updating registration status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 