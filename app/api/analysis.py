from fastapi import APIRouter, Depends

from app.api.alerts import TransactionId
from app.api.dependencies import get_services
from app.errors import error_responses
from app.schemas.analysis import AnalysisResponse

router = APIRouter(prefix="/api/alerts", tags=["Typology"])


@router.get("/{transaction_id}/analysis", response_model=AnalysisResponse,
            responses=error_responses(404, 422, 500), summary="자금세탁 유형 Mock 분석",
            description=("FraudGT 점수와 별도 유형 모델 예측·구조화된 근거를 반환합니다. "
                         "예측은 정답이나 규칙 검증이 아니며 verification_status=unverified입니다. "
                         "미분석 거래도 정상 응답합니다. 관련 ID와 방향성 계좌 경로는 공통 거래를 참조합니다. "
                         "Agent가 이 정보를 사용할 수 있으며 이 서버는 보고서를 생성하지 않습니다."))
def get_analysis(transaction_id: TransactionId, services=Depends(get_services)):
    return services.typology.get_analysis(transaction_id)
