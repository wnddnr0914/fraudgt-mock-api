from hashlib import sha256

from app.errors import ApiError, ErrorInfo
from app.repositories.base import Repository
from app.schemas.explanation import ExplanationAccepted, ExplanationJob, ExplanationResponse
from app.services.alert_service import AlertService
from app.services.graph_service import GraphService


class ExplanationService:
    def __init__(self, repository: Repository, alert_service: AlertService, graph_service: GraphService):
        self.repository = repository
        self.alert_service = alert_service
        self.graph_service = graph_service

    def _version(self, transaction_id, model_version):
        _, prediction = self.alert_service.require_alert(transaction_id)
        version = model_version if model_version is not None else prediction.model_version
        if version != prediction.model_version:
            raise ApiError(409, "MODEL_VERSION_MISMATCH", "요청한 모델 버전이 저장된 Alert 예측 버전과 다릅니다.")
        return version

    def request(self, transaction_id, model_version=None):
        version = self._version(transaction_id, model_version)
        # This is the worker enqueue boundary. Real deployments should persist a
        # unique (transaction_id, model_version) key before enqueueing the job.
        key = sha256(f"{transaction_id}\0{version}".encode()).hexdigest()
        candidate = ExplanationJob(transaction_id=transaction_id, explanation_id=f"EXP-{key}",
                                   status="pending", model_version=version)
        job = self.repository.create_job(candidate)
        return ExplanationAccepted.model_validate(job.model_dump())

    def get(self, transaction_id, model_version=None):
        version = self._version(transaction_id, model_version)
        job = self.repository.get_job(transaction_id, version)
        if job is None:
            return ExplanationResponse(transaction_id=transaction_id, status="not_requested", model_version=version)
        fixture = self.repository.get_explanation_fixture(transaction_id, version)
        if fixture is None:
            if job.status != "failed":
                job = job.model_copy(update={"status": "failed"})
                self.repository.save_job(job)
            return ExplanationResponse(transaction_id=transaction_id, explanation_id=job.explanation_id,
                                       status="failed", model_version=version,
                                       error=ErrorInfo(code="MOCK_RESULT_UNAVAILABLE", message="이 거래와 모델 버전에 준비된 Mock 설명이 없습니다."))
        status = fixture.status
        if job.status != status:
            job = job.model_copy(update={"status": status})
            self.repository.save_job(job)
        if status == "failed":
            return ExplanationResponse(transaction_id=transaction_id, explanation_id=job.explanation_id,
                                       status="failed", model_version=version, graph_snapshot=fixture.snapshot,
                                       error=ErrorInfo(code=fixture.error_code or "MOCK_EXPLANATION_FAILED",
                                                       message="미리 정의된 Mock 설명 실패 시나리오입니다."))
        return ExplanationResponse(transaction_id=transaction_id, explanation_id=job.explanation_id,
                                   status="completed", model_version=version,
                                   graph_snapshot=fixture.snapshot, edge_importance=fixture.edge_importance)

