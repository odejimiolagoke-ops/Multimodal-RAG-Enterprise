import logging

from fastapi import Request
from fastapi.responses import JSONResponse


def register_exception_handlers(app):
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logging.exception("Unhandled application error for %s", request.url.path)
        return JSONResponse(status_code=500, content={"error": "Internal server error"})

    return app
