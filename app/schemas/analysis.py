from typing import Literal

from pydantic import Field

from app.schemas.common import Contract, Score


class TypologyPrediction(Contract):
    predicted_type: str = Field(description="Mock 출력 라벨. SAML-D Laundering_type 정답과 자동으로 같다고 보지 않습니다.")
    confidence: Score = Field(description="독립적인 유형 모델 신뢰도. FraudGT 점수와 별개입니다.")
    verification_status: Literal["unverified", "verified", "rejected"] = Field(description="별도 구조 검증 상태. 현재 Mock은 미검증 unverified입니다.")
    model_version: str


class AnalysisEvidence(Contract):
    related_transaction_ids: list[str] = Field(description="공통 거래 Fixture에 존재하는 근거 거래 ID들.")
    account_path: list[str] = Field(description="근거 거래들에서 실제 송금 방향으로 연결되는 계좌 경로.")
    description: str = Field(description="Mock 거래 구조에 관한 관찰. 범죄 확정이나 Rule 검증 결과가 아닙니다.")


class AnalysisResponse(Contract):
    transaction_id: str
    fraud_score: Score
    model_version: str = Field(description="FraudGT 점수의 모델 버전.")
    typology: TypologyPrediction | None = Field(default=None, description="분석이 아직 없으면 null.")
    evidence: AnalysisEvidence | None = Field(default=None, description="분석이 아직 없으면 null.")

