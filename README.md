# Ecuador Mobility Reliability

> A Python-first, end-to-end data product for turning permitted public mobility and weather data into an evidence-based analysis of transport reliability and delay prediction.

## Project status

**Repository bootstrap / project definition.** Implementation has not started yet. This README is the initial project contract and will be updated as the system becomes real. The source and data audit happens before any code; this document deliberately makes no data-coverage claims.

## Problem

Commuters, planners, and transport operators in Ecuadorian cities rarely have a quantitative picture of how reliable public transport actually is. Schedules exist, but punctuality varies by route, time of day, and weather — and the data needed to measure that variation is scattered across agencies, feeds, and formats (when it is public at all).

This project will turn permitted public mobility and weather data into a reproducible, evidence-based view of transport reliability: measured delays, their patterns, and a defensible delay-prediction baseline.

## Product goal

Build a small production-style data platform that answers questions such as:

- How on-time is a route or corridor, per stop, hour, and day type?
- How do delay distributions change with weather conditions?
- Where and when do the worst reliability problems concentrate?
- How much better than a historical-average baseline can a delay prediction be?

The product must show the evidence behind its conclusions. Every record should retain its source, collection time, and transformation history.

## Intended users

- Commuters who want to plan around known unreliable windows.
- City and transit planners evaluating route-level reliability.
- Transport operators comparing their performance against the data.
- Data and ML candidates demonstrating time-series and geospatial skills on a real problem.

## What the system will do

1. **Audit and select** permitted public mobility and weather sources (candidates: published GTFS feeds where available, INAMHI weather observations, and other permitted feeds — final coverage is decided by the audit, not by this README).
2. **Collect** source data with collection timestamps and source metadata.
3. **Preserve** raw source responses as fixtures for reproducible offline development.
4. **Define** delay and reliability metrics explicitly (scheduled-vs-actual where the feed provides it; otherwise documented proxies such as headway- or dwell-based measures — decided during the data audit).
5. **Validate** time series with walk-forward, out-of-sample splits before any modeling.
6. **Analyze** reliability by route, stop, hour, day type, and weather, with geospatial aggregation.
7. **Predict** delay with a simple baseline first (historical average, seasonal naive), then measured extensions.
8. **Expose** results through an interactive map and demo, plus reports.
9. **Report** data quality, gaps, source health, assumptions, and limitations — including explicit failure states.

## Demo vision

The final demo should be understandable in under one minute and show more than a happy-path chart:

- A map of the audited routes and stops with reliability color coding (for example, on-time share per stop).
- A delay-distribution view per route and hour, with the baseline prediction overlaid.
- A weather-context view linking conditions to delay patterns.
- A data-quality page showing the latest successful ingestion, source status, missing-data rate, and known limitations.
- An empty-result or source-outage state that explains what happened instead of silently failing.

The project will have a public deployment when hosting constraints are understood. Until then, a reproducible local demo and a short recorded walkthrough will be required.

## Scope

### Minimum viable product

- One audited, permitted mobility source and one weather source (or a clearly documented fallback to fixtures).
- A reproducible ingestion command using saved fixtures for offline development.
- Raw and cleaned data layers with documented reliability metrics.
- Walk-forward time-series validation with a simple baseline.
- Geospatial analysis at stop and route level.
- An interactive Streamlit demo with a map component.
- Automated tests for parsing, validation, metric calculation, and failure paths.
- A README that documents data lineage, metrics, limitations, and setup.

### Version 2

- Additional routes or cities after the source audit.
- FastAPI service for the analytical dataset.
- Scheduled ingestion and freshness monitoring.
- A measured ML extension (for example, gradient boosting or a small time-series model) only after the baseline is evaluated.
- Dockerized local deployment and CI checks.

### Explicitly out of scope

- Real-time GPS fleet tracking or private operator telemetry.
- Scraping any source in violation of its terms, robots policy, or access controls.
- Claiming citywide coverage before the source audit demonstrates it.
- Presenting correlation between weather and delay as causation.
- Building an opaque ML delay model without a baseline and evaluation.
- Adding cloud infrastructure before the local pipeline is reproducible.

## Proposed technical stack

| Layer | Initial choice | Purpose |
| --- | --- | --- |
| Language | Python | Core implementation and analysis |
| Environment | `uv` | Reproducible dependency and environment management |
| Quality | Ruff, pytest, Pandera | Formatting/linting, tests, and data contracts |
| Ingestion | Python source adapters, `httpx`, permitted parsers | Collect data without coupling the domain to one source |
| Raw storage | JSON and Parquet/GeoParquet fixtures | Preserve source evidence and enable offline development |
| Analytics | pandas and DuckDB | Cleaning, SQL analysis, and local analytical queries |
| Baseline | statsmodels and scikit-learn | Historical-average and seasonal baselines with evaluation |
| Geospatial | GeoPandas and a map component in the demo | Stop- and route-level spatial analysis and visualization |
| ML extension | scikit-learn, later | Measured delay-prediction improvements after the baseline |
| Demo | Streamlit for the MVP | Fast, readable, interactive public demonstration |
| API | FastAPI and Pydantic, later | Typed service boundary for the application |
| Delivery | Docker and GitHub Actions, later | Reproducible execution and automated checks |

