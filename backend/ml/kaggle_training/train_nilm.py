
import hashlib
import json
import math
import os
import random
import re
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

warnings.filterwarnings("ignore")

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.cuda.manual_seed_all(SEED)
torch.backends.cudnn.deterministic = True

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
WORKING = Path("/kaggle/working")

RESAMPLE = "1min"
WINDOW = 99
HALF = WINDOW // 2
BATCH_SIZE = 512
EPOCHS = 30
PATIENCE = 5
LEARNING_RATE = 1e-3
VAL_FRACTION = 0.15
TEST_FRACTION = 0.15

print("device:", DEVICE)
if DEVICE.type == "cpu":
    print("WARNING: no GPU. Enable the accelerator or this will take hours.")


MAINS_CHANNELS = (1, 2)

CHANNELS = {
    3: "fridge",
    4: "ac_1",
    5: "ac_2",
    6: "washing_machine",
    7: "laptop",
    8: "iron",
    9: "kitchen_outlets",
    10: "tv",
    11: "water_filter",
    12: "motor",
}

TARGETS = ["ac_1", "ac_2", "fridge", "tv", "laptop"]

ON_WATTS = {"ac_1": 200.0, "ac_2": 200.0, "fridge": 100.0, "tv": 20.0, "laptop": 15.0}

PLAUSIBLE_PEAK_WATTS = {
    "ac_1": (400, 4000),
    "ac_2": (400, 4000),
    "fridge": (60, 800),
    "tv": (30, 500),
    "laptop": (20, 400),
}

DEFERRABLE = {"ac_1", "ac_2"}

MAINS_CHANNEL_HINTS = ("mains", "aggregate", "total")


def extract_archives() -> Path | None:
    import tarfile

    roots = [Path("/kaggle/input"), Path("data/raw"), Path(".")]
    archives = []
    for root in roots:
        if root.exists():
            archives += [
                p for p in root.rglob("*.tar.gz") if "electricity" in p.name.lower()
            ]
    if not archives:
        return None

    destination = WORKING / "iawe"
    if destination.exists() and list(destination.rglob("*.csv")):
        print("archive already extracted at", destination)
        return destination

    destination.mkdir(parents=True, exist_ok=True)
    archive = archives[0]
    print(f"extracting {archive.name} ({archive.stat().st_size / 1e6:.0f} MB), this takes a minute")
    with tarfile.open(archive) as bundle:
        bundle.extractall(destination)

    extracted = list(destination.rglob("*.csv"))
    print(f"extracted {len(extracted)} CSV files")
    return destination


def find_electricity_dir() -> Path:
    roots = [Path("/kaggle/input"), Path("data/raw"), Path(".")]

    unpacked = extract_archives()
    if unpacked is not None:
        roots.insert(0, unpacked)

    for root in roots:
        if not root.exists():
            continue
        for candidate in root.rglob("*"):
            if candidate.is_dir() and candidate.name.lower() == "electricity":
                if list(candidate.glob("*.csv")):
                    return candidate
    for root in roots:
        if root.exists() and list(root.rglob("*.csv")):
            return sorted(p.parent for p in root.rglob("*.csv"))[0]

    raise FileNotFoundError(
        "no iAWE CSVs found. Attach electricity.tar.gz from https://iawe.github.io "
        "as a Kaggle dataset; pre-extraction is unnecessary."
    )


ELECTRICITY = find_electricity_dir()
csv_files = sorted(ELECTRICITY.glob("*.csv"))
print("reading from", ELECTRICITY)
print("files:", [p.name for p in csv_files])
assert csv_files, "no CSV files found"


