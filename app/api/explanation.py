from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query

from app.api.alerts import TransactionId
from app.api.dependencies import get_services
from app.errors import error_responses
from app.schemas.explanation import ExplanationAccepted, ExplanationRequest, ExplanationResponse

router = APIRouter(prefix="/api/alerts", tags=["Explanation"])


@router.post("/{transaction_id}/explanation", status_code=202, response_model=ExplanationAccepted,
             responses=error_responses(404, 409, 422, 500), summary="설명 Mock 작업 생성",
             description=("GNNExplainer Worker의 향후 실행 인터페이스입니다. 실제 연산 없이 pending을 반환합니다. "
                          "동일 거래·모델 버전은 같은 작업을 재사용합니다. body 생략 시 현재 FraudGT 버전입니다. "
                          "이후 GET에서 준비된 completed 또는 failed 결과를 확인합니다."))
def request_explanation(
    transaction_id: TransactionId,
    body: Annotated[ExplanationRequest | None, Body(openapi_examples={
        "current": {"summary": "현재 Mock 모델", "value": {"model_version": "fraudgt-mock-v1"}}
    })] = None,
    services=Depends(get_services),
):
    return services.explanations.request(transaction_id, body.model_version if body else None)


@router.get("/{transaction_id}/explanation", response_model=ExplanationResponse,
            responses=error_responses(404, 409, 422, 500), summary="설명 상태와 Edge 중요도",
            description=("요청 전 not_requested, 요청 후 completed 또는 Fixture 실패 시 failed를 반환합니다. "
                         "importance는 FraudGT 점수가 아니라 주변 Edge의 설명 기여도 Mock 값입니다. "
                         "graph_snapshot 메타데이터로 추론 시점의 그래프·전처리·샘플링 버전을 구별합니다. "
                         "화면 그래프를 좁혔다면 일부 설명 Edge가 화면에 없을 수 있습니다."))
def get_explanation(
    transaction_id: TransactionId,
    model_version: Annotated[str | None, Query(min_length=1, max_length=100,
                                             description="생략 시 현재 FraudGT 버전")] = None,
    services=Depends(get_services),
):
    return services.explanations.get(transaction_id, model_version)
