from typing import BinaryIO, Dict, List, Union
import pandas as pd
import json
from datetime import datetime
import asyncio
from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorClient
import logging
from fastapi import UploadFile
import io
import pymongo
import math
from app.services.storage_service import StorageService
import numpy as np
import csv

logger = logging.getLogger("uvicorn.error")

BATCH_SIZE = 1000  # Number of records to process in each batch


class DataIngestionService:
    def __init__(self, collection: AsyncIOMotorCollection, files_collection: AsyncIOMotorCollection):
        self.collection = collection
        self.files_collection = files_collection
        
    async def ensure_indexes(self):
        """Ensure required indexes exist"""
        await self.collection.create_index("email", unique=True)

    async def process_file(
        self, 
        file: UploadFile,
        current_user: str,
        column_mappings: Dict[int, str] = None,
        included_columns: List[int] = None,
        fixed_fields: Dict[str, str] = None
    ) -> Dict[str, int]:
        """Process uploaded file and insert into MongoDB with email as unique key"""
        start_time = datetime.utcnow()
        try:
            # Ensure indexes
            await self.ensure_indexes()
            
            # Save file metadata
            storage_service = StorageService(self.files_collection)
            file_metadata = await storage_service.save_file(file, current_user)
            
            if fixed_fields is None:
                fixed_fields = {}
            fixed_fields['file_source'] = file_metadata['stored_filename']

            # Process based on file type
            file_ext = file.filename.split('.')[-1].lower()
            if file_ext == 'json':
                result = await self._process_json_file(file, current_user, column_mappings, included_columns, fixed_fields)
            elif file_ext == 'csv':
                result = await self._process_csv_file(file, current_user, column_mappings, included_columns, fixed_fields)
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")

            return result

        except Exception as e:
            logger.error(f"Error processing file: {str(e)}", exc_info=True)
            raise
        finally:
            logger.info(f"Ingestion completed in {(datetime.utcnow() - start_time).total_seconds()} seconds")

    async def _process_json_file(self, file: UploadFile, current_user: str, column_mappings: Dict[int, str],
                          included_columns: List[int], fixed_fields: Dict[str, str]) -> Dict[str, int]:
        """Process JSON file and insert records"""
        content = json.loads(await file.read())
        data = content if isinstance(content, list) else content.get("rows", [])
        
        if not data:
            raise ValueError("No data found in JSON file")
            
        df = pd.DataFrame(data)
        return await self._process_dataframe(df, current_user, column_mappings, included_columns, fixed_fields)

    async def _process_csv_file(self, file: UploadFile, current_user: str, column_mappings: Dict[int, str],
                         included_columns: List[int], fixed_fields: Dict[str, str]) -> Dict[str, int]:
        """Process CSV file and insert records"""
        content = await file.read()
        total_inserted = total_updated = 0
        
        for chunk in pd.read_csv(
            io.StringIO(content.decode('utf-8')),
            chunksize=BATCH_SIZE,
            quoting=1,  # QUOTE_ALL
            escapechar='\\'
        ):
            result = await self._process_dataframe(chunk, current_user, column_mappings, included_columns, fixed_fields)
            total_inserted += result['inserted_count']
            total_updated += result['updated_count']
            
        return {
            "inserted_count": total_inserted,
            "updated_count": total_updated
        }

    async def _process_dataframe(self, df: pd.DataFrame, current_user: str, column_mappings: Dict[int, str],
                          included_columns: List[int], fixed_fields: Dict[str, str]) -> Dict[str, int]:
        """Process DataFrame and insert records"""
        # Apply column filtering and mapping
        if included_columns is not None:
            df = df.iloc[:, included_columns]
        
        if column_mappings:
            df.columns = [column_mappings.get(i, col) for i, col in enumerate(df.columns)]

        # Handle multivalue fields (comma-separated strings)
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].apply(lambda x: 
                    [v.strip() for v in str(x).split(',') if v.strip()] if pd.notna(x) and ',' in str(x)
                    else ([x.strip()] if pd.notna(x) and x.strip() else None)  # Convert single values to lists
                )

        # Convert to records and process
        records = df.replace({pd.NA: None}).to_dict('records')
        return await self._insert_records(records, current_user, fixed_fields)

    async def _insert_records(self, records: List[Dict], current_user: str, fixed_fields: Dict[str, str]) -> Dict[str, int]:
        """Insert records using bulk operations with Motor"""
        if not records:
            return {"inserted_count": 0, "updated_count": 0}

        current_time = datetime.utcnow()
        
        # Prepare all records for bulk operation
        bulk_ops = []
        for record in records:
            if not record.get('email'):
                continue

            # Clean record and add metadata
            cleaned_record = {k: v for k, v in record.items() if v is not None}
            cleaned_record.update({
                'lastModified': current_time,
                'created_by': current_user,
                **(fixed_fields or {})
            })

            # Use updateOne with upsert=True
            bulk_ops.append(
                pymongo.UpdateOne(
                    {'email': record['email']},
                    {
                        '$set': cleaned_record,
                        '$setOnInsert': {'createdAt': current_time}
                    },
                    upsert=True
                )
            )

        # Execute single bulk write operation
        if bulk_ops:
            try:
                result = await self.collection.bulk_write(bulk_ops, ordered=False)
                return {
                    "inserted_count": result.upserted_count,
                    "updated_count": result.modified_count
                }
            except Exception as e:
                logger.error(f"Error in bulk write: {str(e)}")
                raise

        return {"inserted_count": 0, "updated_count": 0}

    def _clean_value(self, value):
        """Clean and validate a value before insertion"""
        # Handle arrays/lists
        if isinstance(value, (list, np.ndarray)):
            return [self._clean_value(item) for item in value if item is not None]
        
        # Handle scalar values
        if pd.isna(value) or pd.isnull(value):
            return None
        if isinstance(value, float):
            # Check for invalid float values
            if not math.isfinite(value):
                return None
        if isinstance(value, str):
            value = value.strip()
            if not value:  # Empty string
                return None
        return value

    def _process_record(self, record: dict) -> dict:
        """Process and validate a single record"""
        cleaned_record = {}
        for key, value in record.items():
            cleaned_value = self._clean_value(value)
            if cleaned_value is not None:  # Only include non-None values
                if isinstance(cleaned_value, list) and not cleaned_value:  # Skip empty lists
                    continue
                cleaned_record[key] = cleaned_value
        return cleaned_record