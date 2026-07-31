
import os
import subprocess
import sys

subprocess.run(
    [sys.executable, "-m", "pip", "install", "-q",
     "autogluon.timeseries==1.2.0",
     "transformers==4.44.2", "accelerate==0.33.0",
     "numpy==1.26.4", "pandas==2.2.2"],
    check=True,
)
print("installed — restarting the kernel, this is expected")
print("after the restart, run from the NEXT cell onward and skip this one")
os.kill(os.getpid(), 9)


import accelerate
import torch
import transformers
from transformers import PreTrainedModel
from transformers.integrations.integration_utils import get_reporting_integration_callbacks

print("transformers", transformers.__version__, "| accelerate", accelerate.__version__)
print("cuda", torch.cuda.is_available(),
      torch.cuda.get_device_name(0) if torch.cuda.is_available() else "")
print("Chronos imports resolve; the fine-tune will not be silently skipped")

import json
import re
import shutil
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch

warnings.filterwarnings("ignore")

SEED = 42
np.random.seed(SEED)
torch.manual_seed(SEED)

PREDICTION_LENGTH = 96
FREQ = "15min"
SEASONAL_PERIOD = 96
HORIZON_SLICES = {"next_15min": 1, "next_hour": 4, "day_ahead": 96}
COLD_START_DAYS = 14

FINE_TUNE_LR = 1e-5
FINE_TUNE_STEPS = 2000

HOUSEHOLDS_PER_GROUP = 70
MIN_DAYS_PER_SERIES = 60
MAX_GAP_BRIDGE = 4
INPUT_ROOT = Path("/kaggle/input")
WORKING = Path("/kaggle/working")
MODEL_DIR = WORKING / "predictor"

print("torch", torch.__version__, "| cuda", torch.cuda.is_available())
print("device:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU")
print("numpy", np.__version__, "| pandas", pd.__version__)


TIME_HINTS = ("x_timestamp", "timestamp", "time", "datetime", "date")
ENERGY_HINTS = ("t_kwh", "kwh", "energy", "consumption")
POWER_HINTS = ("kw", "w", "power", "load")
ID_HINTS = ("meter", "meter_id", "id", "household", "consumer", "device")


def pick(columns: dict[str, str], hints: tuple[str, ...]) -> str | None:
    for hint in hints:
        if hint in columns:
            return columns[hint]
    for key, original in columns.items():
        if any(hint in key for hint in hints):
            return original
    return None


MONOTONIC_FRACTION = 0.98
IMPLAUSIBLE_KW = 5_000.0


def is_cumulative(values: np.ndarray) -> bool:
    finite = values[np.isfinite(values)]
    if finite.size < 50:
        return False
    steps = np.diff(finite)
    if steps.size == 0:
        return False
    return float((steps >= -1e-9).mean()) > MONOTONIC_FRACTION


def to_kw(series: pd.Series, minutes: float) -> pd.Series:
    if is_cumulative(series.to_numpy(dtype=float)):
        series = series.diff()
        series[series < 0] = np.nan
    converted = series * (60.0 / minutes)

    median = float(np.nanmedian(converted.to_numpy(dtype=float)))
    if np.isfinite(median) and median > IMPLAUSIBLE_KW:
        raise ValueError(
            f"median load of {median:,.0f} kW is not a household meter; "
            f"the cumulative-register check has misfired on this series"
        )
    return converted


def median_interval_minutes(index: pd.DatetimeIndex) -> float:
    deltas = pd.Series(index).diff().dropna().dt.total_seconds() / 60.0
    positive = deltas[deltas > 0]
    return float(positive.median()) if len(positive) else 3.0


def read_meter_frame(path: Path) -> pd.DataFrame | None:
    try:
        frame = pd.read_csv(path, low_memory=False)
    except Exception:
        return None
    if frame.empty:
        return None

    columns = {str(c).lower().strip(): c for c in frame.columns}
    time_column = pick(columns, TIME_HINTS)
    if time_column is None:
        return None

    energy_column = pick(columns, ENERGY_HINTS)
    power_column = None if energy_column else pick(columns, POWER_HINTS)
    if energy_column is None and power_column is None:
        return None

    id_column = pick(columns, ID_HINTS)
    if id_column in (time_column, energy_column, power_column):
        id_column = None

    stamps = pd.to_datetime(frame[time_column], errors="coerce")
    if stamps.isna().mean() > 0.5:
        stamps = pd.to_datetime(frame[time_column], errors="coerce", unit="s")
    frame = frame.assign(_ts=stamps).dropna(subset=["_ts"])
    if frame.empty:
        return None

    value_column = energy_column or power_column
    frame["_value"] = pd.to_numeric(frame[value_column], errors="coerce")
    frame["_meter"] = frame[id_column].astype(str) if id_column else path.stem
    frame["_is_energy"] = energy_column is not None
    return frame[["_ts", "_value", "_meter", "_is_energy"]]


