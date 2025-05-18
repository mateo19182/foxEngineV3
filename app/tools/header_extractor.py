import logging
import csv
import io
import json
import re
import random
import requests
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple
from fastapi import UploadFile, HTTPException

logger = logging.getLogger("uvicorn.error")

class HeaderExtractor:
    """
    Tool for extracting headers from CSV files that don't have headers.
    Uses an LLM to analyze the content and suggest appropriate headers.
    """
    
    def __init__(self):
        # Initialize any required components here
        self.api_key = "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"
        self.model = "google/gemini-2.0-flash-001"
    
    def is_numeric(self, value: str) -> bool:
        """Check if a string value is numeric."""
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False

    async def extract_headers_from_csv(self, sample_rows: List[List[str]]):
        """
        Extract headers from CSV data without headers.
        
        Args:
            sample_rows (List[List[str]]): Sample rows from the CSV data
            
        Returns:
            dict: A dictionary containing the extracted headers and any additional information
        """
        try:
            # Log the received data for debugging
            logger.info(f"Received sample rows: {sample_rows[:2]}")
            
            if not sample_rows:
                logger.error("Empty CSV data provided")
                raise HTTPException(status_code=400, detail="The CSV data appears to be empty")
            
            # Ensure all rows are properly formatted as lists of strings
            cleaned_rows = []
            for row in sample_rows:
                # If row is already a list, use it directly
                if isinstance(row, list):
                    cleaned_rows.append(row)
                # If row is a dict (which can happen with JSON deserialization), convert to list
                elif isinstance(row, dict):
                    # Convert dict to list by taking values in order of numeric keys
                    try:
                        # Try to convert keys to integers and sort
                        int_keys = sorted([int(k) for k in row.keys()])
                        cleaned_row = [row[str(k)] for k in int_keys]
                        cleaned_rows.append(cleaned_row)
                    except (ValueError, KeyError):
                        # If keys can't be converted to integers, just take values
                        cleaned_rows.append(list(row.values()))
            
            # Update sample_rows with cleaned data
            sample_rows = cleaned_rows
            logger.info(f"Cleaned sample rows: {sample_rows[:2]}")
            
            # Skip header detection and assume all CSV files don't have headers
            logger.info("Assuming CSV data doesn't have headers")
            
            # Get the number of columns
            num_columns = len(sample_rows[0])
            
            # Generate headers using OpenRouter
            logger.info(f"Generating headers for CSV with {num_columns} columns")
            headers = self.generate_headers_with_openrouter(sample_rows, num_columns)
            
            return {
                "headers": headers,
                "sample_data": sample_rows[:3],  # Return first 3 rows as sample data
                "has_headers": False
            }
            
        except Exception as e:
            logger.error(f"Error extracting headers: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to process the data: {str(e)}")
    
    async def extract_headers(self, file: UploadFile = None, csv_data: List[List[str]] = None):
        """
        Extract headers from a CSV file or direct CSV data without headers.
        
        Args:
            file (UploadFile, optional): The uploaded CSV file
            csv_data (List[List[str]], optional): Direct CSV data as a list of rows
            
        Returns:
            dict: A dictionary containing the extracted headers and any additional information
        """
        try:
            # If direct CSV data is provided, use it
            if csv_data is not None:
                logger.info("Processing direct CSV data")
                return await self.extract_headers_from_csv(csv_data)
            
            # Otherwise process the uploaded file
            if file is None:
                raise HTTPException(status_code=400, detail="No CSV file or data provided")
                
            # Read the file content
            content = await file.read()
            file.file.seek(0)  # Reset file pointer for future reads
            
            # Parse CSV content
            text_content = content.decode('utf-8')
            csv_reader = csv.reader(io.StringIO(text_content))
            
            # Get sample rows for analysis
            sample_rows = []
            for i, row in enumerate(csv_reader):
                if i >= 10:  # Get up to 10 rows for analysis
                    break
                sample_rows.append(row)
                
            # Process the sample rows
            return await self.extract_headers_from_csv(sample_rows)
            
        except UnicodeDecodeError:
            logger.error("Unicode decode error when processing CSV file")
            raise HTTPException(status_code=400, detail="The file is not a valid CSV or has an unsupported encoding")
        except Exception as e:
            logger.error(f"Error extracting headers: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to process the file: {str(e)}")
            
    def has_headers(self, sample_rows: List[List[str]]) -> bool:
        """Check if the CSV data already appears to have headers."""
        if len(sample_rows) < 2:
            return False
            
        first_row = sample_rows[0]
        second_row = sample_rows[1]
        
        # Heuristic 1: Headers are often strings while data rows have mixed types
        first_row_types = [self.is_numeric(cell) for cell in first_row]
        second_row_types = [self.is_numeric(cell) for cell in second_row]
        
        # If first row has less numeric values than second row, it might be headers
        if sum(first_row_types) < sum(second_row_types):
            return True
        
        # Heuristic 2: Headers typically don't have empty values
        if first_row.count('') < second_row.count(''):
            return True
        
        # Heuristic 3: Headers are typically shorter than data
        avg_first_len = sum(len(str(cell)) for cell in first_row) / len(first_row)
        avg_second_len = sum(len(str(cell)) for cell in second_row) / len(second_row)
        if avg_first_len < avg_second_len:
            return True
        
        return False
    
    def generate_headers_with_openrouter(self, sample_data: List[List[str]], num_columns: int) -> List[str]:
        """Use OpenRouter API to generate headers based on sample data."""
        # Format the sample data as a readable string
        data_str = "\n".join([','.join(row) for row in sample_data])
        
        # Prepare the prompt for the API
        prompt = f"""Below is sample data from a CSV file without headers. Based on this data, generate appropriate column headers.
        The CSV has {num_columns} columns. Please respond with ONLY a JSON array of {num_columns} header names, nothing else.
        
        Sample data:
        {data_str}
        
        JSON array of header names:
        """
        
        # Make the API request
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a data analysis assistant that helps identify appropriate CSV headers from the data."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 150
        }
        
        try:
            logger.info("Sending request to OpenRouter API")
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            
            # Extract the generated headers from the response
            result = response.json()
            content = result['choices'][0]['message']['content']
            logger.info(f"Received response from OpenRouter API: {content[:100]}...")
            
            # Try to parse the JSON array from the response
            try:
                # First, try to find JSON array in the response if it's not a clean JSON
                json_match = re.search(r'\[.*\]', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
                
                headers = json.loads(content)
                
                # Ensure we have the right number of headers
                if len(headers) != num_columns:
                    logger.warning(f"Generated {len(headers)} headers but expected {num_columns}")
                    # Pad or truncate as needed
                    if len(headers) < num_columns:
                        headers.extend([f"Column_{i+1}" for i in range(len(headers), num_columns)])
                    else:
                        headers = headers[:num_columns]
                
                return headers
            except json.JSONDecodeError:
                logger.error(f"Error parsing API response as JSON: {content}")
                # Fallback to generic headers
                return [f"Column_{i+1}" for i in range(num_columns)]
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API request error: {str(e)}")
            # Fallback to generic headers
            return [f"Column_{i+1}" for i in range(num_columns)]