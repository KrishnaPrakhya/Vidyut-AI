from __future__ import annotations

import numpy as np

STREAMS = ("topology", "population", "profiles", "weather", "controller", "forecast_noise")


def make_rngs(seed: int) -> dict[str, np.random.Generator]:
    seq = np.random.SeedSequence(seed)
    children = seq.spawn(len(STREAMS))
    return {name: np.random.default_rng(child) for name, child in zip(STREAMS, children)}
