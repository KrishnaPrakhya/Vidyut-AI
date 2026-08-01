# Demo readiness

Start the database, API, frontend, and activated n8n workflow, then run:

```powershell
backend\.venv\Scripts\python.exe scripts\demo_check.py
```

The check fails fast if the database, authenticated n8n configuration, recorded heatwave, real-data forecast evidence, frontend, simulation, persistence, or PDF report is unavailable. It creates one four-interval normal-day run and never sends email.

During local UI work without n8n, use:

```powershell
backend\.venv\Scripts\python.exe scripts\demo_check.py --core-only
```

For a deployed instance, pass `--api` and `--frontend` with the public origins. Always run the strict form once before presenting.
