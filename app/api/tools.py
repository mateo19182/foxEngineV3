from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
from ..tools.header_extractor import HeaderExtractor
from ..auth.jwt import get_current_user
from ..utils.logging import log_api_call
import logging

router = APIRouter()
logger = logging.getLogger("uvicorn.error")

# Initialize tools
header_extractor = HeaderExtractor()

@router.post("/extract-headers")
async def extract_headers(
    request: Request,
    file: UploadFile = File(...)
):
    """
    Extract headers from a CSV file without headers.
    """
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    try:
        # Log API call
        await log_api_call("/api/tools/extract-headers", "POST", user["username"])
        
        # Validate file type
        if not file.filename.lower().endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files are supported")
            
        # Process the file with the header extractor
        result = await header_extractor.extract_headers(file)
        
        return JSONResponse(content=result)
        
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error in extract_headers: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
