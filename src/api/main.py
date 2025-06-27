from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(
    title="Photools",
    description="Media cataloging suite for managing and executing AI model routing within a photo metadata database",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Photools API",
        "version": "0.1.0",
        "docs": "/docs",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "database_url": os.getenv("DATABASE_URL", "not configured"), # TODO: Configure for production
        "redis_url": os.getenv("REDIS_URL", "not configured") # TODO: Configure for production
    }

@app.get("/api/v1/photos")
async def list_photos():
    """List photos endpoint (placeholder)"""
    return {
        "photos": [],
        "total": 0,
        "message": "Photo listing endpoint - ready for implementation"
    }

@app.post("/api/v1/photos/upload")
async def upload_photo():
    """Upload photo endpoint (placeholder)""" # TODO: Implement photo upload logic
    return {
        "message": "Photo upload endpoint - ready for implementation",
        "status": "not_implemented"
    }

@app.get("/api/v1/search")
async def search_photos():
    """Search photos endpoint (placeholder)""" # TODO: Implement search logic
    return {
        "results": [],
        "total": 0,
        "message": "Photo search endpoint - ready for implementation"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
    