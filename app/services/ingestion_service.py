from typing import BinaryIO, Dict, List, Union
import pandas as pd
import json
from datetime import datetime
import asyncio
from pymongo.collection import Collection
import logging
from fastapi import UploadFile
import io
import pymongo
import math
from app.services.storage_service import StorageService
import numpy as np
import csv

logger = logging.getLogger("uvicorn.error")

CHUNK_SIZE = 1000  # Number of records to process at once


class DataIngestionService:
    def __init__(self, collection: Collection, files_collection: Collection):
        self.collection = collection
        self.files_collection = files_collection

    def process_file(
        self, 
        file: UploadFile,
        current_user: str,
        column_mappings: Dict[int, str] = None,
        included_columns: List[int] = None,
        fixed_fields: Dict[str, str] = None,
        multivalue_separator: str = ","  # New parameter for multivalue separator
    ) -> Dict[str, int]:
        """Process uploaded file and insert into MongoDB"""
        start_time = datetime.utcnow()
        try:
            # Save file first
            storage_service = StorageService(self.files_collection)
            file_metadata = storage_service.save_file(file, current_user)

            content_type = file.content_type or file.filename.split('.')[-1]
            logger.info(f"Processing file with content type: {content_type}")

            # Add file metadata to fixed fields
            if fixed_fields is None:
                fixed_fields = {}
            fixed_fields['file_source'] = file_metadata['stored_filename']

            if content_type in ['application/json', 'json']:
                result = self._process_json_file(file, current_user, column_mappings, included_columns, fixed_fields)
            elif content_type in ['text/csv', 'application/vnd.ms-excel', 'csv']:
                result = self._process_csv_file(
                    file, 
                    current_user, 
                    column_mappings, 
                    included_columns, 
                    fixed_fields,
                    multivalue_separator=multivalue_separator
                )
            else:
                raise ValueError(f"Unsupported file type: {content_type}")

            return result
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}", exc_info=True)
            raise
        finally:
            elapsed_time = datetime.utcnow() - start_time
            logger.info(f"Ingestion completed in {elapsed_time.total_seconds()} seconds")

    def _process_json_file(
        self, 
        file: UploadFile,
        current_user: str,
        column_mappings: Dict[int, str] = None,
        included_columns: List[int] = None,
        fixed_fields: Dict[str, str] = None
    ) -> Dict[str, int]:
        content = file.file.read()
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
            
            # Add this before applying the column mappings
            logger.info(f"Original columns: {df.columns.tolist()}")
            logger.info(f"Column mappings: {column_mappings}")
            
            # Apply column filtering and mapping
            if included_columns is not None:
                if len(included_columns) > len(df.columns):
                    raise ValueError("Invalid included_columns indices")
                df = df.iloc[:, included_columns]
            
            if column_mappings:
                column_mappings = {int(k): v for k, v in column_mappings.items()}
                df.columns = [
                    column_mappings.get(included_columns[i], col)  # Use original index from included_columns
                    for i, col in enumerate(df.columns)
                ]
            
            # After applying mappings
            logger.info(f"New columns: {df.columns.tolist()}")
            
            # Convert DataFrame to records while preserving the new column names
            records = json.loads(df.to_json(orient='records'))
            filtered_rows = [record for record in records if any(record.values())]
            
            logger.info(f"Processing {len(filtered_rows)} JSON records")
            logger.info(f"Sample record after conversion: {records[0] if records else 'No records'}")
            return self._process_records(filtered_rows, current_user, fixed_fields)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")
        except Exception as e:
            logger.error(f"Error processing JSON: {str(e)}", exc_info=True)
            raise

    def _process_csv_file(
        self, 
        file: UploadFile,
        current_user: str,
        column_mappings: Dict[int, str] = None,
        included_columns: List[int] = None,
        fixed_fields: Dict[str, str] = None,
        delimiter: str = ",",
        multivalue_separator: str = ","
    ) -> Dict[str, int]:
        content = file.file.read()
        text = content.decode('utf-8')
        
        try:
            # Use pandas with custom CSV reading configuration
            csv_file = io.StringIO(text)
            
            # First read headers
            try:
                headers = pd.read_csv(
                    csv_file, 
                    nrows=0,
                    sep=delimiter,
                    quoting=csv.QUOTE_MINIMAL,
                    doublequote=True,
                    escapechar='\\'
                ).columns.tolist()
                
                # Reset file pointer for data reading
                csv_file.seek(0)
                
                # Read CSV in chunks with proper handling of quoted fields
                chunks = pd.read_csv(
                    csv_file,
                    chunksize=CHUNK_SIZE,
                    sep=delimiter,
                    quoting=csv.QUOTE_MINIMAL,
                    doublequote=True,
                    escapechar='\\',
                    on_bad_lines='warn'
                )
                
                total_inserted = 0
                total_duplicates = 0
                
                for chunk in chunks:
                    if chunk.empty:
                        continue
                        
                    # Apply column filtering if specified
                    if included_columns is not None:
                        chunk = chunk.iloc[:, included_columns]
                    
                    # Apply column mappings if specified
                    if column_mappings:
                        column_mappings = {int(k): v for k, v in column_mappings.items()}
                        chunk.columns = [
                            column_mappings.get(included_columns[i], col)
                            for i, col in enumerate(chunk.columns)
                        ]
                    
                    # Process potential array fields
                    for column in chunk.columns:
                        # Check if any cell in this column contains the multivalue separator
                        if chunk[column].astype(str).str.contains(f'"{multivalue_separator}"', regex=False).any():
                            # Convert the string values to arrays using the multivalue separator
                            chunk[column] = chunk[column].apply(
                                lambda x: [v.strip() for v in str(x).strip('"').split(multivalue_separator) if v.strip()]
                                if pd.notna(x) else None
                            )
                    
                    # Convert to records while preserving column names
                    records = json.loads(chunk.to_json(orient='records'))
                    records = [record for record in records if any(record.values())]
                    
                    # Process the chunk
                    result = self._process_records(records, current_user, fixed_fields)
                    total_inserted += result.get('inserted_count', 0)
                    total_duplicates += result.get('duplicate_count', 0)

                if total_inserted == 0 and total_duplicates == 0:
                    raise ValueError("No valid records found in CSV")

                return {
                    "inserted_count": total_inserted,
                    "duplicate_count": total_duplicates
                }
                
            except Exception as e:
                logger.warning(f"Error in processing CSV: {str(e)}")
                raise
            
        except Exception as e:
            logger.error(f"Error processing CSV: {str(e)}")
            raise

    def _process_records(
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
                'registered_in': {}
            }
            
            # Add any fixed fields
            if fixed_fields:
                processed_record.update(fixed_fields)
            
            processed_records.append(processed_record)

        if not processed_records:
            return {"inserted_count": 0, "duplicate_count": 0}

        try:
            result = self.collection.insert_many(processed_records, ordered=False)
            return {"inserted_count": len(result.inserted_ids)}
        except pymongo.errors.BulkWriteError as bwe:
            # Handle partial success case
            return {
                "inserted_count": bwe.details.get('nInserted', 0),
                "duplicate_count": len([err for err in bwe.details.get('writeErrors', []) 
                                     if err.get('code') == 11000])
            }
        except Exception as e:
            logger.error(f"Error inserting records: {str(e)}")
            raise

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