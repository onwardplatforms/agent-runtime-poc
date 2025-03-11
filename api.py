#!/usr/bin/env python3

import sys
import os
import uvicorn

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("Starting Agent Runtime API on 0.0.0.0:5003")
    uvicorn.run("api.runtime_api:app", host="0.0.0.0", port=5003, log_level="error") 