def read_channel(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    columns = {c.lower().strip(): c for c in frame.columns}

    time_column = next(
        (columns[c] for c in ("timestamp", "time", "unix", "datetime") if c in columns),
        frame.columns[0],
    )
    power_column = next(
        (columns[c] for c in ("w", "power", "active_power", "p") if c in columns), None
    )
    if power_column is None:
        numeric = [c for c in frame.columns if c != time_column and frame[c].dtype != object]
        assert numeric, f"{path.name}: no numeric power column found in {list(frame.columns)}"
        power_column = numeric[0]

    stamps = frame[time_column]
    if np.issubdtype(stamps.dtype, np.number):
        index = pd.to_datetime(stamps, unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
    else:
        index = pd.to_datetime(stamps, utc=True, errors="coerce").dt.tz_convert("Asia/Kolkata")

    series = pd.Series(
        pd.to_numeric(frame[power_column], errors="coerce").to_numpy(), index=index
    )
    series = series[~series.index.isna()]
    series = series[~series.index.duplicated()].sort_index()
    return series.resample(RESAMPLE).mean()


channels: dict[str, pd.Series] = {}
mains_parts: list[pd.Series] = []

for path in csv_files:
    stem = path.stem.lower()
    series = read_channel(path)
    if series.empty:
        print(f"  {path.name}: empty, skipped")
        continue

    digits = re.findall(r"\d+", stem)
    number = int(digits[0]) if digits else None

    if any(hint in stem for hint in MAINS_CHANNEL_HINTS) or number in MAINS_CHANNELS:
        mains_parts.append(series)
        print(f"  {path.name}: mains phase, {len(series):,} minutes, max {series.max():.0f} W")
        continue

    name = CHANNELS.get(number)
    if name is None:
        print(f"  {path.name}: unmapped channel {number}, skipped")
        continue
    channels[name] = series
    print(f"  {path.name}: {name}, {len(series):,} minutes, max {series.max():.0f} W")

missing = [t for t in TARGETS if t not in channels]
assert not missing, f"target appliances not found: {missing}. Check CHANNELS against the README."


suspicious = []
for appliance, (low, high) in PLAUSIBLE_PEAK_WATTS.items():
    if appliance not in channels:
        continue
    peak = float(channels[appliance].max())
    verdict = "ok" if low <= peak <= high else "IMPLAUSIBLE"
    print(f"  {appliance:<10} peak {peak:>7.0f} W   expected {low}-{high} W   {verdict}")
    if not (low <= peak <= high):
        suspicious.append(f"{appliance} peaks at {peak:.0f} W, expected {low}-{high} W")

assert not suspicious, (
    "channel mapping looks wrong:\n  " + "\n  ".join(suspicious)
    + "\nCorrect CHANNELS at the top of this notebook before training."
)
print("\npeak power is consistent with the labels")


if mains_parts:
    mains = pd.concat(mains_parts, axis=1).sum(axis=1, min_count=1)
    aggregate_source = "metered_mains"
else:
    mains = pd.concat(list(channels.values()), axis=1).sum(axis=1, min_count=1)
    aggregate_source = "reconstructed_from_submeters"

print("aggregate source:", aggregate_source)

frame = pd.concat(
    [mains.rename("mains")] + [channels[t].rename(t) for t in TARGETS], axis=1
).sort_index()

full_index = pd.date_range(frame.index.min(), frame.index.max(), freq=RESAMPLE)
frame = frame.reindex(full_index)

observed = frame.notna()
frame = frame.clip(lower=0.0)

print(f"grid: {len(frame):,} minutes, {frame.index.min()} to {frame.index.max()}")
print(f"observed mains        {observed['mains'].mean() * 100:.1f}%")
for target in TARGETS:
    print(f"observed {target:<16} {observed[target].mean() * 100:.1f}%")


valid_for = {
    appliance: (frame["mains"].notna() & frame[appliance].notna())
    for appliance in TARGETS
}
joint = np.logical_and.reduce([mask.to_numpy() for mask in valid_for.values()])

print("usable minutes, aggregate plus that appliance:")
for appliance, mask in valid_for.items():
    print(f"  {appliance:<10} {mask.mean() * 100:>5.1f}%  ({int(mask.sum()):>7,} minutes)")
print(f"\nall five at once would have been {joint.mean() * 100:.1f}%, which is why masks are per appliance")

usable_targets = [a for a, m in valid_for.items() if int(m.sum()) >= WINDOW * 20]
dropped_targets = [a for a in TARGETS if a not in usable_targets]
if dropped_targets:
    print(f"\ntoo little coverage to train: {dropped_targets}")
assert usable_targets, "no appliance has enough coverage; check the channel mapping"


def contiguous_runs(mask: np.ndarray) -> np.ndarray:
    padded = np.concatenate([[False], mask, [False]])
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return edges[1::2] - edges[::2]


windows_at = {}
for appliance in usable_targets:
    runs = contiguous_runs(valid_for[appliance].to_numpy())
    counts = {c: int(np.sum(np.maximum(runs - c + 1, 0))) for c in (599, 299, 99)}
    windows_at[appliance] = counts
    print(
        f"  {appliance:<10} {len(runs):>5} runs, longest {runs.max():>7,} min   "
        + "   ".join(f"W{c}: {n:>8,}" for c, n in counts.items())
    )

viable = [a for a in usable_targets if windows_at[a][WINDOW] >= 5000]
print(f"\nat WINDOW={WINDOW}, {len(viable)} of {len(usable_targets)} appliances are viable: {viable}")

if len(viable) < len(usable_targets):
    for smaller in (299, 99):
        alternative = [a for a in usable_targets if windows_at[a][smaller] >= 5000]
        if len(alternative) > len(viable):
            print(
                f"  WINDOW={smaller} would cover {len(alternative)}: {alternative}. "
                f"Change WINDOW at the top and re-run from there if you want them."
            )
            break

assert viable, (
    f"no appliance has 5,000 windows at WINDOW={WINDOW}; reduce WINDOW to 299 or 99"
)
TARGETS = viable


n = len(frame)


def splits_for(appliance: str) -> dict[str, slice]:
    positions = np.flatnonzero(valid_for[appliance].to_numpy())
    if positions.size < 3:
        return {"train": slice(0, 0), "val": slice(0, 0), "test": slice(0, 0)}

    train_end = int(positions[int(positions.size * (1 - TEST_FRACTION - VAL_FRACTION))])
    val_end = int(positions[int(positions.size * (1 - TEST_FRACTION))])
    return {
        "train": slice(0, train_end),
        "val": slice(train_end, val_end),
        "test": slice(val_end, n),
    }


splits = {"train": slice(0, int(n * 0.7)), "val": slice(int(n * 0.7), int(n * 0.85)),
          "test": slice(int(n * 0.85), n)}
any_valid = np.logical_or.reduce([m.to_numpy() for m in valid_for.values()])
for name, span in splits.items():
    part = frame.iloc[span]
    print(
        f"{name:<6} {part.index[0].date()} to {part.index[-1].date()}  {len(part):,} minutes, "
        + ", ".join(f"{a} {valid_for[a].iloc[span].mean()*100:.0f}%" for a in TARGETS)
    )

assert frame["mains"].notna().sum() > WINDOW * 10, "not enough usable aggregate data"
print("\nnormalisation statistics use each appliance training slice")
print("per-appliance split boundaries:")
for appliance in TARGETS:
    parts = splits_for(appliance)
    print(
        f"  {appliance:<10} "
        + "  ".join(
            f"{name} {frame.index[span.start].date()}" for name, span in parts.items()
        )
    )


class Seq2PointDataset(Dataset):
    def __init__(self, mains_values, target_values, valid_mask, appliance_mean, appliance_std,
                 mains_mean, mains_std):
        self.mains = mains_values.astype(np.float32)
        self.target = target_values.astype(np.float32)
        self.appliance_mean = appliance_mean
        self.appliance_std = appliance_std
        self.mains_mean = mains_mean
        self.mains_std = mains_std

        usable = valid_mask.astype(np.int32)
        cumulative = np.concatenate([[0], np.cumsum(usable)])
        centres = []
        for centre in range(HALF, len(self.mains) - HALF):
            start, end = centre - HALF, centre + HALF + 1
            if cumulative[end] - cumulative[start] == WINDOW:
                centres.append(centre)
        self.centres = np.array(centres, dtype=np.int64)

    def __len__(self) -> int:
        return len(self.centres)

    def __getitem__(self, index: int):
        centre = self.centres[index]
        window = self.mains[centre - HALF : centre + HALF + 1]
        x = (window - self.mains_mean) / self.mains_std
        y = (self.target[centre] - self.appliance_mean) / self.appliance_std
        return torch.from_numpy(x).unsqueeze(0), torch.tensor(y, dtype=torch.float32)


def build_datasets(appliance: str):
    appliance_splits = splits_for(appliance)
    train_slice = appliance_splits["train"]
    train_mask = valid_for[appliance].iloc[train_slice].to_numpy()
    train_target = frame[appliance].iloc[train_slice].to_numpy()

    appliance_mean = float(train_target[train_mask].mean())
    appliance_std = float(train_target[train_mask].std()) or 1.0

    train_mains = frame["mains"].iloc[train_slice].to_numpy()[train_mask]
    mains_mean = float(train_mains.mean())
    mains_std = float(train_mains.std()) or 1.0

    made = {}
    for name, span in appliance_splits.items():
        made[name] = Seq2PointDataset(
            frame["mains"].iloc[span].to_numpy(),
            frame[appliance].iloc[span].to_numpy(),
            valid_for[appliance].iloc[span].to_numpy(),
            appliance_mean,
            appliance_std,
            mains_mean,
            mains_std,
        )
    return made, appliance_mean, appliance_std, appliance_splits


class Seq2Point(nn.Module):
    def __init__(self, window: int = WINDOW):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv1d(1, 30, 10, padding="same"), nn.ReLU(),
            nn.Conv1d(30, 30, 8, padding="same"), nn.ReLU(),
            nn.Conv1d(30, 40, 6, padding="same"), nn.ReLU(),
            nn.Conv1d(40, 50, 5, padding="same"), nn.ReLU(),
            nn.Dropout(0.2),
            nn.Conv1d(50, 50, 5, padding="same"), nn.ReLU(),
            nn.Dropout(0.2),
        )
        self.head = nn.Sequential(
            nn.Flatten(), nn.Linear(50 * window, 1024), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(1024, 1),
        )

    def forward(self, x):
        return self.head(self.features(x)).squeeze(-1)


def train_appliance(appliance: str) -> dict:
    datasets, appliance_mean, appliance_std, appliance_splits = build_datasets(appliance)
    print(
        f"\n=== {appliance} ===  windows: "
        + "  ".join(f"{k} {len(v):,}" for k, v in datasets.items())
    )
    if len(datasets["train"]) < 100 or len(datasets["test"]) < 50:
        print(f"  too few usable windows, skipping {appliance}")
        return {}

    loaders = {
        name: DataLoader(
            dataset,
            batch_size=BATCH_SIZE,
            shuffle=(name == "train"),
            num_workers=2,
            pin_memory=(DEVICE.type == "cuda"),
            drop_last=(name == "train"),
        )
        for name, dataset in datasets.items()
    }

    model = Seq2Point().to(DEVICE)
    optimiser = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimiser, factor=0.5, patience=2)
    criterion = nn.MSELoss()
    scaler = torch.cuda.amp.GradScaler(enabled=(DEVICE.type == "cuda"))

    best_loss, best_state, stale = math.inf, None, 0
    started = time.time()

    for epoch in range(EPOCHS):
        model.train()
        for x, y in loaders["train"]:
            x, y = x.to(DEVICE, non_blocking=True), y.to(DEVICE, non_blocking=True)
            optimiser.zero_grad(set_to_none=True)
            with torch.cuda.amp.autocast(enabled=(DEVICE.type == "cuda")):
                loss = criterion(model(x), y)
            scaler.scale(loss).backward()
            scaler.step(optimiser)
            scaler.update()

        model.eval()
        losses = []
        with torch.no_grad():
            for x, y in loaders["val"]:
                x, y = x.to(DEVICE), y.to(DEVICE)
                losses.append(criterion(model(x), y).item())
        validation = float(np.mean(losses)) if losses else math.inf
        scheduler.step(validation)

        if validation < best_loss - 1e-5:
            best_loss, stale = validation, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            stale += 1
        print(f"  epoch {epoch + 1:>2}  val {validation:.5f}{'  *' if stale == 0 else ''}")
        if stale >= PATIENCE:
            print(f"  early stop at epoch {epoch + 1}")
            break

    if best_state is not None:
        model.load_state_dict(best_state)

    model.eval()
    predictions, truths = [], []
    with torch.no_grad():
        for x, y in loaders["test"]:
            predictions.append(model(x.to(DEVICE)).cpu().numpy())
            truths.append(y.numpy())

    predicted = np.concatenate(predictions) * appliance_std + appliance_mean
    actual = np.concatenate(truths) * appliance_std + appliance_mean
    predicted = np.clip(predicted, 0.0, None)

    threshold = ON_WATTS[appliance]
    predicted_on = predicted >= threshold
    actual_on = actual >= threshold
    true_positive = int((predicted_on & actual_on).sum())
    false_positive = int((predicted_on & ~actual_on).sum())
    false_negative = int((~predicted_on & actual_on).sum())
    precision = true_positive / max(true_positive + false_positive, 1)
    recall = true_positive / max(true_positive + false_negative, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)

    duty = float(actual_on.mean())
    f1_always_on = 2 * duty / (1 + duty) if duty > 0 else 0.0
    mae_always_mean = float(np.mean(np.abs(actual - actual.mean())))

    result = {
        "MAE": round(float(np.mean(np.abs(predicted - actual))), 3),
        "MAE_predicting_the_mean": round(mae_always_mean, 3),
        "F1": round(float(f1), 4),
        "F1_always_on_baseline": round(f1_always_on, 4),
        "beats_trivial_classifier": bool(f1 > f1_always_on),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "on_threshold_w": threshold,
        "duty_cycle_pct": round(float(actual_on.mean() * 100), 2),
        "mean_power_w": round(float(actual.mean()), 2),
        "test_windows": int(len(actual)),
        "train_windows": len(datasets["train"]),
        "epochs_run": epoch + 1,
        "minutes_trained": round((time.time() - started) / 60, 2),
    }
    verdict = "beats" if result["beats_trivial_classifier"] else "LOSES TO"
    print(
        f"  MAE {result['MAE']:.1f} W (predicting the mean would give "
        f"{result['MAE_predicting_the_mean']:.1f} W)"
    )
    print(
        f"  F1  {result['F1']:.3f} {verdict} the always-on baseline "
        f"{result['F1_always_on_baseline']:.3f}   duty cycle {result['duty_cycle_pct']:.1f}%"
    )

    torch.save(
        {
            "appliance": appliance,
            "state_dict": model.state_dict(),
            "window": WINDOW,
            "mains_mean": datasets["train"].mains_mean,
            "mains_std": datasets["train"].mains_std,
            "appliance_mean": appliance_mean,
            "appliance_std": appliance_std,
            "on_threshold_w": threshold,
        },
        WORKING / f"nilm_{appliance}.pt",
    )
    return result


