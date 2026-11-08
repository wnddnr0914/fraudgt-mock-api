from datetime import timedelta, timezone

from app.repositories.base import Repository
from app.schemas.graph import DisplayGraph, GraphEdge, GraphNode, GraphResponse
from app.services.alert_service import AlertService


class GraphService:
    def __init__(self, repository: Repository, alert_service: AlertService):
        self.repository = repository
        self.alert_service = alert_service

    def get_graph(self, transaction_id, hops=2, lookback_days=7):
        target, _ = self.alert_service.require_alert(transaction_id)
        end = target.timestamp.astimezone(timezone.utc)
        start = end - timedelta(days=lookback_days)
        eligible = [tx for tx in self.repository.transactions() if start <= tx.timestamp <= end]
        # Neighborhood discovery ignores direction, output never does. The two
        # target endpoints are the seed set (distance zero), not the target edge.
        reached = {target.sender_account, target.receiver_account}
        frontier = set(reached)
        for _ in range(hops):
            neighbors = set()
            for tx in eligible:
                if tx.sender_account in frontier:
                    neighbors.add(tx.receiver_account)
                if tx.receiver_account in frontier:
                    neighbors.add(tx.sender_account)
            frontier = neighbors - reached
            reached.update(frontier)
            if not frontier:
                break
        # Return the induced, time-filtered directed multigraph. Using IDs rather
        # than account pairs preserves parallel and identical-value transfers.
        selected = {tx.transaction_id: tx for tx in eligible
                    if tx.sender_account in reached and tx.receiver_account in reached}
        selected[target.transaction_id] = target
        edges = [GraphEdge(id=tx.transaction_id, source=tx.sender_account, target=tx.receiver_account,
                           amount=tx.amount, currency=tx.payment_currency,
                           timestamp=tx.timestamp.astimezone(timezone.utc),
                           is_target=tx.transaction_id == transaction_id)
                 for tx in sorted(selected.values(), key=lambda tx: (tx.timestamp, tx.transaction_id))]
        nodes = sorted({account for edge in edges for account in (edge.source, edge.target)})
        return GraphResponse(transaction_id=transaction_id, graph=DisplayGraph(
            hops=hops, lookback_days=lookback_days, window_start=start, window_end=end,
            nodes=[GraphNode(id=account) for account in nodes], edges=edges))

