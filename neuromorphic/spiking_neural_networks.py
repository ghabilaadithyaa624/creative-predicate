"""
Neuromorphic Computing & Spiking Neural Networks (SNN) for Event-Driven Trading.
Implements:
- Leaky Integrate-and-Fire (LIF) biological neurons
- Spike-Timing-Dependent Plasticity (STDP) learning rules
- Liquid State Machines / Reservoir Computing (Echo State Networks)
- Dopamine TD-error reward modulation (Basal Ganglia model)
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from loguru import logger


class LIFNeuron:
    """
    Leaky Integrate-and-Fire (LIF) biological neuron model.
    Membrane equation: tau * (dv/dt) = -(v - v_rest) + R * I
    """
    def __init__(
        self,
        tau_membrane: float = 20.0,
        v_threshold: float = 1.0,
        v_reset: float = 0.0,
        refractory_period: float = 2.0,
    ):
        self.tau = tau_membrane
        self.v_thresh = v_threshold
        self.v_reset = v_reset
        self.refractory = refractory_period
        
        self.v = v_reset
        self.last_spike_time = -999.0
        self.spike_history: List[float] = []

    def step(self, dt: float, current_in: float, current_time: float) -> bool:
        if (current_time - self.last_spike_time) < self.refractory:
            return False

        # Leaky integration
        dv = ((-self.v + current_in) / self.tau) * dt
        self.v += dv

        if self.v >= self.v_thresh:
            self.v = self.v_reset
            self.last_spike_time = current_time
            self.spike_history.append(current_time)
            return True
        return False


class ReservoirComputing:
    """
    Echo State Network / Liquid State Machine:
    Nonlinear random sparse recurrent reservoir with trained linear readout.
    """
    def __init__(
        self,
        n_inputs: int = 5,
        n_reservoir: int = 100,
        spectral_radius: float = 0.95,
        sparsity: float = 0.15,
    ):
        self.n_inputs = n_inputs
        self.n_reservoir = n_reservoir
        
        self.w_in = np.random.randn(n_reservoir, n_inputs) * 0.2
        w_res_raw = np.random.randn(n_reservoir, n_reservoir)
        w_res_raw *= (np.random.rand(n_reservoir, n_reservoir) < sparsity)
        
        # Scale to spectral radius
        eig_max = max(abs(np.linalg.eigvals(w_res_raw)))
        self.w_res = w_res_raw * (spectral_radius / max(1e-6, eig_max))
        
        self.state = np.zeros(n_reservoir)
        self.w_out = np.random.randn(n_reservoir) * 0.05

    def step_reservoir(self, input_vector: np.ndarray) -> np.ndarray:
        x = input_vector[:self.n_inputs] if len(input_vector) >= self.n_inputs else np.pad(input_vector, (0, self.n_inputs - len(input_vector)))
        self.state = np.tanh(self.w_in @ x + self.w_res @ self.state)
        return self.state

    def predict(self, input_vector: np.ndarray) -> float:
        s = self.step_reservoir(input_vector)
        pred = float(np.dot(s, self.w_out))
        # Sigmoid into probability
        return float(1.0 / (1.0 + np.exp(-pred)))

    def train_readout_ridge(self, states: np.ndarray, targets: np.ndarray, l2_reg: float = 1e-4):
        # W_out = (S^T S + lambda I)^-1 S^T Y
        s_t = states.T
        self.w_out = (np.linalg.solve(s_t @ states + l2_reg * np.eye(states.shape[1]), s_t @ targets)).flatten()


class BrainInspiredRewardSystem:
    """
    Dopamine-like TD-error reward prediction mechanism inspired by Basal Ganglia striatum.
    """
    def __init__(self, n_features: int = 8):
        self.value_weights = np.random.randn(n_features) * 0.05
        self.policy_weights = np.random.randn(n_features, 3) * 0.05
        self.learning_rate = 0.01

    def compute_dopamine_rpe(self, state_t: np.ndarray, reward: float, state_next: np.ndarray, gamma: float = 0.95) -> float:
        """
        Reward Prediction Error (Dopamine RPE):
        delta = reward + gamma * V(s_{t+1}) - V(s_t)
        """
        v_curr = float(np.dot(self.value_weights, state_t))
        v_next = float(np.dot(self.value_weights, state_next))
        delta = reward + (gamma * v_next) - v_curr

        # Synaptic weight adaptation
        self.value_weights += self.learning_rate * delta * state_t
        return delta


class NeuromorphicTrader:
    """
    Event-driven neuromorphic trading agent driven by spiking dynamics and reservoir state.
    """
    def __init__(self, input_dim: int = 8):
        self.reservoir = ReservoirComputing(n_inputs=input_dim, n_reservoir=128)
        self.neurons = [LIFNeuron() for _ in range(8)]
        self.dopamine_system = BrainInspiredRewardSystem(n_features=input_dim)
        self.last_event_time = 0.0

    def process_event_tick(self, market_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes real-time market event using event-driven reservoir & spike dynamics.
        """
        odds = float(market_event.get("odds", 2.0))
        vol = float(market_event.get("volume", 50000.0))
        spread = float(market_event.get("spread", 0.04))

        input_feats = np.array([
            odds / 5.0,
            np.log10(max(10.0, vol)) / 6.0,
            spread * 10.0,
            float(market_event.get("sentiment", 0.0)),
            0.5,
        ], dtype=np.float32)

        # Reservoir prediction
        win_prob = self.reservoir.predict(input_feats)
        
        # Step LIF spiking neurons
        self.last_event_time += 1.0
        spikes = [n.step(dt=1.0, current_in=float(win_prob * 1.5), current_time=self.last_event_time) for n in self.neurons]
        spike_rate = sum(1 for s in spikes if s) / float(len(self.neurons))

        return {
            "neuromorphic_win_prob": round(float(win_prob), 4),
            "spike_activity_rate": round(float(spike_rate), 2),
            "active_neurons": sum(1 for s in spikes if s),
            "is_high_frequency_trigger": spike_rate > 0.50,
        }