results = {appliance: train_appliance(appliance) for appliance in TARGETS}
results = {k: v for k, v in results.items() if v}

accepted = {
    appliance: metrics
    for appliance, metrics in results.items()
    if metrics["MAE"] < metrics["MAE_predicting_the_mean"]
    and metrics["F1"] > metrics["F1_always_on_baseline"]
}
rejection_reasons = []
for appliance, metrics in results.items():
    if metrics["MAE"] >= metrics["MAE_predicting_the_mean"]:
        rejection_reasons.append(
            f"{appliance} does not beat the constant-power MAE baseline"
        )
    if metrics["F1"] <= metrics["F1_always_on_baseline"]:
        rejection_reasons.append(
            f"{appliance} does not beat the trivial state-classification baseline"
        )
missing_deferrable = sorted(DEFERRABLE - set(accepted))
if missing_deferrable:
    rejection_reasons.append(
        "validated deferrable models are missing: " + ", ".join(missing_deferrable)
    )
deployment_ready = not rejection_reasons


present_deferrable = [a for a in accepted if a in DEFERRABLE]
if present_deferrable:
    test_start = max(splits_for(appliance)["test"].start for appliance in present_deferrable)
    deferrable_mask = np.logical_and.reduce(
        [valid_for[a].to_numpy() for a in present_deferrable]
        + [frame["mains"].notna().to_numpy()]
    )
    deferrable_mask[:test_start] = False
    measured = frame[deferrable_mask]
    total_mains = float(measured["mains"].sum())
    deferrable_share = (
        float(measured[present_deferrable].sum(axis=1).sum() / total_mains)
        if total_mains > 0
        else 0.0
    )
    print(f"measured over {int(deferrable_mask.sum()):,} minutes where the aggregate and "
          f"{present_deferrable} were all reporting")
