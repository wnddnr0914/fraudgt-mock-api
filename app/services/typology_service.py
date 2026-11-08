from app.repositories.base import Repository
from app.schemas.analysis import AnalysisEvidence, AnalysisResponse, TypologyPrediction
from app.services.alert_service import AlertService


class TypologyService:
    def __init__(self, repository: Repository, alert_service: AlertService):
        self.repository = repository
        self.alert_service = alert_service

    def get_analysis(self, transaction_id):
        _, prediction = self.alert_service.require_alert(transaction_id)
        result = self.repository.get_typology(transaction_id)
        if result is not None and result.model_version != self.alert_service.settings.typology_model_version:
            result = None
        if result is None:
            return AnalysisResponse(transaction_id=transaction_id, fraud_score=prediction.fraud_score,
                                    model_version=prediction.model_version)
        return AnalysisResponse(transaction_id=transaction_id, fraud_score=prediction.fraud_score,
                                model_version=prediction.model_version,
                                typology=TypologyPrediction(predicted_type=result.predicted_type,
                                    confidence=result.confidence, verification_status=result.verification_status,
                                    model_version=result.model_version),
                                evidence=AnalysisEvidence(related_transaction_ids=result.related_transaction_ids,
                                    account_path=result.account_path, description=result.description))
