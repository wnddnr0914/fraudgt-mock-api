from typing import Literal

from pydantic import AwareDatetime, Field

from app.schemas.common import Contract


class GraphNode(Contract):
    id: str = Field(description="원본 계좌 ID. 모델의 정수 Node Index가 아닙니다.")


class GraphEdge(Contract):
    id: str = Field(description="공통 transaction_id. 같은 계좌 쌍의 반복 송금도 개별 Edge로 유지합니다.")
    source: str = Field(description="원본 송금 계좌 ID.")
    target: str = Field(description="원본 수취 계좌 ID.")
    amount: float = Field(ge=0, allow_inf_nan=False)
    currency: str
    timestamp: AwareDatetime
    is_target: bool


class DisplayGraph(Contract):
    hops: int = Field(ge=1, le=3, description="타깃 양 끝 계좌를 0-Hop으로 하는 양방향 인접 탐색 깊이.")
    lookback_days: int = Field(ge=1, le=30)
    neighborhood_direction: Literal["both"] = Field(default="both", description="이웃 탐색만 양방향입니다. 응답 Edge 방향은 원본 송금 방향입니다.")
    window_start: AwareDatetime = Field(description="포함되는 과거 시각 하한.")
    window_end: AwareDatetime = Field(description="포함되는 거래 시각 상한. 타깃 거래 시각으로 고정됩니다.")
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphResponse(Contract):
    transaction_id: str
    graph: DisplayGraph = Field(description="화면 조회 그래프. 중요도가 없으며 설명용 고정 추론 그래프와 구분됩니다.")

