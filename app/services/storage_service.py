import os
import shutil
from datetime import datetime
from fastapi import UploadFile
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorCollection
import hashlib
import aiofiles

class StorageService:
    def __init__(self, files_collection: AsyncIOMotorCollection):
        self.upload_dir = "/app/uploads"
        self.files_collection = files_collection
        self._ensure_upload_dir()

    def _ensure_upload_dir(self):
        """Ensure upload directory exists"""
        os.makedirs(self.upload_dir, exist_ok=True)

    async def save_file(self, file: UploadFile, user: str) -> dict:
        """Save uploaded file and record metadata"""
        try:
            # Generate unique filename using timestamp and original filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            original_filename = file.filename
            extension = os.path.splitext(original_filename)[1]
            new_filename = f"{timestamp}_{original_filename}"
            file_path = os.path.join(self.upload_dir, new_filename)

            # Calculate file hash and save file
            contents = await file.read()
            file_hash = hashlib.sha256(contents).hexdigest()
            
            # Save file using aiofiles
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(contents)

            # Reset file position for further processing
            await file.seek(0)

            # Record metadata in MongoDB
            metadata = {
                "original_filename": original_filename,
                "stored_filename": new_filename,
                "file_path": file_path,
                "file_hash": file_hash,
                "content_type": file.content_type,
                "size": os.path.getsize(file_path),
                "uploaded_by": user,
                "uploaded_at": datetime.utcnow(),
                "extension": extension
            }

            # Use Motor's async insert_one
            result = await self.files_collection.insert_one(metadata)
            metadata['_id'] = str(result.inserted_id)
            return metadata

        except Exception as e:
            # Clean up file if saved but metadata recording failed
            if 'file_path' in locals() and os.path.exists(file_path):
                os.remove(file_path)
            raise e 