def series_from_group(group: pd.DataFrame) -> pd.Series | None:
    series = group.set_index("_ts")["_value"].sort_index().dropna()
    series = series[~series.index.duplicated()]
    if len(series) < 500:
        return None
    minutes = median_interval_minutes(series.index)
    kw = to_kw(series, minutes) if bool(group["_is_energy"].iloc[0]) else series
    resampled = kw.resample(FREQ).mean().dropna()
    resampled = resampled[(resampled >= 0) & np.isfinite(resampled)]
    return resampled if len(resampled) else None


def load_ceew() -> dict[str, pd.Series]:
    candidates = []
    for root in (INPUT_ROOT, Path("data/raw"), Path(".")):
        if root.exists():
            candidates += [
                p for p in root.rglob("*.csv")
                if any(k in str(p).lower() for k in ("mathura", "bareilly", "ceew", "smart"))
            ]
    if not candidates and INPUT_ROOT.exists():
        candidates = list(INPUT_ROOT.rglob("*.csv"))

    print(f"scanning {len(candidates)} candidate CSV files")
    meters: dict[str, pd.Series] = {}

    for path in candidates:
        frame = read_meter_frame(path)
        if frame is None:
            continue
        for meter, group in frame.groupby("_meter"):
            resampled = series_from_group(group)
            if resampled is None or len(resampled) < MIN_DAYS_PER_SERIES * 96 // 2:
                continue
            key = f"{path.stem}:{meter}" if str(meter) != path.stem else str(meter)
            meters[key] = resampled

    return meters


CEEW_DOI = "doi:10.7910/DVN/GOCHJH"
CEEW_DATAVERSE = (
    "https://dataverse.harvard.edu/api/access/dataset/:persistentId/?persistentId=" + CEEW_DOI
)


def fetch_ceew_from_dataverse() -> bool:
    import zipfile
    from urllib.request import urlretrieve

    archive = WORKING / "ceew.zip"
    target = WORKING / "ceew"
    try:
        if not archive.exists():
            print(f"attempting Harvard Dataverse download of {CEEW_DOI}")
            print("this can be several GB and is slower than attaching the Kaggle dataset")
            urlretrieve(CEEW_DATAVERSE, archive)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(target)
        print("extracted to", target)
        return True
    except Exception as exc:
        print(f"Dataverse download failed: {exc}")
        return False


ceew = load_ceew()

if not ceew and fetch_ceew_from_dataverse():
    INPUT_ROOT_FALLBACK = WORKING / "ceew"
    candidates = list(INPUT_ROOT_FALLBACK.rglob("*.csv"))
    print(f"rescanning {len(candidates)} extracted files")
    for path in candidates:
        frame = read_meter_frame(path)
        if frame is None:
            continue
        for meter, group in frame.groupby("_meter"):
            resampled = series_from_group(group)
            if resampled is not None and len(resampled) >= MIN_DAYS_PER_SERIES * 96 // 2:
                ceew[f"{path.stem}:{meter}"] = resampled

print(f"\nCEEW meters loaded before deduplication: {len(ceew)}")
assert ceew, (
    "no CEEW meters found and the Dataverse fallback did not work.\n"
    "Attach a Kaggle dataset such as:\n"
    "  jehanbhathena/smart-meter-data-mathura-and-bareilly\n"
    "  pythonafroz/electricity-smart-meter-data-from-india"
)


def fingerprint(series: pd.Series) -> tuple:
    values = series.to_numpy(dtype=float)
    return (
        len(values),
        round(float(np.mean(values)), 6),
        round(float(np.std(values)), 6),
        round(float(values[:64].sum()), 6),
    )


seen: dict[tuple, str] = {}
deduplicated: dict[str, pd.Series] = {}
for name, series in ceew.items():
    key = fingerprint(series)
    if key in seen:
        continue
    seen[key] = name
    deduplicated[name] = series

