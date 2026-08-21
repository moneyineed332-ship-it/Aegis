"""Tests for the consensus engine."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.consensus import StrategyVote, ConsensusEngine, add_strategy_vote, compute_consensus, clear_votes, get_engine


def test_strategy_vote_basic():
    vote = StrategyVote("sma", "SMA Crossover", "buy", 0.8, weight=1.5, reason="Golden cross")
    assert vote.strategy_id == "sma"
    assert vote.signal == "buy"
    assert vote.confidence == 0.8
    assert vote.weight == 1.5
    d = vote.to_dict()
    assert d["signal"] == "buy"
    assert d["confidence"] == 0.8
    assert d["weighted_score"] > 0


def test_strategy_vote_confidence_clamped():
    vote = StrategyVote("test", "Test", "buy", 1.5)
    assert vote.confidence == 1.0
    vote2 = StrategyVote("test", "Test", "buy", -0.5)
    assert vote2.confidence == 0.0


def test_strategy_vote_score():
    buy = StrategyVote("a", "A", "buy", 1.0)
    assert buy._score() == 1.0
    sell = StrategyVote("b", "B", "sell", 1.0)
    assert sell._score() == -1.0
    hold = StrategyVote("c", "C", "hold", 1.0)
    assert hold._score() == 0.0
    half = StrategyVote("d", "D", "buy", 0.5)
    assert half._score() == 0.5


def test_consensus_empty():
    engine = ConsensusEngine(min_votes=1)
    result = engine.compute_consensus()
    assert result["action"] == "hold"
    assert result["vote_count"] == 0
    assert "No votes" in result["reason"]


def test_consensus_insufficient_votes():
    engine = ConsensusEngine(min_votes=3)
    engine.add_vote("a", "A", "buy", 0.9)
    engine.add_vote("b", "B", "buy", 0.8)
    result = engine.compute_consensus()
    assert result["action"] == "hold"
    assert "Insufficient" in result["reason"]


def test_consensus_strong_buy():
    engine = ConsensusEngine(min_votes=2, min_confidence=0.5, min_agreement=0.6)
    engine.add_vote("a", "A", "buy", 0.9)
    engine.add_vote("b", "B", "buy", 0.8)
    engine.add_vote("c", "C", "buy", 0.7)
    result = engine.compute_consensus()
    assert result["action"] == "buy"
    assert result["confidence"] > 0.5
    assert result["agreement_ratio"] >= 0.6


def test_consensus_strong_sell():
    engine = ConsensusEngine(min_votes=2, min_confidence=0.5, min_agreement=0.6)
    engine.add_vote("a", "A", "sell", 0.9)
    engine.add_vote("b", "B", "sell", 0.8)
    engine.add_vote("c", "C", "sell", 0.7)
    result = engine.compute_consensus()
    assert result["action"] == "sell"


def test_consensus_mixed_signals():
    engine = ConsensusEngine(min_votes=2, min_confidence=0.5, min_agreement=0.6)
    engine.add_vote("a", "A", "buy", 0.8)
    engine.add_vote("b", "B", "sell", 0.8)
    engine.add_vote("c", "C", "hold", 0.8)
    result = engine.compute_consensus()
    assert result["action"] == "hold"
    assert "Mixed" in result["reason"] or "Insufficient agreement" in result["reason"]


def test_consensus_low_confidence():
    engine = ConsensusEngine(min_votes=2, min_confidence=0.7, min_agreement=0.6)
    engine.add_vote("a", "A", "buy", 0.3)
    engine.add_vote("b", "B", "buy", 0.4)
    result = engine.compute_consensus()
    assert result["action"] == "hold"
    assert "Low confidence" in result["reason"]


def test_consensus_zero_weight():
    engine = ConsensusEngine(min_votes=1, min_confidence=0.1, min_agreement=0.5)
    engine.add_vote("a", "A", "buy", 0.9, weight=0)
    engine.add_vote("b", "B", "buy", 0.9, weight=0)
    result = engine.compute_consensus()
    assert result["action"] == "hold"
    assert result["weighted_score"] == 0.0


def test_clear_votes():
    engine = ConsensusEngine(min_votes=1)
    engine.add_vote("a", "A", "buy", 0.9)
    assert len(engine.votes) == 1
    engine.clear_votes()
    assert len(engine.votes) == 0


def test_get_engine():
    engine = get_engine()
    assert isinstance(engine, ConsensusEngine)
    assert engine is not None


def test_global_consensus_functions():
    clear_votes()
    add_strategy_vote("sma", "SMA", "buy", 0.9)
    add_strategy_vote("rsi", "RSI", "buy", 0.8)
    add_strategy_vote("macd", "MACD", "buy", 0.7)
    result = compute_consensus()
    assert result["breakdown"]["total"] == 3
    assert result["action"] == "buy"
    clear_votes()


if __name__ == "__main__":
    test_strategy_vote_basic()
    test_strategy_vote_confidence_clamped()
    test_strategy_vote_score()
    test_consensus_empty()
    test_consensus_insufficient_votes()
    test_consensus_strong_buy()
    test_consensus_strong_sell()
    test_consensus_mixed_signals()
    test_consensus_low_confidence()
    test_consensus_zero_weight()
    test_clear_votes()
    test_get_engine()
    test_global_consensus_functions()
    print("All consensus tests passed.")
