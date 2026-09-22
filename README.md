# Hicks Analytics | HVAC Performance Hub

A portfolio-grade analytics engineering project for **Hicks Analytics** using a fictional Middle Tennessee HVAC company and entirely synthetic data.

It connects estimating, technician, job-costing, customer, and maintenance-agreement data to answer practical questions about margins, productivity, first-time fix, callbacks, sales conversion, and recurring revenue.

## Dashboard views

The app opens in **Guided Demo** mode with a five-step HVAC owner story focused
on first-time fix, callbacks, recovered technician capacity, and an operational
coaching plan. **Explore Dashboard** preserves the complete filtered dashboard.

1. **Executive Overview** — revenue, profit, average ticket, first-time fix, service mix, and operating insights.
2. **Job Profitability** — job margins, labor variance, emergency work, and loss-making jobs.
3. **Technician Performance** — revenue per hour, service quality, callbacks, ratings, and agreement conversion.
4. **Sales & Agreements** — estimate conversion, lead sources, active agreements, and renewal rates.

## Architecture

```text
Synthetic CSVs → DuckDB analytics layer → validated marts → Streamlit dashboard
```

## Run locally

```bash
pip install -r requirements.txt
python scripts/generate_data.py
python scripts/build_duckdb.py
streamlit run app.py
```

The app automatically prepares its synthetic data on first launch when the database is missing.

## Data safety

All companies, customers, technicians, jobs, estimates, and results are fictional. No client, employee, patient, or consumer data is used.
# Hicks Analytics | HVAC Performance Hub

A portfolio-grade analytics engineering project for **Hicks Analytics** using a fictional Middle Tennessee HVAC company and entirely synthetic data.

It connects estimating, technician, job-costing, customer, and maintenance-agreement data to answer practical questions about margins, productivity, first-time fix, callbacks, sales conversion, and recurring revenue.

## Dashboard views

1. **Executive Overview** — revenue, profit, average ticket, first-time fix, service mix, and operating insights.
2. **Job Profitability** — job margins, labor variance, emergency work, and loss-making jobs.
3. **Technician Performance** — revenue per hour, service quality, callbacks, ratings, and agreement conversion.
4. **Sales & Agreements** — estimate conversion, lead sources, active agreements, and renewal rates.

## Architecture

```text
Synthetic CSVs → DuckDB analytics layer → validated marts → Streamlit dashboard
```

## Run locally

```bash
pip install -r requirements.txt
python scripts/generate_data.py
python scripts/build_duckdb.py
streamlit run app.py
```

The app automatically prepares its synthetic data on first launch when the database is missing.

## Data safety

All companies, customers, technicians, jobs, estimates, and results are fictional. No client, employee, patient, or consumer data is used.
