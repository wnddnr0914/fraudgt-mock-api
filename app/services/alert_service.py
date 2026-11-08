from datetime import datetime, timezone

from app.errors import ApiError
from app.config import Settings
from app.repositories.base import Repository
from app.schemas.alert import AlertDetail, AlertItem, AlertListResponse


class AlertService:
    def __init__(self, repository: Repository, settings: Settings):
        self.repository = repository
        self.settings = settings

    def require_alert(self, transaction_id):
        transaction = self.repository.get_transaction(transaction_id)
        prediction = self.repository.get_prediction(transaction_id, self.settings.fraudgt_model_version)
        if transaction is None or prediction is None or prediction.fraud_score < self.settings.alert_threshold:
            raise ApiError(404, "ALERT_NOT_FOUND", "해당 거래가 없거나 현재 서버 임계값 이상의 Alert가 아닙니다.")
        return transaction, prediction

    def _item(self, transaction, prediction, *, detail=False):
        typology = self.repository.get_typology(transaction.transaction_id)
        if typology is not None and typology.model_version != self.settings.typology_model_version:
            typology = None
        model = AlertDetail if detail else AlertItem
        return model(
            transaction_id=transaction.transaction_id,
            timestamp=transaction.timestamp.astimezone(timezone.utc),
            sender_account=transaction.sender_account,
            receiver_account=transaction.receiver_account,
            amount=transaction.amount,
            currency=transaction.payment_currency,
            fraud_score=prediction.fraud_score,
            is_alert=prediction.fraud_score >= self.settings.alert_threshold,
            model_version=prediction.model_version,
            predicted_typology=typology.predicted_type if typology else None,
            typology_confidence=typology.confidence if typology else None,
            typology_model_version=typology.model_version if typology else None,
        )

    def list_alerts(self, start: datetime, end: datetime, page=1, page_size=20, min_score=None):
        if start.tzinfo is None or end.tzinfo is None:
            raise ApiError(422, "TIMEZONE_REQUIRED", "start와 end는 시간대를 포함한 ISO 8601이어야 합니다.")
        start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
        if start >= end:
            raise ApiError(400, "INVALID_PERIOD", "start는 end보다 빨라야 합니다. 종료 시각은 결과에 포함하지 않습니다.")
        cutoff = max(self.settings.alert_threshold, min_score if min_score is not None else self.settings.alert_threshold)
        rows = []
        for transaction in self.repository.transactions():
            prediction = self.repository.get_prediction(transaction.transaction_id, self.settings.fraudgt_model_version)
            if start <= transaction.timestamp < end and prediction is not None and prediction.fraud_score >= cutoff:
                rows.append((transaction, prediction))
        rows.sort(key=lambda pair: (pair[0].timestamp, pair[0].transaction_id), reverse=True)
        offset = (page - 1) * page_size
        return AlertListResponse(total=len(rows), page=page, page_size=page_size,
                                 alerts=[self._item(*pair) for pair in rows[offset:offset + page_size]])

    def get_alert(self, transaction_id):
        return self._item(*self.require_alert(transaction_id), detail=True)