Technology choices are staged deliberately: metrics and baselines come before models, and coverage claims come before code.

## Skills demonstrated

### Data science

- Problem framing and metric definition (reliability, punctuality, delay).
- Time-series validation: walk-forward splits, no leakage, out-of-sample reporting.
- Uncertainty, missingness, and gap handling.
- Correlation-vs-causation discipline around weather effects.

### Data engineering

- Source adapters and resilient ingestion.
- Raw, cleaned, and analytical data layers.
- Schema design and data contracts.
- Failure handling, freshness, and idempotency.
- SQL and geospatial analytics with DuckDB and GeoPandas.

### AI and ML

- Baseline-first modeling: naive and seasonal baselines before any learned model.
- Measured extension with honest error reporting.
- Feature discipline: weather and calendar features, tested on temporal splits.

### Software and full stack

- Typed Python modules and service boundaries.
- Interactive user experience through Streamlit with a map.
- Tests, documentation, configuration, logging, and reproducible execution.
- CI and deployment readiness.

### Professional communication

- Clear problem statement and stakeholder value.
- Architecture and data-lineage diagrams.
- Metrics, trade-offs, limitations, and failure analysis.
- A short demo video and a LinkedIn post focused on the result rather than the tool list.

## Evaluation plan

The project will report measurable evidence, including:

- Source health: ingestion success rate and freshness per source.
- Data quality: missingness per field, gap lengths, and duplicate rate on a reviewed sample.
- Baseline forecast error: MAE and RMSE on out-of-sample temporal splits.
- Improvement over baseline for any later model, reported with the same splits.
- Geospatial coverage of the audited dataset (routes, stops, time range).
- Dashboard and map response time for the demo workload.
- Reproducibility from a clean environment using fixtures.
- At least one intentionally induced failure (for example, a missing source) and the system's response.

A strong result is a trustworthy, explainable reliability view whose limitations are visible — not a large number of routes.

## Data and ethics principles

- Use only public or explicitly permitted sources.
- Respect terms of service, robots policies, rate limits, and attribution requirements (including weather-data attribution).
- Store source URLs and collection timestamps.
- Avoid personal data and unnecessary identifiers.
- Keep a fixture dataset so the project remains runnable if a source changes or disappears.
- Document source coverage and sampling bias; never claim coverage the audit did not establish.
- Never present the dashboard as an official transport statistic.
- Report gaps and failure states as first-class results, not footnotes.

## Planned repository structure

```text
.
├── README.md
├── pyproject.toml
├── src/
│   └── mobility_reliability/
│       ├── ingestion/
│       ├── metrics/
│       ├── validation/
│       ├── analytics/
│       └── config.py
├── tests/
├── data/
│   └── sample/
├── notebooks/
├── app/
├── docs/
└── .github/
    └── workflows/
```

Large raw datasets, credentials, and local runtime state must not be committed.

## Roadmap

- [ ] Audit candidate mobility and weather sources and their usage constraints.
- [ ] Define delay and reliability metrics and the canonical schema.
- [ ] Create source fixtures and the first ingestion adapter.
- [ ] Implement raw storage, cleaning, and metric calculation.
- [ ] Build the walk-forward validation harness and baseline forecasts.
- [ ] Add geospatial analysis and the first map visualizations.
- [ ] Add data-quality checks and failure-path tests.
- [ ] Build the Streamlit MVP with a map and quality page.
- [ ] Add an ML extension only after the baseline is measured.
- [ ] Add FastAPI and scheduled ingestion only when the MVP justifies them.
- [ ] Deploy the demo or publish a recorded walkthrough.
- [ ] Write the final technical case study and LinkedIn publication.

## Definition of done

The project is ready for portfolio publication when:

- A new contributor can run it from documented instructions.
- The demo answers a clear reliability question with traceable evidence.
- The pipeline handles missing data, gaps, and a source failure.
- Baselines and evaluation results are reported honestly on temporal splits.
- Tests and CI pass on the reviewed revision.
- The README explains the architecture, trade-offs, limitations, and next steps.
- A recruiter can understand the problem, result, and demo link in under two minutes.

## License

To be decided after the data-source and dependency licenses are audited.
