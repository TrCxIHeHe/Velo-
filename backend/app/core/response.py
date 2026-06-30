from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def success_response(data: Any, status_code: int = 200) -> JSONResponse:
    """Wrap data in the standard success envelope.

    jsonable_encoder handles UUID, datetime, and Pydantic models correctly.
    """
    return JSONResponse(
        status_code=status_code,
        content={"success": True, "data": jsonable_encoder(data)},
    )


def error_response(code: str, message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": {"code": code, "message": message}},
    )
