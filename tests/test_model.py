"""Unit tests for MARVI Deep Learning LSTM forecaster and Physics Loss."""
import os
import torch
from torch.utils.data import TensorDataset, DataLoader
import numpy as np
import pytest

from marvi_model.lstm import MARVILSTM, PhysicsInformedLoss
from marvi_model.trainer import LSTMTrainer


def test_lstm_forward_pass_shapes():
    model = MARVILSTM(input_dim=6, hidden_dim=32, num_layers=2, dropout=0.1)
    batch_size = 4
    seq_len = 8
    input_dim = 6
    x = torch.randn(batch_size, seq_len, input_dim)

    y_60d, y_90d = model(x)
    assert y_60d.shape == (batch_size, 1)
    assert y_90d.shape == (batch_size, 1)


def test_physics_loss_gradient_flow():
    loss_fn = PhysicsInformedLoss(physics_weight=0.2)
    batch_size = 4
    # Predictions: 60d depth is deeper than 90d (i.e. predicting water level magically rises)
    y_pred_60d = torch.tensor([[12.0], [13.0], [11.0], [10.0]], requires_grad=True)
    y_pred_90d = torch.tensor([[8.0], [9.0], [7.0], [6.0]], requires_grad=True)

    y_true_60d = torch.tensor([[11.5], [12.5], [10.5], [9.5]])
    y_true_90d = torch.tensor([[12.5], [13.5], [11.5], [10.5]])

    # Zero rainfall in lookback window (feature index 1 is 0.0)
    x_batch = torch.zeros(batch_size, 8, 6)

    loss, metrics = loss_fn(y_pred_60d, y_pred_90d, y_true_60d, y_true_90d, x_batch)

    # Physics violation must be detected (since water was predicted to rise during dry spell)
    assert metrics["loss_physics"] > 0.0
    assert metrics["loss_total"] > metrics["loss_data"]

    # Verify gradients flow back through predictions
    loss.backward()
    assert y_pred_60d.grad is not None
    assert y_pred_90d.grad is not None


def test_trainer_single_epoch():
    model = MARVILSTM(input_dim=6, hidden_dim=16, num_layers=1)
    trainer = LSTMTrainer(model=model, lr=0.01)

    # Create dummy dataset of 16 sequences
    X = torch.randn(16, 8, 6)
    y60 = torch.rand(16, 1)
    y90 = torch.rand(16, 1)

    dataset = TensorDataset(X, y60, y90)
    loader = DataLoader(dataset, batch_size=4)

    metrics = trainer.train_epoch(loader)
    assert "loss_total" in metrics
    assert metrics["loss_total"] > 0.0
    assert not np.isnan(metrics["loss_total"])
