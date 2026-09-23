import uvicorn

from app.core.settings import settings

if __name__ == "__main__":
    server = settings.uvicorn

    uvicorn.run(
        "app.main:app",
        host=server.host,
        port=server.port,
        log_level=server.log_level,
        reload=server.reload,
    )
