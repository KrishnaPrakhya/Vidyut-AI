# Forecasting with fine-tuned Chronos-Bolt

This directory contains Vidyut's real-data demand-forecasting experiment. It compares seasonal naive, Chronos-Bolt-small zero-shot, and Chronos-Bolt-small fine-tuned on Indian smart-meter histories, then exports the fitted predictor and held-out forecasts.

The headline result is not a synthetic benchmark: the evaluation artifact declares `real_measurements: true` and `synthetic_training_data: false`.

## Headline result

| Model | Day-ahead MASE | Day-ahead MAPE | Relative to seasonal naive |
| --- | ---: | ---: | ---: |
| Seasonal naive | 1.0635 | 60.5636% | Baseline |
| Chronos-Bolt-small zero-shot | 0.8748 | 45.7893% | 17.7% better MASE |
| **Chronos-Bolt-small fine-tuned** | **0.8579** | **43.2293%** | **19.3% better MASE** |

Lower MASE is better. Here MASE is mean absolute error divided by the in-sample seasonal-naive MAE at a period of 96 intervals.

### Horizon-specific results

| Horizon | Seasonal naive MASE | Fine-tuned Chronos MASE | Improvement |
| --- | ---: | ---: | ---: |
| Next 15 minutes | 0.6823 | 0.2933 | 57.0% |
| Next hour | 0.6958 | 0.3779 | 45.7% |
| Day ahead | 1.0635 | 0.8579 | 19.3% |

### Cold-start result

With only 14 days of history:

| Model | MASE |
| --- | ---: |
| From-scratch recursive tabular model | 0.9322 |
| **Fine-tuned Chronos-Bolt** | **0.8238** |

That is an **11.6% MASE improvement**, relevant to new AMI deployments where years of history are unavailable.

## Data

- **Source:** CEEW high-frequency smart-meter measurements from Mathura and Bareilly, Uttar Pradesh.
- **Native resolution:** 3 minutes.
- **Model resolution:** 15 minutes, produced only by downsampling and averaging.
- **Training rows:** 1,285,204.
- **Evaluation series:** 192.
- **Scales:** 5 transformer aggregates, 18 household clusters, and 169 individual homes.
- **Holdout:** the final 96 intervals—one full day—for every eligible series.

Preparation performed by the training script:

1. detect cumulative energy registers and difference them;
2. remove negative and non-finite measurements;
3. bridge gaps up to four intervals while leaving longer outages missing;
4. remove meters below 60% common-window coverage;
5. form disjoint household groups for aggregate-scale evaluation; and
6. scale partial aggregate sums only when at least 70% of group members report.

No individual reading is fabricated, and no household contributes to more than one group at the same aggregation scale.

## Fine-tuning configuration

| Parameter | Value |
| --- | --- |
| Base model | `chronos-bolt-small` |
| Framework | AutoGluon TimeSeries |
| Prediction length | 96 intervals |
| Frequency | 15 minutes |
| Seasonal period | 96 |
| Fine-tuning steps | 2,000 |
| Learning rate | `1e-5` |
| Random seed | 42 |
| Ensemble | Disabled |
| Recorded fit time | 8.24 minutes |

The pipeline asserts that both zero-shot and fine-tuned Chronos models survived AutoGluon's fit process. This prevents AutoGluon's per-model exception handling from silently turning a failed fine-tune into an apparently successful experiment.

## Files

| File | Purpose |
| --- | --- |
| `kaggle_training/train_forecast.py` | Complete data preparation, fine-tuning, evaluation, assertions, and export pipeline |
| `kaggle_training/train_forecast.ipynb` | Notebook representation of the same experiment |
| `kaggle_training/to_notebook.py` | Generates the notebook from the script |
| `models/forecast_eval.json` | Canonical metrics, data provenance, cohorts, cleaning rules, and configuration |
| `models/forecasts.parquet` | Fine-tuned held-out forecast output |
| `models/forecast_predictor.zip` | Fitted AutoGluon predictor including the fine-tuned Chronos model |
| `export_forecast_data.py` | Exports simulation demand data for separate analysis; it is not used as real training evidence |

## Reproduce the experiment

The training job targets a Kaggle GPU notebook because AutoGluon, Transformers, Accelerate, and PyTorch are intentionally excluded from the lightweight API image.

1. Attach the CEEW Mathura/Bareilly smart-meter dataset to a Kaggle notebook.
2. Upload or open `kaggle_training/train_forecast.ipynb`.
3. Run the dependency cell once; the kernel restart is expected.
4. Run the remaining cells.
5. Download `forecast_eval.json`, `forecasts.parquet`, and `forecast_predictor.zip` from `/kaggle/working`.
6. Replace the corresponding files under `backend/ml/models/` only after reviewing the assertions and metrics.

The script also contains a Harvard Dataverse fallback for the CEEW DOI when the Kaggle dataset is not attached.

## Inspect through the application

With the API running:

```bash
curl http://localhost:8000/api/models
```

Or from the repository root:

```bash
make models
```

The frontend Assurance & Models workspace reads this registry; it does not hardcode the headline metrics.

## Runtime status—important

The trained predictor is **not loaded inside the live simulation loop**. The registry deliberately returns:

```json
{
  "trained": true,
  "evaluation_only": true,
  "runtime_ready": false
}
```

Every simulation tick reports `model: "damped_trend"`, matching the forecaster actually used by the controller. This keeps the API image small and inference latency predictable while preserving an honest boundary between forecasting research and runtime behavior.

## Limitations

- The transformer-scale slice contains five aggregate series; broader feeder diversity is future work.
- Day-ahead MAPE is high because residential load includes low-demand intervals; MASE is the primary comparison metric.
- The evaluation is offline and held out by final day, not a live field deployment.
- The fitted archive is large and requires dependencies not installed in the runtime API image.
- Improving a forecast metric does not automatically prove better end-to-end control; controller impact must be evaluated separately under identical scenarios.

These limits are included in the artifact and the API so evaluators can distinguish what was measured from what remains to be integrated.