removed = len(ceew) - len(deduplicated)
if removed:
    print(
        f"removed {removed} duplicate series; the same meters appear in more than one attached "
        f"mirror, and counting them twice would break the disjoint-group guarantee"
    )
ceew = deduplicated
print(f"CEEW meters after deduplication: {len(ceew)}")

sample = next(iter(ceew.values()))
print(f"example series: {len(sample):,} points, {sample.index.min()} to {sample.index.max()}")
print(f"mean {sample.mean():.3f} kW, max {sample.max():.2f} kW")


spans = {name: (s.index.min(), s.index.max()) for name, s in ceew.items()}
overall_start = min(a for a, _ in spans.values())
overall_end = max(b for _, b in spans.values())
print(f"meters span {overall_start.date()} to {overall_end.date()} in total")

naive_start = max(a for a, _ in spans.values())
naive_end = min(b for _, b in spans.values())
if naive_start >= naive_end:
    print(
        "no window is shared by every meter, so the meters are grouped into overlapping "
        "cohorts instead of forcing one global window"
    )


def members_covering(candidates: dict, start, end, fraction: float = 0.9) -> list[str]:
    required = (end - start) * fraction
    return [
        name
        for name in candidates
        if spans[name][0] <= start + (end - start) * (1 - fraction)
        and spans[name][1] >= start + required
    ]


def densest_window(candidates: dict, min_days: int) -> tuple:
    boundaries = sorted({a for name in candidates for a in (spans[name][0],)})
    closings = sorted({b for name in candidates for b in (spans[name][1],)})

    best = (None, None, [])
    best_score = 0.0
    for start in boundaries:
        for end in closings:
            days = (end - start).days
            if days < min_days:
                continue
            members = members_covering(candidates, start, end)
            score = len(members) * days
            if len(members) >= 2 and score > best_score:
                best_score = score
                best = (start, end, members)
    return best


cohorts = []
remaining = dict(ceew)
while len(remaining) >= 2:
    start, end, members = densest_window(remaining, MIN_DAYS_PER_SERIES)
    if start is None or len(members) < 2:
        break
    cohorts.append((start, end, members))
    for name in members:
        remaining.pop(name, None)

print(f"\ncohorts found: {len(cohorts)}")
for index, (start, end, members) in enumerate(cohorts):
    print(f"  cohort {index}: {len(members):>3} meters, {start.date()} to {end.date()} "
          f"({(end - start).days} days)")

assert cohorts, "no cohort of overlapping meters could be formed"

prepared = []
for cohort_index, (start, end, members) in enumerate(cohorts):
    grid = pd.date_range(start, end, freq=FREQ)
    aligned = pd.DataFrame(
        {name: ceew[name].reindex(grid) for name in members}
    ).ffill(limit=MAX_GAP_BRIDGE)
    coverage = aligned.notna().mean()
    aligned = aligned.loc[:, coverage >= 0.6]
    if aligned.shape[1] >= 2:
        prepared.append(aligned)
        print(f"cohort {cohort_index}: {aligned.shape[1]} meters pass the coverage filter")

assert prepared, "no cohort survived the coverage filter"


MIN_AGGREGATE_GROUPS = 4
SIZE_CANDIDATES = [70, 60, 50, 40, 30, 25, 20, 15, 10]

available = sorted((frame.shape[1] for frame in prepared), reverse=True)
print("meters available per cohort:", available)

