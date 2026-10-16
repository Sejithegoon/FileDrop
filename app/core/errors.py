"""API errors with stable codes: {"error": {"code", "message", "details"}}."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, **details):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return JSONResponse({"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
                            status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _invalid(request: Request, exc: RequestValidationError):
        return JSONResponse({"error": {"code": "INVALID_REQUEST", "message": "The request was not valid.",
                                       "details": {"errors": str(exc.errors())[:500]}}}, status_code=400)
