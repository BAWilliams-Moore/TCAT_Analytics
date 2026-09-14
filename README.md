# Segment Workbench

Flask GUI around the existing Snowflake ODBC workflow: connect once, pick scoring runs, then build pairwise `MODEL_SEGMENT` overlap heatmaps.

The left side menu stays visible on every page (it is not a dropdown). It splits the original single page into three views:

- **Snowflake connection** — posts `dsn` and `username` to `/api/connect` and caches the ODBC session
- **Model segment comparison** — project search, scoring-run picker, comparison list, and heatmap PDF download
- **Model feature comparison** — project search, modeling-run picker, then a side-by-side importance table

## Run locally

Windows with a Snowflake ODBC DSN (the original setup):

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

The app listens on [http://127.0.0.1:5000](http://127.0.0.1:5000). Do not use port 48631.

Set `SNOWFLAKE_DSN` / `SNOWFLAKE_USER` in `.env`, or enter them on the connection page. The first Connect click is when the browser SSO prompt should appear.

## Comparison tables

Selected runs are stored as fully qualified names, matching the original items list:

`{DATABASE}.{PROJECT}__{ACTIVITY}{SHORT_NAME}.S540_SEGMENTED` from `TCAT_CENTRAL.PUBLIC.RUNS`

Analysis joins those tables on `PID` and writes one heatmap page per pair to `generated/`.

## Feature importance table

Selected models are stored as fully qualified `FEATURE_METRICS` names from `TCAT_CENTRAL.PUBLIC.RUNS`:

`{DATABASE}.{PROJECT}__{ACTIVITY}{SHORT_NAME}.FEATURE_METRICS`

**Get Model Feature Analysis** runs this query for each selected model:

```sql
SELECT NAME AS FEATURE, VALUE AS IMPORTANCE
FROM {table} F
LEFT JOIN TCAT_CENTRAL.FEATURE_HANDLING.FEATURES_BACKPOPULATION D ON F.NAME = D.FEATURE_NAME
WHERE METRIC = 'IMPORTANCE'
QUALIFY ROW_NUMBER() OVER (PARTITION BY NAME ORDER BY IMPORTANCE DESC) = 1
ORDER BY IMPORTANCE DESC
LIMIT 20
```

Unique feature names are appended in first-seen order. Each model’s result is left-joined onto that list. Column headers are the schema names (`GIVING_IQ__M002`, `SHRINERS_MIDLEVEL_MODEL2__M004`, …). A blank cell means the feature was not in that model’s top 20.

The comparison table is shown on the page. **Download CSV** saves the same table (Excel-friendly UTF-8 with BOM) under `generated/`.
