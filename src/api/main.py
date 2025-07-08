# src/api/main.py
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Import route modules
from src.api.routes import filesystem, health, photos


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    print("🚀 Starting Photools API...")
    yield
    # Cleanup logic
    print("🛑 Shutting down Photools API...")


# Create FastAPI app with lifespan
app = FastAPI(
    title="Photools API",
    description="Media cataloging suite for managing and executing AI model routing within a photo metadata database",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(photos.router, prefix="/api/v1")
app.include_router(filesystem.router, prefix="/api/v1")


@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/index.html")


@app.get("/api")
async def api_root():
    return {
        "message": "Photools API is running",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/v1/health",
        "ui": "/static/index.html",
    }


if __name__ == "__main__":
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