else:
    deferrable_share = 0.0
    print("no deferrable appliance survived the coverage filter")
print(f"measured deferrable share of aggregate on held-out data: {deferrable_share * 100:.1f}%")


bundle = {
    appliance: torch.load(WORKING / f"nilm_{appliance}.pt", map_location="cpu")
    for appliance in accepted
}
model_path = WORKING / "nilm_model.pt"
torch.save(bundle, model_path)
with model_path.open("rb") as handle:
    weights_sha256 = hashlib.file_digest(handle, "sha256").hexdigest()


payload = {
    "dataset": "iAWE",
    "resample": RESAMPLE,
    "aggregate_source": aggregate_source,
    "window": WINDOW,
    "appliances": results,
    "accepted_appliances": sorted(accepted),
    "deployment_ready": deployment_ready,
    "weights_sha256": weights_sha256,
    "rejection_reasons": rejection_reasons,
    "deferrable_share_of_aggregate": round(deferrable_share, 4),
    "data_quality": {
        "observed_fraction": {
            column: round(float(observed[column].mean()), 4) for column in observed.columns
        },
        "usable_per_appliance": {a: round(float(valid_for[a].mean()), 4) for a in TARGETS},
        "max_gap_bridged_minutes": 0,
        "gaps_are_masked_not_interpolated": True,
    },
    "split": {
        name: {
            "from": str(frame.iloc[span].index[0]),
            "to": str(frame.iloc[span].index[-1]),
            "minutes": int(len(frame.iloc[span])),
        }
        for name, span in splits.items()
    },
    "role": (
        "observability: estimates the deferrable share of household load and verifies "
        "realised reduction after an event; issues no control commands"
    ),
    "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "seed": SEED,
}

with (WORKING / "nilm_eval.json").open("w") as handle:
    json.dump(payload, handle, indent=2)

print(json.dumps({k: {"MAE": v["MAE"], "F1": v["F1"]} for k, v in results.items()}, indent=2))

print("artifacts in /kaggle/working:")
for path in sorted(WORKING.glob("nilm*")):
    print(f"  {path.name:<28} {path.stat().st_size / 1e6:8.1f} MB")
print("\ncopy nilm_eval.json and nilm_model.pt into backend/ml/models/")
