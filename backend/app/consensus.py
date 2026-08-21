"""Consensus Engine — aggregates signals from multiple strategies.

Inspired by AutoTrade Bot's multi-strategy consensus approach.
Strategies vote with signals + confidence, final decision is weighted average.
"""

from datetime import datetime, timezone
from typing import Literal


# Signal types
Signal = Literal["buy", "sell", "hold"]
Confidence = float  # 0.0 to 1.0


class StrategyVote:
    """A single strategy's vote."""

    def __init__(self, strategy_id: str, strategy_name: str, signal: Signal, confidence: Confidence, weight: float = 1.0, reason: str = ""):
        self.strategy_id = strategy_id
        self.strategy_name = strategy_name
        self.signal = signal
        self.confidence = max(0.0, min(1.0, confidence))  # Clamp 0-1
        self.weight = weight
        self.reason = reason
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "signal": self.signal,
            "confidence": round(self.confidence, 4),
            "weight": self.weight,
            "weighted_score": round(self._score(), 4),
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }

    def _score(self) -> float:
        """Convert signal to numeric score: buy=1, hold=0, sell=-1, scaled by confidence."""
        signal_map = {"buy": 1.0, "hold": 0.0, "sell": -1.0}
        return signal_map.get(self.signal, 0.0) * self.confidence


class ConsensusEngine:
    """Aggregates votes from multiple strategies."""

    def __init__(self, min_votes: int = 3, min_confidence: float = 0.5, min_agreement: float = 0.6):
        """
        Args:
            min_votes: Minimum strategies needed for consensus
            min_confidence: Minimum average confidence to act
            min_agreement: Minimum % of votes on same side (0.6 = 60%)
        """
        self.min_votes = min_votes
        self.min_confidence = min_confidence
        self.min_agreement = min_agreement
        self.votes: list[StrategyVote] = []

    def add_vote(self, strategy_id: str, strategy_name: str, signal: Signal, confidence: Confidence, weight: float = 1.0, reason: str = "") -> dict:
        """Add a strategy vote."""
        vote = StrategyVote(strategy_id, strategy_name, signal, confidence, weight, reason)
        self.votes.append(vote)
        return vote.to_dict()

    def clear_votes(self) -> None:
        """Clear all votes (call at start of each analysis cycle)."""
        self.votes = []

    def compute_consensus(self) -> dict:
        """Compute consensus from all votes."""
        if not self.votes:
            return {
                "action": "hold",
                "confidence": 0,
                "reason": "No votes cast",
                "vote_count": 0,
                "votes": [],
            }

        if len(self.votes) < self.min_votes:
            return {
                "action": "hold",
                "confidence": 0,
                "reason": f"Insufficient votes ({len(self.votes)}/{self.min_votes})",
                "vote_count": len(self.votes),
                "votes": [v.to_dict() for v in self.votes],
            }

        # Calculate weighted scores
        total_weight = sum(v.weight for v in self.votes)
        if total_weight == 0:
            total_weight = 1.0

        weighted_score = sum(v._score() * v.weight for v in self.votes) / total_weight
        avg_confidence = sum(v.confidence for v in self.votes) / len(self.votes)

        # Count agreement
        buy_votes = sum(1 for v in self.votes if v.signal == "buy")
        sell_votes = sum(1 for v in self.votes if v.signal == "sell")
        hold_votes = sum(1 for v in self.votes if v.signal == "hold")
        total_votes = len(self.votes)

        # Determine majority signal
        majority_signal = "hold"
        majority_count = hold_votes
        if buy_votes > majority_count:
            majority_signal = "buy"
            majority_count = buy_votes
        if sell_votes > majority_count:
            majority_signal = "sell"
            majority_count = sell_votes

        agreement_ratio = majority_count / total_votes

        # Decision logic
        action = "hold"
        reason = ""

        if agreement_ratio < self.min_agreement:
            reason = f"Insufficient agreement: {agreement_ratio*100:.0f}% < {self.min_agreement*100:.0f}% threshold"
        elif avg_confidence < self.min_confidence:
            reason = f"Low confidence: {avg_confidence*100:.0f}% < {self.min_confidence*100:.0f}% threshold"
        elif weighted_score > 0.3:
            action = "buy"
            reason = f"Strong buy consensus (score: {weighted_score:.2f})"
        elif weighted_score < -0.3:
            action = "sell"
            reason = f"Strong sell consensus (score: {weighted_score:.2f})"
        else:
            reason = f"Mixed signals (score: {weighted_score:.2f})"

        return {
            "action": action,
            "confidence": round(avg_confidence, 4),
            "weighted_score": round(weighted_score, 4),
            "agreement_ratio": round(agreement_ratio, 4),
            "majority_signal": majority_signal,
            "breakdown": {
                "buy": buy_votes,
                "sell": sell_votes,
                "hold": hold_votes,
                "total": total_votes,
            },
            "reason": reason,
            "votes": [v.to_dict() for v in self.votes],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Global consensus engine instance
_engine = ConsensusEngine()


def get_engine() -> ConsensusEngine:
    """Get the global consensus engine."""
    return _engine


def add_strategy_vote(strategy_id: str, strategy_name: str, signal: Signal, confidence: Confidence, weight: float = 1.0, reason: str = "") -> dict:
    """Convenience: add a vote to the global engine."""
    return _engine.add_vote(strategy_id, strategy_name, signal, confidence, weight, reason)


def compute_consensus() -> dict:
    """Convenience: compute consensus from global engine."""
    return _engine.compute_consensus()


def clear_votes() -> None:
    """Convenience: clear all votes."""
    _engine.clear_votes()
