import logging
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pathlib import Path

from .config import settings
from .api.routes import router as rag_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ragapi")

# Create directories if they don't exist
os.makedirs(settings.documents_path, exist_ok=True)
os.makedirs(settings.embeddings_path, exist_ok=True)
logger.info(f"Ensured documents directory exists: {settings.documents_path}")
logger.info(f"Ensured embeddings directory exists: {settings.embeddings_path}")

# Create FastAPI app
app = FastAPI(
    title="RAG API",
    description="API for Retrieval-Augmented Generation",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development - restrict this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(rag_router)


@app.get("/")
async def root():
    return {"message": "Welcome to the RAG API", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Check if document and embedding directories exist
    if not os.path.exists(settings.documents_path):
        raise HTTPException(status_code=500, detail="Documents directory not found")
    if not os.path.exists(settings.embeddings_path):
        raise HTTPException(status_code=500, detail="Embeddings directory not found")
    
    return {
        "status": "healthy",
        "documents_path": settings.documents_path,
        "embeddings_path": settings.embeddings_path,
    }


if __name__ == "__main__":
    # Run the application
    uvicorn.run(
        "ragapi.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
