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

logger = logging.getLogger("uvicorn.error")

CHUNK_SIZE = 1000  # Number of records to process at once


class DataIngestionService:
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def process_file(
        self, 
        file: UploadFile,
        current_user: str,
        column_mappings: Dict[int, str] = None,
        included_columns: List[int] = None,
        fixed_fields: Dict[str, str] = None
    ) -> Dict[str, int]:
        """
        Process uploaded file in chunks and insert into MongoDB
        """
        try:
            content_type = file.content_type or file.filename.split('.')[-1]
            logger.info(f"Processing file with content type: {content_type}")
            
            if content_type in ['application/json', 'json']:
                return await self._process_json_file(file, current_user, column_mappings, included_columns, fixed_fields)
            elif content_type in ['text/csv', 'application/vnd.ms-excel', 'csv']:
                return await self._process_csv_file(
                    file, 
                    current_user, 
                    column_mappings, 
                    included_columns, 
                    fixed_fields
                )
            else:
                raise ValueError(f"Unsupported file type: {content_type}")
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}", exc_info=True)
            raise

    async def _process_json_file(
        self, 
        file: UploadFile,
        current_user: str,
        column_mappings: Dict[int, str] = None,
        included_columns: List[int] = None,
        fixed_fields: Dict[str, str] = None
    ) -> Dict[str, int]:
        content = await file.read()
        try:
            data = json.loads(content.decode('utf-8'))
            logger.info(f"JSON data type: {type(data)}")
            
            if isinstance(data, dict):
                rows = data.get("rows", [])
            elif isinstance(data, list):
                rows = data
            else:
                raise ValueError(f"Invalid JSON format. Expected dict or list, got {type(data)}")

            if not rows:
                raise ValueError("No data rows found in JSON")

            # Convert rows to DataFrame for consistent processing
            df = pd.DataFrame(rows)
            
            # Apply column filtering and mapping
            if included_columns is not None:
                if len(included_columns) > len(df.columns):
                    raise ValueError("Invalid included_columns indices")
                df = df.iloc[:, included_columns]
            
            if column_mappings:
                df.columns = [column_mappings.get(i, col) for i, col in enumerate(df.columns)]
            
            # Convert back to records
            filtered_rows = df.to_dict('records')
            
            logger.info(f"Processing {len(filtered_rows)} JSON records")
            return await self._process_records(filtered_rows, current_user, fixed_fields)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")
        except Exception as e:
            logger.error(f"Error processing JSON: {str(e)}", exc_info=True)
            raise

    async def _process_csv_file(
        self, 
        file: UploadFile,
        current_user: str,
        column_mappings: Dict[int, str] = None,
        included_columns: List[int] = None,
        fixed_fields: Dict[str, str] = None
    ) -> Dict[str, int]:
        content = await file.read()
        text = content.decode('utf-8')
        
        try:
            csv_file = io.StringIO(text)
            total_inserted = 0
            total_duplicates = 0

            for chunk in pd.read_csv(csv_file, chunksize=CHUNK_SIZE):
                if chunk.empty:
                    continue
                
                # Apply column mappings and filtering
                if included_columns is not None:
                    chunk = chunk.iloc[:, included_columns]
                
                if column_mappings:
                    chunk.columns = [column_mappings.get(i, col) for i, col in enumerate(chunk.columns)]
                else:
                    # Clean column names: strip whitespace and lowercase
                    chunk.columns = [col.strip().lower() for col in chunk.columns]
                
                records = chunk.to_dict('records')
                cleaned_records = []
                
                for record in records:
                    # Remove any leading/trailing spaces from keys and values
                    cleaned_record = {
                        k.strip(): v.strip() if isinstance(v, str) else v
                        for k, v in record.items()
                    }
                    cleaned_records.append(cleaned_record)
                
                logger.info(f"Processing chunk of {len(cleaned_records)} CSV records")
                result = await self._process_records(cleaned_records, current_user, fixed_fields)
                total_inserted += result['inserted_count']
                total_duplicates += result.get('duplicate_count', 0)

            if total_inserted == 0 and total_duplicates == 0:
                raise ValueError("No valid records found in CSV")

            return {
                "inserted_count": total_inserted,
                "duplicate_count": total_duplicates
            }
        except pd.errors.EmptyDataError:
            raise ValueError("CSV file is empty")
        except Exception as e:
            logger.error(f"Error processing CSV: {str(e)}", exc_info=True)
            raise

    async def _process_records(
        self, 
        records: List[Dict],
        current_user: str,
        fixed_fields: Dict[str, str] = None
    ) -> Dict[str, int]:
        """Process a batch of records"""
        if not records:
            return {"inserted_count": 0, "duplicate_count": 0}

        current_time = datetime.utcnow()
        processed_records = []
        
        for record in records:
            # Clean and validate record
            cleaned_record = self._process_record(record)
            if not cleaned_record:  # Skip empty records
                continue
            
            # Remove any existing timestamp fields
            cleaned_record.pop('createdAt', None)
            cleaned_record.pop('lastModified', None)
            
            # Create the processed record with required fields
            processed_record = {
                **cleaned_record,
                'createdAt': current_time,
                'lastModified': current_time,
                'created_by': current_user,
                'updated_by': current_user
            }
            
            # Add source if not present
            if 'source' not in processed_record:
                processed_record['source'] = 'file_import' + datetime.utcnow().strftime('%Y-%m-%d-%H-%M')
            
            # Add any fixed fields
            if fixed_fields:
                processed_record.update(fixed_fields)
            
            processed_records.append(processed_record)

        if not processed_records:
            return {"inserted_count": 0, "duplicate_count": 0}

        try:
            result = self.collection.insert_many(processed_records)
            return {
                "inserted_count": len(result.inserted_ids),
                "duplicate_count": 0
            }
        except pymongo.errors.BulkWriteError as bwe:
            inserted_count = bwe.details.get('nInserted', 0)
            duplicate_count = sum(1 for err in bwe.details.get('writeErrors', []) 
                                if err.get('code') == 11000)
            return {
                "inserted_count": inserted_count,
                "duplicate_count": duplicate_count
            }
        except Exception as e:
            logger.error(f"Error inserting records: {str(e)}")
            raise

    def _clean_value(self, value):
        """Clean and validate a value before insertion"""
        if pd.isna(value) or pd.isnull(value):
            return None
        if isinstance(value, float):
            # Check for invalid float values
            if not math.isfinite(value):
                return None
        return value

    def _process_record(self, record: dict) -> dict:
        """Process and validate a single record"""
        cleaned_record = {}
        for key, value in record.items():
            cleaned_value = self._clean_value(value)
            if cleaned_value is not None:  # Only include non-None values
                cleaned_record[key] = cleaned_value
        return cleaned_record 