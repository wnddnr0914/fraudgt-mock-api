from typing import Literal

from pydantic import AwareDatetime, Field

from app.schemas.common import Contract, Score


class AlertItem(Contract):
    transaction_id: str = Field(description="개별 송금 거래 ID. 계좌 ID, 모델 Node Index와 다릅니다.", examples=["TX000003"])
    timestamp: AwareDatetime = Field(description="거래 시각. 응답은 UTC ISO 8601입니다.")
    sender_account: str = Field(description="원본 송금 계좌 식별자.")
    receiver_account: str = Field(description="원본 수취 계좌 식별자.")
    amount: float = Field(ge=0, allow_inf_nan=False, description="송금 원통화 금액. 다른 통화와 합산하지 않습니다.")
    currency: str = Field(description="원본 Payment_currency 값. 반드시 ISO 통화 코드인 것은 아닙니다.")
    fraud_score: Score = Field(description="저장된 FraudGT Mock 이상 점수. Explainer 중요도, 정답 라벨과 별개입니다.")
    is_alert: bool = Field(description="fraud_score >= 서버 alert_threshold.")
    model_version: str = Field(description="이상 점수를 생성한 FraudGT 버전.", examples=["fraudgt-mock-v1"])
    predicted_typology: str | None = Field(default=None, description="독립 유형 모델의 Mock 예측명. 정답 라벨이 아닙니다.")
    typology_confidence: Score | None = Field(default=None, description="유형 모델의 신뢰도. FraudGT 점수와 별개입니다.")
    typology_model_version: str | None = Field(default=None, description="유형 분석이 없으면 null.")
    status: Literal["unreviewed"] = "unreviewed"


class AlertDetail(AlertItem):
    """동일한 거래 ID를 다른 기능에 전달할 수 있는 거래 상세."""


class AlertListResponse(Contract):
    total: int = Field(ge=0, description="페이지 제한 적용 전 전체 필터 결과 수.")
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    alerts: list[AlertItem]

