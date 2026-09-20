from pathlib import Path
import runpy

import duckdb


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs"
DB = ROOT / "hicks_hvac.duckdb"

required = ["customers", "services", "technicians", "estimates", "jobs", "memberships"]
if any(not (RAW / f"{name}.csv").exists() for name in required):
    runpy.run_path(str(ROOT / "scripts" / "generate_data.py"), run_name="__main__")

con = duckdb.connect(str(DB))
con.execute("create schema if not exists raw")
con.execute("create schema if not exists analytics")

for table in required:
    path = (RAW / f"{table}.csv").as_posix()
    con.execute(f"create or replace table raw.{table} as select * from read_csv_auto('{path}', header=true)")

con.execute("""
create or replace table analytics.fct_job_performance as
select
    j.job_id, j.estimate_id, cast(j.completed_date as date) completed_date,
    date_trunc('month', cast(j.completed_date as date)) completed_month,
    j.customer_id, c.customer_name, j.customer_type, c.lead_source,
    j.maintenance_member, j.emergency_flag,
    j.service_id, s.service_name, s.service_category, s.target_margin,
    j.technician_id, t.technician_name, t.role technician_role, t.home_base,
    j.city, j.billed_revenue, j.labor_cost, j.material_cost,
    j.billed_revenue - j.labor_cost - j.material_cost gross_profit,
    (j.billed_revenue - j.labor_cost - j.material_cost) / nullif(j.billed_revenue, 0) gross_margin_pct,
    j.estimated_labor_hours, j.actual_labor_hours,
    j.actual_labor_hours - j.estimated_labor_hours labor_variance_hours,
    (j.actual_labor_hours - j.estimated_labor_hours) / nullif(j.estimated_labor_hours, 0) labor_variance_pct,
    j.first_time_fix_flag, j.callback_flag, j.agreement_sold_flag,
    j.travel_minutes, j.response_minutes, j.customer_rating
from raw.jobs j
left join raw.customers c using(customer_id)
left join raw.services s using(service_id)
left join raw.technicians t using(technician_id)
""")

con.execute("""
create or replace table analytics.mart_executive_monthly as
select completed_month, count(*) jobs_completed, count(distinct customer_id) customers_served,
       sum(billed_revenue) revenue, sum(gross_profit) gross_profit,
       sum(gross_profit)/nullif(sum(billed_revenue),0) gross_margin_pct,
       avg(billed_revenue) avg_ticket,
       sum(billed_revenue)/nullif(sum(actual_labor_hours),0) revenue_per_tech_hour,
       avg(first_time_fix_flag) first_time_fix_rate, avg(callback_flag) callback_rate,
       avg(customer_rating) avg_customer_rating
from analytics.fct_job_performance group by 1 order by 1
""")

con.execute("""
create or replace table analytics.mart_technician_performance as
select technician_id, technician_name, technician_role,
       count(*) jobs_completed, sum(billed_revenue) revenue, sum(gross_profit) gross_profit,
       sum(gross_profit)/nullif(sum(billed_revenue),0) gross_margin_pct,
       sum(actual_labor_hours) tech_hours,
       sum(billed_revenue)/nullif(sum(actual_labor_hours),0) revenue_per_tech_hour,
       avg(first_time_fix_flag) first_time_fix_rate, avg(callback_flag) callback_rate,
       avg(agreement_sold_flag) agreement_conversion_rate,
       avg(labor_variance_pct) avg_labor_variance_pct, avg(customer_rating) avg_rating
from analytics.fct_job_performance group by 1,2,3 order by revenue desc
""")

con.execute("""
create or replace table analytics.mart_service_performance as
select service_id, service_name, service_category, count(*) jobs_completed,
       sum(billed_revenue) revenue, sum(gross_profit) gross_profit,
       sum(gross_profit)/nullif(sum(billed_revenue),0) gross_margin_pct,
       avg(billed_revenue) avg_ticket, avg(first_time_fix_flag) first_time_fix_rate,
       avg(callback_flag) callback_rate, avg(labor_variance_pct) avg_labor_variance_pct
from analytics.fct_job_performance group by 1,2,3 order by revenue desc
""")

con.execute("""
create or replace table analytics.mart_estimate_performance as
select e.service_id, s.service_name, e.lead_source,
       count(*) estimates_sent,
       sum(case when e.estimate_status='Won' then 1 else 0 end) estimates_won,
       sum(case when e.estimate_status='Won' then 1 else 0 end)/nullif(count(*),0)::double win_rate,
       sum(e.quoted_revenue) quoted_value, avg(e.quoted_revenue) avg_estimate_value
from raw.estimates e left join raw.services s using(service_id)
group by 1,2,3 order by quoted_value desc
""")

con.execute("""
create or replace table analytics.mart_membership_performance as
select count(*) memberships, sum(annual_value) annual_contract_value,
       avg(renewed_flag) renewal_rate,
       sum(case when status='Active' then 1 else 0 end) active_memberships
from raw.memberships
""")

OUT.mkdir(exist_ok=True)
exports = {
    "job_performance": "analytics.fct_job_performance",
    "executive_monthly": "analytics.mart_executive_monthly",
    "technician_performance": "analytics.mart_technician_performance",
    "service_performance": "analytics.mart_service_performance",
    "estimate_performance": "analytics.mart_estimate_performance",
    "membership_performance": "analytics.mart_membership_performance",
}
for name, table in exports.items():
    con.execute(f"copy {table} to '{(OUT / f'{name}.csv').as_posix()}' (header, delimiter ',')")

checks = {
    "job_id_unique": "select count(*)=count(distinct job_id) from analytics.fct_job_performance",
    "positive_revenue": "select count(*)=0 from analytics.fct_job_performance where billed_revenue<=0",
    "valid_first_time_fix": "select count(*)=0 from analytics.fct_job_performance where first_time_fix_flag not in (0,1)",
    "valid_callback": "select count(*)=0 from analytics.fct_job_performance where callback_flag not in (0,1)",
    "technicians_present": "select count(*)=0 from analytics.fct_job_performance where technician_id is null",
}
failed = []
for name, sql in checks.items():
    ok = con.execute(sql).fetchone()[0]
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok:
        failed.append(name)
if failed:
    raise SystemExit(f"Data quality checks failed: {failed}")

print(f"Built DuckDB database: {DB}")
con.close()
