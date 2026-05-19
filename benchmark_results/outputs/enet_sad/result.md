# ENet-SAD Result

Date: 2026-05-19

## Setup Attempt

Sources checked:

- Official repo: `https://github.com/cardwing/Codes-for-Lane-Detection`
- PyTorch reimplementation: `https://github.com/InhwanBae/ENet-SAD_Pytorch`
- Paper: `https://arxiv.org/abs/1908.00821`

Local repos:

- `repos/Codes-for-Lane-Detection`
- `repos/ENet-SAD_Pytorch`

Downloaded official pretrained model:

```text
weights/enet_sad/official/ENet-label-new.t7
```

Source ID from official `ENet-Label-Torch/README.md`:

```text
https://drive.google.com/open?id=1pIMThIsGn8z8rIs6WgSNzom1H8WVvP5Q
```

## Status

Blocked for the current Windows/Python `.venv-gpu` benchmark.

Reason:

- The official ENet-SAD implementation is `ENet-Label-Torch`, which uses Torch7/Lua, not PyTorch.
- The official pretrained model is a Torch7 serialized `nn.Sequential` file (`.t7`).
- The PyTorch reimplementation has runnable model code, but does not provide a matching pretrained checkpoint in the repository.
- Running an untrained PyTorch ENet-SAD model would produce meaningless benchmark numbers, so it is intentionally not included in FPS/quality tables.

## Verification

The downloaded model header begins with Torch7 serialized module metadata:

```text
nn.Sequential
```

`torch.load()` in PyTorch cannot load it as a normal PyTorch checkpoint.

## Decision

Do not spend more time forcing ENet-SAD on Windows native for benchmark v2. The clean path is one of:

1. Use an old Torch7/Lua environment to run the official model.
2. Find or train a PyTorch checkpoint for `InhwanBae/ENet-SAD_Pytorch`.
3. Replace ENet-SAD with another lightweight segmentation model that has current PyTorch weights.

For the current TrafficFlow benchmark, ENet-SAD is recorded as blocked with a reproducible reason.
