from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from pydantic import AwareDatetime, BeforeValidator

from app.api.dependencies import get_services
from app.errors import error_responses
from app.schemas.alert import AlertDetail, AlertListResponse

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])
TransactionId = Annotated[str, Path(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_-]+$",
                                   description="조회할 개별 거래 ID. 계좌 ID와 구분합니다.", examples=["TX000003"])]


def require_iso_datetime(value):
    if not isinstance(value, str) or "T" not in value.upper():
        raise ValueError("Use a timezone-aware ISO 8601 datetime, for example 2022-11-01T00:00:00Z")
    return value


IsoDatetime = Annotated[AwareDatetime, BeforeValidator(require_iso_datetime)]


@router.get("", response_model=AlertListResponse,
            responses=error_responses(400, 422, 500), summary="기간별 이상거래 목록",
            description=("저장된 Mock 예측을 조회합니다. start <= timestamp < end, 최신 시각·ID 내림차순입니다. "
                         "항상 서버 Alert Threshold 이상의 거래만 반환하며 min_score는 추가 필터입니다. "
                         "total은 페이지를 자르기 전 전체 개수입니다. 실제 추론은 수행하지 않습니다."))
def list_alerts(
    start: Annotated[IsoDatetime, Query(description="포함할 시작 시각. timezone 필수", examples=["2022-11-01T00:00:00Z"])],
    end: Annotated[IsoDatetime, Query(description="제외할 종료 시각. timezone 필수", examples=["2022-11-02T00:00:00Z"])],
    page: Annotated[int, Query(ge=1, description="1부터 시작하는 페이지")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="페이지 크기, 최대 100")] = 20,
    min_score: Annotated[float | None, Query(ge=0, le=1, allow_inf_nan=False,
                                           description="추가 점수 하한. 생략 시 서버 Alert Threshold")] = None,
    services=Depends(get_services),
):
    return services.alerts.list_alerts(start, end, page, page_size, min_score)


@router.get("/{transaction_id}", response_model=AlertDetail,
            responses=error_responses(404, 422, 500), summary="이상거래 상세",
            description=("거래·고정 FraudGT Mock 점수·유형 예측을 반환합니다. "
                         "존재하지 않거나 서버 임계값 미만인 거래는 404입니다. 정답 라벨은 반환하지 않습니다."))
def get_alert(transaction_id: TransactionId, services=Depends(get_services)):
    return services.alerts.get_alert(transaction_id)
