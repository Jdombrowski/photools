import platform
from datetime import UTC, datetime

import psutil
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "service": "photools-api",
        "version": "0.1.0",
    }


@router.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with system information."""
    try:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        return {
            "status": "healthy",
            "timestamp": datetime.now(UTC).isoformat(),
            "service": "photools-api",
            "version": "0.1.0",
            "system": {
                "platform": platform.system(),
                "platform_release": platform.release(),
                "platform_version": platform.version(),
                "architecture": platform.machine(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
            },
            "resources": {
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used,
                    "free": memory.free,
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": (disk.used / disk.total) * 100,
                },
            },
            "dependencies": {
                "database": "pending",  # Will check DB connection when implemented
                "redis": "pending",  # Will check Redis connection when implemented
                "models": "pending",  # Will check AI models when implemented
            },
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(UTC).isoformat(),
            "error": str(e),
        }
