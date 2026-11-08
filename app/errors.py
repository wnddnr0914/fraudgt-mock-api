"""Public errors shared by routers and services, independent of FastAPI."""
from typing import Any

from pydantic import BaseModel, Field


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class ErrorInfo(BaseModel):
    code: str = Field(description="Stable machine-readable error code")
    message: str = Field(description="Human-readable reason")
    details: list[dict[str, Any]] = Field(default_factory=list, description="Parameter validation details")


class ErrorResponse(BaseModel):
    error: ErrorInfo


def error_responses(*codes: int) -> dict:
    examples = {
        400: ("INVALID_PERIOD", "start must be earlier than end"),
        404: ("ALERT_NOT_FOUND", "Transaction is absent or below the configured alert threshold"),
        409: ("MODEL_VERSION_MISMATCH", "The requested version does not match this prediction"),
        422: ("VALIDATION_ERROR", "Request parameters are invalid"),
        500: ("INTERNAL_ERROR", "An internal error occurred"),
    }
    return {
        code: {
            "model": ErrorResponse,
            "description": examples[code][1],
            "content": {"application/json": {"example": {
                "error": {"code": examples[code][0], "message": examples[code][1], "details": []}
            }}},
        }
        for code in codes
    }
