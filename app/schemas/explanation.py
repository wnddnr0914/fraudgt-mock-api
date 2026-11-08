from typing import Literal

from pydantic import Field

from app.errors import ErrorInfo
from app.schemas.common import Contract
from app.schemas.transaction import EdgeImportance, GraphSnapshot


class ExplanationRequest(Contract):
    model_version: str | None = Field(default=None, min_length=1, max_length=100, description="저장된 타깃 예측의 모델 버전. 생략하면 서버 FraudGT 버전.", examples=["fraudgt-mock-v1"])


class ExplanationAccepted(Contract):
    transaction_id: str
    explanation_id: str = Field(description="거래와 모델 버전 쌍의 안정적인 작업 ID.")
    status: Literal["pending", "completed", "failed"] = Field(description="최초 요청은 pending. 중복 요청은 같은 작업의 현재 상태를 재사용합니다.")
    model_version: str


class ExplanationJob(ExplanationAccepted):
    """Repository에 저장할 최소 작업 상태. 실 Worker Queue로 교체 가능한 레코드."""


class ExplanationResponse(Contract):
    transaction_id: str
    explanation_id: str | None = None
    status: Literal["not_requested", "pending", "completed", "failed"]
    method: Literal["GNNExplainer"] = "GNNExplainer"
    model_version: str
    graph_snapshot: GraphSnapshot | None = Field(default=None, description="모델의 예측 입력을 재현하기 위한 고정 그래프. 화면 graph Query와 독립적입니다.")
    edge_importance: list[EdgeImportance] = Field(default_factory=list, description="타깃 예측 설명에 대한 Context Edge 중요도. 이상 확률이나 유형 확률이 아닙니다.")
    error: ErrorInfo | None = None

