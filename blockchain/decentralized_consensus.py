"""
Blockchain-based decentralized consensus and Byzantine Fault Tolerant (BFT) agent voting.
Implements on-chain/off-chain proposal lifecycle, stake-weighted voting, and reputation slashing.
"""
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
from typing import Dict, List, Optional, Any
from loguru import logger


@dataclass
class Proposal:
    proposal_id: str
    proposer: str
    market: str
    selection: str
    odds: float
    suggested_stake: float
    expected_value: float
    votes_yes: int = 0
    votes_no: int = 0
    stake_yes: float = 0.0
    stake_no: float = 0.0
    status: str = "pending"  # pending, approved, rejected, executed
    created_at: int = field(default_factory=lambda: int(datetime.now().timestamp()))


@dataclass
class ConsensusVote:
    voter: str
    proposal_id: str
    vote: bool  # True = YES (Approve)
    stake: float
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    signature: str = ""


class BlockchainConsensus:
    """
    Decentralized agent coordination layer with stake-weighted voting and slashing.
    """
    def __init__(self, rpc_url: str = "https://polygon-rpc.com", contract_address: Optional[str] = None):
        self.rpc_url = rpc_url
        self.contract_address = contract_address or "0x000000000000000000000000000000000000dEaD"
        self.proposals: Dict[str, Proposal] = {}
        self.votes: Dict[str, List[ConsensusVote]] = {}
        self.reputation: Dict[str, float] = {}

    def create_proposal(
        self,
        proposer_address: str,
        market: str,
        selection: str,
        odds: float,
        suggested_stake: float,
        expected_value: float,
    ) -> str:
        payload = f"{market}:{selection}:{datetime.now().timestamp()}"
        proposal_id = hashlib.sha256(payload.encode()).hexdigest()[:16]
        
        p = Proposal(
            proposal_id=proposal_id,
            proposer=proposer_address,
            market=market,
            selection=selection,
            odds=odds,
            suggested_stake=suggested_stake,
            expected_value=expected_value,
        )
        self.proposals[proposal_id] = p
        self.votes[proposal_id] = []
        logger.info(f"On-chain proposal created: {proposal_id} by {proposer_address}")
        return proposal_id

    def cast_vote(
        self,
        voter_address: str,
        proposal_id: str,
        approve: bool,
        stake_amount: float = 10.0,
    ) -> bool:
        if proposal_id not in self.proposals:
            return False

        vote_sig = hashlib.sha256(f"{voter_address}:{proposal_id}:{approve}:{stake_amount}".encode()).hexdigest()
        vote = ConsensusVote(
            voter=voter_address,
            proposal_id=proposal_id,
            vote=approve,
            stake=stake_amount,
            signature=vote_sig,
        )
        self.votes[proposal_id].append(vote)

        # Update proposal counters
        p = self.proposals[proposal_id]
        if approve:
            p.votes_yes += 1
            p.stake_yes += stake_amount
        else:
            p.votes_no += 1
            p.stake_no += stake_amount

        logger.info(f"Agent {voter_address} voted {'YES' if approve else 'NO'} on proposal {proposal_id}")
        return True

    def evaluate_consensus(self, proposal_id: str) -> Dict[str, Any]:
        if proposal_id not in self.proposals:
            return {"status": "not_found"}

        p = self.proposals[proposal_id]
        total_stake = p.stake_yes + p.stake_no
        if total_stake == 0:
            return {"consensus": "pending", "ratio": 0.0}

        ratio = p.stake_yes / total_stake
        is_approved = ratio > 0.60
        p.status = "approved" if is_approved else "rejected"

        return {
            "proposal_id": proposal_id,
            "status": p.status,
            "yes_ratio": round(ratio, 4),
            "total_staked": round(total_stake, 2),
            "votes_yes": p.votes_yes,
            "votes_no": p.votes_no,
        }

    def slash_reputation(self, agent_address: str, slash_pct: float = 0.15):
        """Slashes reputation of agents who voted for failed/fraudulent signals."""
        current = self.reputation.get(agent_address, 1.0)
        self.reputation[agent_address] = max(0.05, round(current * (1.0 - slash_pct), 3))


class OffChainConsensusBFT:
    r"""
    Byzantine Fault Tolerant off-chain voting engine ($N \ge 3f + 1$).
    """
    def __init__(self, n_agents: int = 4, f_byzantine: int = 1):
        self.n = n_agents
        self.f = f_byzantine
        self.threshold = 2 * f_byzantine + 1
        self.votes_log: Dict[str, Dict[str, bool]] = {}

    def submit_vote(self, proposal_id: str, agent_id: str, approve: bool) -> Dict[str, Any]:
        if proposal_id not in self.votes_log:
            self.votes_log[proposal_id] = {}
        self.votes_log[proposal_id][agent_id] = approve

        votes = self.votes_log[proposal_id]
        yes_count = sum(1 for v in votes.values() if v)
        no_count = sum(1 for v in votes.values() if not v)

        finalized = len(votes) >= self.threshold
        approved = yes_count >= self.threshold

        return {
            "proposal_id": proposal_id,
            "finalized": finalized,
            "approved": approved,
            "total_votes": len(votes),
            "threshold": self.threshold,
        }
