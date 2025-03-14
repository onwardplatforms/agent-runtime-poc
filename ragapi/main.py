import logging
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pathlib import Path
import datetime

from ragapi.config import settings
from ragapi.api.routes import router as rag_router

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
    try:
        # Check if document and embedding directories exist
        if not os.path.exists(settings.documents_path):
            raise HTTPException(status_code=500, detail="Documents directory not found")
        if not os.path.exists(settings.embeddings_path):
            raise HTTPException(status_code=500, detail="Embeddings directory not found")
        
        # Check storage health if available
        storage_health = {"status": "unknown"}
        try:
            from ragapi.api.dependencies import get_storage
            storage = await get_storage()
            storage_health = await storage.health_check()
        except Exception as e:
            logger.warning(f"Could not check storage health: {str(e)}")
            storage_health = {
                "status": "error",
                "message": f"Failed to check storage: {str(e)}"
            }
            
        # Check embedding model if available
        embedding_health = {"status": "unknown"}
        try:
            from ragapi.api.dependencies import get_embedding_model_instance
            embedding_model = await get_embedding_model_instance()
            embedding_health = {
                "status": "healthy",
                "model": settings.embedding_model if settings.embedding_provider == "local" else settings.openai_embedding_model,
                "provider": settings.embedding_provider,
                "dimension": embedding_model.embedding_dim
            }
        except Exception as e:
            logger.warning(f"Could not check embedding model health: {str(e)}")
            embedding_health = {
                "status": "error",
                "message": f"Failed to check embedding model: {str(e)}"
            }
        
        # Calculate overall status
        overall_status = "healthy"
        if storage_health.get("status") == "unhealthy" or embedding_health.get("status") == "error":
            overall_status = "unhealthy"
        elif storage_health.get("status") == "warning":
            overall_status = "warning"
            
        return {
            "status": overall_status,
            "documents_path": settings.documents_path,
            "embeddings_path": settings.embeddings_path,
            "storage": storage_health,
            "embedding": embedding_health,
            "version": "0.1.0",
            "timestamp": datetime.datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }


@app.get("/system/storage")
async def storage_info():
    """Get information about the storage backend."""
    try:
        from ragapi.api.dependencies import get_storage
        storage = await get_storage()
        storage_info = await storage.get_storage_info()
        
        return {
            "status": "success",
            "storage": storage_info,
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get storage info: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to get storage info: {str(e)}",
            "timestamp": datetime.datetime.now().isoformat()
        }


if __name__ == "__main__":
    # Run the application
    uvicorn.run(
        "ragapi.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
