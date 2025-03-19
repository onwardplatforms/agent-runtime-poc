#!/usr/bin/env python3

import asyncio
import aiohttp
import logging
import os
from pathlib import Path

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("upload_test_document")

# API URLs
RUNTIME_API_URL = "http://localhost:5003"

async def create_test_document():
    """Create a simple test document."""
    test_dir = Path("./test_docs")
    test_dir.mkdir(exist_ok=True)
    
    test_file = test_dir / "test_nda.txt"
    
    # Create a simple NDA document
    content = """
CONFIDENTIALITY AND NON-DISCLOSURE AGREEMENT

This Confidentiality and Non-Disclosure Agreement (the "Agreement") is entered into as of [Date] by and between:

Onward Platforms, Inc., a Delaware corporation with its principal place of business at 123 Tech Way, San Francisco, CA 94105 ("Company")

and

[Recipient Name], an individual/entity with an address at [Recipient Address] ("Recipient").

1. PURPOSE
The purpose of this Agreement is to protect the confidential and proprietary information of the Company which may be disclosed to the Recipient for the purpose of [describe business purpose] (the "Purpose").

2. CONFIDENTIAL INFORMATION
"Confidential Information" means any information disclosed by the Company to the Recipient, either directly or indirectly, in writing, orally or by inspection of tangible objects, that is designated as "Confidential," "Proprietary" or some similar designation, or that should reasonably be understood to be confidential given the nature of the information and the circumstances of disclosure.

3. TERM
This Agreement shall remain in effect for a period of 3 years from the date of execution.

4. GOVERNING LAW
This Agreement shall be governed by and construed in accordance with the laws of the State of California.

IN WITNESS WHEREOF, the parties have executed this Agreement as of the date first written above.

COMPANY: Onward Platforms, Inc.

By: ____________________________
Name: John Smith
Title: CEO

RECIPIENT:

By: ____________________________
Name: [Recipient Name]
Title: [Recipient Title]
"""
    
    with open(test_file, "w") as f:
        f.write(content)
        
    logger.info(f"Created test document: {test_file}")
    return test_file

async def upload_document(file_path):
    """Upload a document to the RAG API."""
    try:
        logger.info(f"Uploading document: {file_path}")
        
        # Create form data with the file
        data = aiohttp.FormData()
        data.add_field('files', 
                      open(file_path, 'rb'),
                      filename=os.path.basename(file_path),
                      content_type='text/plain')
        
        # Upload to the Runtime API
        async with aiohttp.ClientSession() as session:
            url = f"{RUNTIME_API_URL}/api/upload"
            logger.info(f"Sending POST request to: {url}")
            
            async with session.post(url, data=data) as response:
                status = response.status
                logger.info(f"Response status: {status}")
                
                text = await response.text()
                logger.info(f"Response text: {text[:500]}")
                
                if status == 200:
                    logger.info("Document uploaded successfully")
                    return True
                else:
                    logger.error(f"Upload failed with status: {status}")
                    return False
    except Exception as e:
        logger.error(f"Error uploading document: {e}", exc_info=True)
        return False

async def main():
    """Create and upload a test document."""
    logger.info("Starting test document upload...")
    
    # Create test document
    test_file = await create_test_document()
    
    # Upload the document
    success = await upload_document(test_file)
    
    if success:
        logger.info("Test document uploaded successfully")
    else:
        logger.error("Failed to upload test document")
    
    logger.info("Test completed")

if __name__ == "__main__":
    asyncio.run(main()) 