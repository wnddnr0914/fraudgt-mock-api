from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.alerts import TransactionId
from app.api.dependencies import get_services
from app.errors import error_responses
from app.schemas.graph import GraphResponse

router = APIRouter(prefix="/api/alerts", tags=["Graph"])


@router.get("/{transaction_id}/graph", response_model=GraphResponse,
            responses=error_responses(404, 422, 500), summary="시점 기준 주변 Subgraph",
            description=("송금·수취 계좌를 hop 0으로 두고 입출금 양방향 이웃을 탐색합니다. "
                         "출력 Edge 방향과 반복 송금은 보존합니다. 시간 범위는 [target-lookback, target]입니다. "
                         "타깃 Edge를 반드시 포함하며 importance는 반환하지 않습니다. "
                         "설명용 고정 추론 그래프와 별개의 화면 표시용 그래프입니다."))
def get_graph(
    transaction_id: TransactionId,
    request: Request,
    hops: Annotated[int | None, Query(ge=1, le=3, description="탐색 깊이. 서버 기본값 2")] = None,
    lookback_days: Annotated[int | None, Query(ge=1, le=30, description="과거 조회 일수. 서버 기본값 7")] = None,
    services=Depends(get_services),
):
    settings = request.app.state.settings
    return services.graphs.get_graph(
        transaction_id,
        settings.graph_default_hops if hops is None else hops,
        settings.graph_default_lookback_days if lookback_days is None else lookback_days,
    )
