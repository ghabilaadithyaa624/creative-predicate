"""
Unit tests for Quantum, Federated, and Neuromorphic modules.
"""
import numpy as np
from quantum.quantum_portfolio_optimizer import QuantumPortfolioOptimizer, QuantumMachineLearning
from federated.federated_learning import FederatedServer, FederatedClient, ShamirSecretSharing
from neuromorphic.spiking_neural_networks import LIFNeuron, ReservoirComputing, NeuromorphicTrader, BrainInspiredRewardSystem


def test_quantum_portfolio_optimization():
    q_opt = QuantumPortfolioOptimizer()
    exp_returns = np.array([0.12, 0.18, 0.08, 0.15])
    cov_matrix = np.array([
        [0.04, 0.01, 0.005, 0.01],
        [0.01, 0.09, 0.01, 0.02],
        [0.005, 0.01, 0.02, 0.005],
        [0.01, 0.02, 0.005, 0.06]
    ])
    res = q_opt.solve_qaoa(exp_returns, cov_matrix, risk_factor=0.5)
    assert len(res.weights) == 4
    assert round(sum(res.weights), 2) == 1.0
    assert res.sharpe > 0


def test_quantum_machine_learning():
    qml = QuantumMachineLearning(n_qubits=6, n_layers=2)
    feats = np.array([0.5, -0.2, 0.8, -0.1, 0.3, 0.9])
    exp_val = qml.forward(feats)
    assert 0.0 <= exp_val <= 1.0


def test_federated_shamir_and_fedavg():
    # Shamir Secret Sharing
    sss = ShamirSecretSharing()
    secret = 42069
    shares = sss.split_secret(secret, n_shares=5, threshold_k=3)
    reconstructed = sss.reconstruct_secret(shares[:3])
    assert reconstructed == secret

    # Federated Server & Client
    server = FederatedServer(model_dim=10)
    c1 = FederatedClient("agent_1", model_dim=10)
    c2 = FederatedClient("agent_2", model_dim=10)

    u1 = c1.compute_local_update(server.global_weights)
    u2 = c2.compute_local_update(server.global_weights)

    agg_res = server.aggregate_updates([u1, u2])
    assert agg_res["round"] == 1
    assert agg_res["participating_clients"] == 2


def test_neuromorphic_lif_and_reservoir():
    neuron = LIFNeuron(v_threshold=1.0)
    spikes = [neuron.step(dt=1.0, current_in=2.0, current_time=t) for t in range(20)]
    assert any(spikes)  # Spikes under supra-threshold current

    rc = ReservoirComputing(n_inputs=4, n_reservoir=50)
    pred_p = rc.predict(np.array([0.5, 0.2, 0.8, 0.1]))
    assert 0.0 < pred_p < 1.0

    trader = NeuromorphicTrader(input_dim=5)
    event_res = trader.process_event_tick({"odds": 2.10, "volume": 100000, "spread": 0.03})
    assert "neuromorphic_win_prob" in event_res
    assert "spike_activity_rate" in event_res
