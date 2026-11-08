"""Shared app construction; service selection changes routes, not JSON contracts."""
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.api import alerts, analysis, explanation, graph
from app.config import Settings
from app.deployment import SERVICE_SPECS, ServiceName
from app.errors import ApiError
from app.repositories.mock_repository import MockRepository
from app.repositories.base import Repository
from app.services.alert_service import AlertService
from app.services.graph_service import GraphService
from app.services.explanation_service import ExplanationService
from app.services.typology_service import TypologyService

log = logging.getLogger("fraudgt_mock")


def create_app(settings: Settings | None = None, repository: Repository | None = None,
               *, service: ServiceName | Literal["all"] = "all") -> FastAPI:
    if service != "all" and service not in SERVICE_SPECS:
        raise ValueError(f"Unknown service: {service!r}")
    settings = settings if settings is not None else Settings.from_env()
    repository = repository if repository is not None else MockRepository(source_timezone=settings.source_timezone)
    alert_service = AlertService(repository, settings)
    graph_service = GraphService(repository, alert_service)
    app = FastAPI(
        title="FraudGT AML Mock API" if service == "all" else f"FraudGT AML — {SERVICE_SPECS[service].title}",
        version="1.0.0",
        description=("프론트엔드·그래프·Agent 연동을 위한 합성 거래 기반 API. "
                     "거래 조회·그래프·설명·유형 분석은 서비스별 Base URL로 독립 실행합니다. "
                     "실제 SAML-D 행이나 ML 추론 결과가 아닙니다. fraud_score, edge importance, "
                     "typology confidence는 서로 다른 Mock 출력입니다. 모든 시간 응답은 UTC로 정규화합니다."),
    )
    app.state.settings = settings
    app.state.service_name = service
    app.state.repository = repository
    app.state.services = SimpleNamespace(
        alerts=alert_service,
        graphs=graph_service,
        explanations=ExplanationService(repository, alert_service, graph_service),
        typology=TypologyService(repository, alert_service),
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False,
        allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
    )

    def error_response(request: Request, status_code: int, code: str, message: str, details=None):
        headers = {}
        origin = request.headers.get("origin")
        # ServerErrorMiddleware handles unhandled errors outside CORSMiddleware.
        if origin and origin in settings.cors_origins:
            headers = {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}
        return JSONResponse(status_code=status_code, headers=headers, content={
            "error": {"code": code, "message": message, "details": details or []}
        })

    @app.exception_handler(ApiError)
    async def domain_error(request: Request, exc: ApiError):
        return error_response(request, exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        details = [{"loc": list(item["loc"]), "type": item["type"], "message": item["msg"]}
                   for item in exc.errors()]
        return error_response(request, 422, "VALIDATION_ERROR", "Request parameters are invalid", details)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error_response(request, exc.status_code, "HTTP_ERROR", str(exc.detail))

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        log.error("Unexpected request failure", exc_info=(type(exc), exc, exc.__traceback__))
        return error_response(request, 500, "INTERNAL_ERROR", "An internal error occurred")

    routers = {"alerts": alerts.router, "graph": graph.router,
               "explanation": explanation.router, "analysis": analysis.router}
    for name, router in routers.items():
        if service == "all" or name == service:
            app.include_router(router)

    def documented_openapi():
        if app.openapi_schema is None:
            spec = get_openapi(title=app.title, version=app.version,
                               description=app.description, routes=app.routes)
            examples_path = Path(__file__).parent / "api" / "response_examples.json"
            if examples_path.exists():
                examples = json.loads(examples_path.read_text(encoding="utf-8"))
                for path, methods in examples.items():
                    for method, statuses in methods.items():
                        if method not in spec["paths"].get(path, {}):
                            continue
                        for status, example in statuses.items():
                            media = spec["paths"][path][method]["responses"][status]["content"]["application/json"]
                            media["examples"] = {"fixture": example}
            app.openapi_schema = spec
        return app.openapi_schema

    app.openapi = documented_openapi
    return app