group_size = None
for candidate in SIZE_CANDIDATES:
    possible = sum(count // candidate for count in available)
    if possible >= MIN_AGGREGATE_GROUPS:
        group_size = candidate
        break

if group_size is None:
    group_size = max(min(available[0], 10), 2)
    print(f"data is thin; falling back to groups of {group_size}")
else:
    total = sum(count // group_size for count in available)
    print(
        f"aggregating at {group_size} households per group, giving {total} independent groups "
        f"(target was {HOUSEHOLDS_PER_GROUP}, not reachable with these cohorts)"
    )

cluster_size = max(group_size // 3, 5)

MIN_MEMBER_PRESENCE = 0.70

frames = []
min_points = MIN_DAYS_PER_SERIES * 96
group_count = 0
cluster_count = 0
home_count = 0
scale_factors = []

for aligned in prepared:
    names = sorted(aligned.columns)

    def add_group(group_members: list[str], item_id: str) -> bool:
        block = aligned[group_members]
        present = block.notna().sum(axis=1)
        usable = present >= max(len(group_members) * MIN_MEMBER_PRESENCE, 1)
        if not usable.any():
            return False

        partial = block.sum(axis=1, min_count=1)[usable]
        correction = len(group_members) / present[usable]
        total = (partial * correction).dropna()
        if len(total) < min_points:
            return False

        scale_factors.append(float(correction.mean()))
        frames.append(
            pd.DataFrame(
                {"item_id": item_id, "timestamp": total.index, "target": total.to_numpy()}
            )
        )
        return True

    for name in names:
        series = aligned[name].dropna()
        if len(series) >= min_points:
            frames.append(
                pd.DataFrame(
                    {"item_id": f"CEEW_home_{home_count:03d}", "timestamp": series.index,
                     "target": series.to_numpy()}
                )
            )
            home_count += 1

    for start_index in range(0, len(names) - group_size + 1, group_size):
        if add_group(names[start_index : start_index + group_size],
                     f"CEEW_transformer_{group_count:02d}"):
            group_count += 1

    for start_index in range(0, len(names) - cluster_size + 1, cluster_size):
        if add_group(names[start_index : start_index + cluster_size],
                     f"CEEW_cluster_{cluster_count:02d}"):
            cluster_count += 1

assert frames, "no series survived aggregation"
real = pd.concat(frames, ignore_index=True)
print(f"\nCEEW series built: {real.item_id.nunique()}")
print(f"  aggregate groups of {group_size}: {group_count}")
print(f"  clusters of {cluster_size}: {cluster_count}")
print(f"  individual homes: {home_count}")
assert group_count > 0, "no aggregate group was formed; lower MIN_AGGREGATE_GROUPS"

aggregate_peak = real[real.item_id.str.contains("transformer")].groupby("item_id").target.max()
print(f"\naggregate group peak load: {aggregate_peak.min():.1f} to {aggregate_peak.max():.1f} kW")

mean_correction = float(np.mean(scale_factors)) if scale_factors else 1.0
print(
    f"mean scaling applied to aggregates: {mean_correction:.3f}x "
    f"(1.000 would mean every member always reported)"
)
assert mean_correction < 1.45, (
    f"aggregates were scaled by {mean_correction:.2f}x on average, so too much of each group "
    f"is estimated rather than measured; raise MIN_MEMBER_PRESENCE"
)


def load_generic(keywords: tuple[str, ...], prefix: str, divide_by: float = 1.0) -> list[pd.DataFrame]:
    if not INPUT_ROOT.exists():
        return []
    paths = [p for p in INPUT_ROOT.rglob("*.csv") if any(k in str(p).lower() for k in keywords)]
    collected = []
    for path in paths:
        frame = read_meter_frame(path)
        if frame is None:
            continue
        for meter, group in frame.groupby("_meter"):
            resampled = series_from_group(group)
            if resampled is None or len(resampled) < min_points:
                continue
            if not bool(group["_is_energy"].iloc[0]) and divide_by != 1.0:
                resampled = resampled / divide_by
            label = re.sub(r"[^A-Za-z0-9]+", "_", str(meter))[:24]
            collected.append(
                pd.DataFrame(
                    {"item_id": f"{prefix}_{label}", "timestamp": resampled.index,
                     "target": resampled.to_numpy()}
                )
            )
    return collected


iblend = load_generic(("iblend", "i-blend", "blend"), "IBLEND")
iawe = load_generic(("iawe",), "IAWE", divide_by=1000.0)

for name, extra in (("I-BLEND", iblend), ("iAWE", iawe)):
    if extra:
        print(f"{name}: {len(extra)} series added")
        real = pd.concat([real] + extra, ignore_index=True)
    else:
        print(f"{name}: not attached")

real = real.sort_values(["item_id", "timestamp"]).reset_index(drop=True)
print(f"\ntotal series {real.item_id.nunique()}, rows {len(real):,}")


MIN_TOTAL_POINTS = PREDICTION_LENGTH * 5


def longest_regular_run(group: pd.DataFrame, item_id: str) -> pd.DataFrame | None:
    series = group.set_index("timestamp")["target"].sort_index()
    grid = pd.date_range(series.index.min(), series.index.max(), freq=FREQ)
    series = series.reindex(grid)

    present = series.notna().to_numpy()
    if not present.any():
        return None

    padded = np.concatenate([[False], present, [False]])
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    starts, ends = edges[::2], edges[1::2]
    if not len(starts):
        return None

    best = int(np.argmax(ends - starts))
    run = series.iloc[starts[best] : ends[best]]
    if len(run) < MIN_TOTAL_POINTS:
        return None

    return pd.DataFrame(
        {"item_id": item_id, "timestamp": run.index, "target": run.to_numpy()}
    )


kept = []
for item_id, group in real.groupby("item_id"):
    trimmed = longest_regular_run(group, item_id)
    if trimmed is not None:
        kept.append(trimmed)

assert kept, "no series had an unbroken stretch long enough to train on"
before_rows, before_series = len(real), real.item_id.nunique()
real = (
    pd.concat(kept, ignore_index=True)
    .sort_values(["item_id", "timestamp"])
    .reset_index(drop=True)
)

print(f"series {before_series} -> {real.item_id.nunique()} after trimming to unbroken runs")
print(f"rows   {before_rows:,} -> {len(real):,} "
      f"({len(real) / before_rows * 100:.0f}% retained)")


ROW_BUDGET = 2_500_000

lengths = real.groupby("item_id").size().sort_values(ascending=False)
aggregates = [i for i in lengths.index if "transformer" in i or "cluster" in i]
homes = [i for i in lengths.index if "home" in i]

aggregate_rows = int(lengths[aggregates].sum())
print(f"aggregate series: {len(aggregates)} using {aggregate_rows:,} rows, always kept in full")

selected = list(aggregates)
running = aggregate_rows
for name in homes:
    if running + lengths[name] > ROW_BUDGET:
        continue
    selected.append(name)
    running += int(lengths[name])

dropped = len(homes) - (len(selected) - len(aggregates))
if dropped:
    print(
        f"kept {len(selected) - len(aggregates)} of {len(homes)} household series at full "
        f"history; dropped {dropped} to stay inside the row budget"
    )

before = len(real)
real = real[real.item_id.isin(selected)].reset_index(drop=True)

span = real.groupby("item_id").timestamp.agg(["min", "max"])
memory_mb = real.memory_usage(deep=True).sum() / 1e6
print(f"\nfinal dataset: {real.item_id.nunique()} series, {len(real):,} rows, {memory_mb:.0f} MB")
print(f"calendar coverage preserved: {span['min'].min().date()} to {span['max'].max().date()}")
print(f"longest series: {int(lengths[selected].max()) // 96} days")

assert len(real) < 3_000_000, (
    f"{len(real):,} rows risks exhausting Kaggle memory during fitting; lower ROW_BUDGET"
)

assert not real.duplicated(["item_id", "timestamp"]).any(), "duplicate timestamps"
assert real.target.notna().all(), "nulls remain"
assert (real.target >= 0).all(), "negative load"
assert np.isfinite(real.target).all(), "non-finite load"

gaps = real.groupby("item_id").timestamp.diff().dropna().unique()
assert len(gaps) == 1 and gaps[0] == pd.Timedelta(FREQ), f"irregular spacing remains: {gaps}"
print(f"every series is now on an unbroken {FREQ} grid")

position_from_end = real.groupby("item_id").cumcount(ascending=False)
train_raw = real[position_from_end >= PREDICTION_LENGTH].copy()
test_target = real[position_from_end < PREDICTION_LENGTH].copy()

assert (test_target.groupby("item_id").size() == PREDICTION_LENGTH).all(), "ragged holdout"
print(f"\ntrain {len(train_raw):,} rows across {train_raw.item_id.nunique()} series")
print(f"holdout {len(test_target):,} rows, {PREDICTION_LENGTH} steps per series")
print(f"span {train_raw.timestamp.min()} to {test_target.timestamp.max()}")

from autogluon.timeseries import TimeSeriesDataFrame, TimeSeriesPredictor

def to_ts(frame: pd.DataFrame) -> TimeSeriesDataFrame:
    return TimeSeriesDataFrame.from_data_frame(
        frame, id_column="item_id", timestamp_column="timestamp"
    )


train_data = to_ts(train_raw)
truth = to_ts(test_target)

cold_cut = train_raw.groupby("item_id").timestamp.transform("max") - pd.Timedelta(
    days=COLD_START_DAYS
)
cold_slice = train_raw[train_raw.timestamp >= cold_cut].copy()

cold_counts = cold_slice.groupby("item_id").size()
too_short = cold_counts[cold_counts < PREDICTION_LENGTH * 2].index
if len(too_short):
    print(
        f"dropping {len(too_short)} series from the cold-start experiment; a model cannot be "
        f"fitted and validated on fewer than {PREDICTION_LENGTH * 2} points"
    )
    cold_slice = cold_slice[~cold_slice.item_id.isin(too_short)]

assert not cold_slice.empty, "no series has enough history for the cold-start experiment"
cold_start_data = to_ts(cold_slice)
print("train", train_data.shape, "| cold start", cold_start_data.shape,
      f"({cold_slice.item_id.nunique()} series)")


MAPE_FLOOR_KW = 0.05
RELATIVE_SCALE_FLOOR = 1e-6


def seasonal_naive_scale(history: pd.Series, period: int = SEASONAL_PERIOD) -> float:
    values = history.to_numpy(dtype=float)
    magnitude = float(np.mean(np.abs(values))) if values.size else 0.0
    floor = max(magnitude * RELATIVE_SCALE_FLOOR, np.finfo(float).eps)

    if values.size > period:
        seasonal = float(np.mean(np.abs(values[period:] - values[:-period])))
        if seasonal > floor:
            return seasonal
    if values.size > 1:
        first_difference = float(np.mean(np.abs(np.diff(values))))
        if first_difference > floor:
            return first_difference
    return max(magnitude, 1.0)


def score(truth_frame, prediction, history, steps: int, prefix: str | None = None) -> dict:
    absolute, scaled, percentage = [], [], []
    excluded = 0
    items = [
        i for i in truth_frame.index.get_level_values(0).unique()
        if prefix is None or str(i).startswith(prefix)
    ]

    misaligned = 0
    for item_id in items:
        if item_id not in prediction.index.get_level_values(0):
            continue
        actual_series = truth_frame.loc[item_id, "target"]
        forecast_series = prediction.loc[item_id, "mean"]

        span = min(len(actual_series), len(forecast_series), steps)
        if not actual_series.index[:span].equals(forecast_series.index[:span]):
            misaligned += 1
            continue

        actual = actual_series.to_numpy(dtype=float)[:span]
        forecast = forecast_series.to_numpy(dtype=float)[:span]

        scale = seasonal_naive_scale(history.loc[item_id, "target"])
        error = np.abs(actual - forecast)
        absolute.append(error)
        scaled.append(error / scale)

        usable = actual > MAPE_FLOOR_KW
        excluded += int((~usable).sum())
        if usable.any():
            percentage.append(error[usable] / actual[usable])

    assert misaligned == 0, (
        f"{misaligned} series had forecast timestamps that did not match the holdout; "
        f"scoring them would compare the wrong points"
    )
    if not scaled:
        return {"MASE": None, "MAPE": None, "MAE_kw": None, "series": 0}

    mape = float(np.mean(np.concatenate(percentage)) * 100) if percentage else None
    return {
        "MASE": round(float(np.mean(np.concatenate(scaled))), 4),
        "MAPE": round(mape, 4) if mape is not None else None,
        "MAE_kw": round(float(np.mean(np.concatenate(absolute))), 4),
        "series": len(items),
        "points_excluded_from_mape": excluded,
    }


def fitted_models(fitted_predictor) -> list[str]:
    for accessor in ("model_names", "get_model_names"):
        method = getattr(fitted_predictor, accessor, None)
        if callable(method):
            return list(method())
    return list(fitted_predictor.leaderboard(silent=True)["model"])


if MODEL_DIR.exists():
    shutil.rmtree(MODEL_DIR)

predictor = TimeSeriesPredictor(
    prediction_length=PREDICTION_LENGTH,
    freq=FREQ,
    eval_metric="MASE",
    eval_metric_seasonal_period=SEASONAL_PERIOD,
    target="target",
    path=str(MODEL_DIR),
    verbosity=2,
)

started = time.time()
predictor.fit(
    train_data,
    hyperparameters={
        "SeasonalNaive": {},
        "Chronos": [
            {"model_path": "bolt_small", "ag_args": {"name_suffix": "ZeroShot"}},
            {
                "model_path": "bolt_small", "fine_tune": True,
                "fine_tune_lr": FINE_TUNE_LR, "fine_tune_steps": FINE_TUNE_STEPS,
                "ag_args": {"name_suffix": "FineTuned"},
            },
        ],
    },
    enable_ensemble=False,
    random_seed=SEED,
)
fit_seconds = time.time() - started
print(f"fit completed in {fit_seconds / 60:.1f} min")

trained = fitted_models(predictor)
print("models that survived training:", trained)
missing = {"ChronosZeroShot", "ChronosFineTuned"} - {
    part for name in trained for part in ("ChronosZeroShot", "ChronosFineTuned") if part in name
}
assert not missing, (
    f"{sorted(missing)} were dropped during fit. AutoGluon catches per-model exceptions and "
    f"carries on, so scroll up for the 'Warning: Exception caused ... to fail' line. A wrong "
    f"transformers version is the usual cause and shows up as an import error."
)

def label_for(name: str) -> str | None:
    if "SeasonalNaive" in name:
        return "seasonal_naive"
    if "FineTuned" in name:
        return "chronos_finetuned"
    if "Chronos" in name:
        return "chronos_zeroshot"
    return None


print("fitted:", fitted_models(predictor))


results, by_scale = {}, {}
for model_name in fitted_models(predictor):
    label = label_for(model_name)
    if label is None:
        continue
    prediction = predictor.predict(train_data, model=model_name)
    results[label] = {
        horizon: score(truth, prediction, train_data, steps)
        for horizon, steps in HORIZON_SLICES.items()
    }
    by_scale[label] = {
        "transformer_scale": score(truth, prediction, train_data, PREDICTION_LENGTH,
                                   prefix="CEEW_transformer"),
        "cluster_scale": score(truth, prediction, train_data, PREDICTION_LENGTH,
                               prefix="CEEW_cluster"),
        "individual_home": score(truth, prediction, train_data, PREDICTION_LENGTH,
                                 prefix="CEEW_home"),
    }
    day = results[label]["day_ahead"]
    print(f"{label:<20} day-ahead MASE {day['MASE']}  MAPE {day['MAPE']}")

assert "chronos_finetuned" in results and "seasonal_naive" in results, fitted_models(predictor)


COLD_DIR = WORKING / "predictor_cold_start"
if COLD_DIR.exists():
    shutil.rmtree(COLD_DIR)

cold_predictor = TimeSeriesPredictor(
    prediction_length=PREDICTION_LENGTH, freq=FREQ, eval_metric="MASE",
    eval_metric_seasonal_period=SEASONAL_PERIOD, target="target",
    path=str(COLD_DIR), verbosity=1,
)
cold_predictor.fit(
    cold_start_data,
    hyperparameters={
        "RecursiveTabular": {},
        "Chronos": [{
            "model_path": "bolt_small", "fine_tune": True,
            "fine_tune_lr": FINE_TUNE_LR, "fine_tune_steps": FINE_TUNE_STEPS,
            "ag_args": {"name_suffix": "FineTuned"},
        }],
    },
    enable_ensemble=False,
    random_seed=SEED,
)

cold_results = {}
for model_name in fitted_models(cold_predictor):
    label = "chronos_finetuned" if "Chronos" in model_name else "lgbm_from_scratch"
    prediction = cold_predictor.predict(cold_start_data, model=model_name)
    cold_results[label] = score(truth, prediction, cold_start_data, PREDICTION_LENGTH)
    print(f"cold start {label:<20} MASE {cold_results[label]['MASE']}")


best = next(n for n in fitted_models(predictor) if label_for(n) == "chronos_finetuned")
predictor.predict(train_data, model=best).reset_index().to_parquet(
    WORKING / "forecasts.parquet", index=False
)
print("wrote forecasts.parquet")


counts_by_kind = {
    kind: int(sum(1 for i in real.item_id.unique() if kind in i))
    for kind in ("CEEW_transformer", "CEEW_cluster", "CEEW_home", "IBLEND", "IAWE")
}

sources = [
    "CEEW high-frequency smart meter data, Mathura and Bareilly, Uttar Pradesh, 3-minute native",
]
if iblend:
    sources.append("I-BLEND, IIIT-Delhi campus buildings, 1-minute native")
if iawe:
    sources.append("iAWE, single Delhi household, 1-minute native")

payload = {
    "holdout": "indian_meters_final_day",
    "models": {
        label: {"MASE": entry["day_ahead"]["MASE"], "MAPE": entry["day_ahead"]["MAPE"]}
        for label, entry in results.items()
    },
    "cold_start": {
        "history_days": COLD_START_DAYS,
        "lgbm_from_scratch": {"MASE": cold_results.get("lgbm_from_scratch", {}).get("MASE")},
        "chronos_finetuned": {"MASE": cold_results.get("chronos_finetuned", {}).get("MASE")},
    },
    "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "n_series": int(train_raw.item_id.nunique()),
    "n_obs": int(len(train_raw)),
    "by_horizon": results,
    "by_scale": by_scale,
    "data": {
        "country": "India",
        "real_measurements": True,
        "synthetic_training_data": False,
        "sources": sources,
        "series_counts": counts_by_kind,
        "households_per_aggregate_group": group_size,
        "households_per_transformer_target": HOUSEHOLDS_PER_GROUP,
        "aggregate_group_note": (
            f"the simulated network serves {HOUSEHOLDS_PER_GROUP} homes per transformer; no "
            f"cohort of real meters had that many recording together for long enough, so "
            f"groups of {group_size} were used"
        ),
        "cohorts": [
            {"meters": int(frame.shape[1]),
             "from": str(frame.index.min()), "to": str(frame.index.max())}
            for frame in prepared
        ],
        "resampling": "downsampled to 15 minutes by averaging; nothing upsampled or interpolated",
        "aggregation": (
            "households pooled into disjoint groups to reconstruct transformer-scale load; "
            "no household contributes to more than one group at a given scale"
        ),
        "aggregate_estimation": {
            "minimum_members_reporting": MIN_MEMBER_PRESENCE,
            "mean_scaling_factor": round(mean_correction, 4),
            "method": (
                "where some meters in a group were not reporting, the partial sum was scaled "
                "by the fraction present, the standard treatment for missing AMI reads; "
                "individual readings were never fabricated"
            ),
        },
        "cleaning": [
            "cumulative meter registers detected and differenced automatically",
            "negative and non-finite readings dropped",
            f"gaps bridged up to {MAX_GAP_BRIDGE} intervals, longer outages left missing",
            "meters with under 60% coverage on the common window dropped",
        ],
    },
    "config": {
        "base_model": "chronos-bolt-small",
        "prediction_length": PREDICTION_LENGTH,
        "freq": FREQ,
        "seasonal_period": SEASONAL_PERIOD,
        "fine_tune_lr": FINE_TUNE_LR,
        "fine_tune_steps": FINE_TUNE_STEPS,
        "seed": SEED,
        "fit_minutes": round(fit_seconds / 60, 2),
        "mase_definition": "MAE divided by in-sample seasonal-naive MAE at period 96",
    },
}

with (WORKING / "forecast_eval.json").open("w") as handle:
    json.dump(payload, handle, indent=2)

print(json.dumps(payload["models"], indent=2))
print(json.dumps(payload["by_scale"].get("chronos_finetuned", {}), indent=2))

naive = results["seasonal_naive"]["day_ahead"]["MASE"]
zero_shot = results.get("chronos_zeroshot", {}).get("day_ahead", {}).get("MASE")
tuned = results["chronos_finetuned"]["day_ahead"]["MASE"]

assert naive and tuned, f"missing headline metrics: naive={naive} tuned={tuned}"

print("evaluated on held-out REAL Indian meter data\n")
print(f"seasonal naive     MASE {naive:.4f}")
if zero_shot:
    print(f"chronos zero-shot  MASE {zero_shot:.4f}  ({(1 - zero_shot / naive) * 100:+.1f}% vs naive)")
print(f"chronos fine-tuned MASE {tuned:.4f}  ({(1 - tuned / naive) * 100:+.1f}% vs naive)")

if zero_shot:
    delta = (1 - tuned / zero_shot) * 100
    print()
    if delta > 1.0:
        print(f"fine-tuning improved on zero-shot by {delta:.1f}%")
    elif delta < -1.0:
        print(f"fine-tuning was {-delta:.1f}% worse than zero-shot; report the zero-shot model")
    else:
        print("fine-tuning made no material difference")

shutil.make_archive(str(WORKING / "forecast_predictor"), "zip", str(MODEL_DIR))
print("\nartifacts in /kaggle/working:")
for path in sorted(WORKING.glob("*")):
    if path.is_file() and path.suffix in (".json", ".parquet", ".zip"):
        print(f"  {path.name:<28} {path.stat().st_size / 1e6:8.1f} MB")
