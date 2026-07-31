from __future__ import annotations

import numpy as np
import pytest

from services.nilm.disaggregate import disaggregate, dr_baseline_kw, model_status


def test_invalid_artifact_is_not_deployable() -> None:
    status = model_status()
    assert status.ready is False
    assert "ac_1" in " ".join(status.reasons)
    assert "ac_2" in " ".join(status.reasons)


def test_invalid_artifact_cannot_run_inference() -> None:
    with pytest.raises(RuntimeError, match="NILM is unavailable"):
        disaggregate(np.ones(700, dtype=float))


def test_daily_profile_baseline_uses_comparable_interval() -> None:
    history = np.array(
        [
            [1.0, 2.0, 3.0],
            [2.0, 3.0, 4.0],
            [3.0, 4.0, 5.0],
            [4.0, 5.0, 6.0],
            [5.0, 6.0, 7.0],
        ]
    )
    assert dr_baseline_kw(history, 1) == pytest.approx(4.5)
