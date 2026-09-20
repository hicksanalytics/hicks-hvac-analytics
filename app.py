from pathlib import Path
import runpy

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "hicks_hvac.duckdb"
BUILD_SCRIPT = ROOT / "scripts" / "build_duckdb.py"

st.set_page_config(page_title="Hicks Analytics | HVAC Performance Hub", page_icon="❄️", layout="wide")
st.markdown("""
<style>
.block-container{padding-top:1.25rem;max-width:1480px}.brand-kicker{font-size:.76rem;letter-spacing:.15em;text-transform:uppercase;color:#45a9ce;font-weight:700}.brand-title{font-size:2.15rem;font-weight:760;line-height:1.1}.brand-subtitle{opacity:.68;margin-bottom:1.2rem}.insight-card{border:1px solid rgba(100,130,150,.22);border-radius:14px;padding:1rem 1.1rem;min-height:125px;background:rgba(65,156,195,.035)}.insight-card strong{color:#2d7fa2}div[data-testid="stMetric"]{border:1px solid rgba(105,130,150,.19);padding:.75rem .85rem;border-radius:14px}.demo-note{font-size:.8rem;opacity:.65;border-top:1px solid rgba(120,120,120,.2);padding-top:.75rem}
</style>
""", unsafe_allow_html=True)


def require_database():
    if not DB_PATH.exists():
        with st.spinner("Preparing the synthetic HVAC portfolio data..."):
            try:
                runpy.run_path(str(BUILD_SCRIPT), run_name="__main__")
            except Exception as exc:
                st.error("The demo data could not be prepared.")
                st.exception(exc)
                st.stop()


@st.cache_data
def query(sql):
    require_database()
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        return con.execute(sql).df()
    finally:
        con.close()


jobs = query("select * from analytics.fct_job_performance")
estimates = query("select * from analytics.mart_estimate_performance")
memberships = query("select * from analytics.mart_membership_performance")
jobs["completed_date"] = pd.to_datetime(jobs["completed_date"])


def money(value):
    value = float(value)
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:,.2f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:,.0f}K"
    return f"${value:,.0f}"


def pct(value):
    return f"{float(value):.1%}"


def chart(fig, height=360, unified=True):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=50, b=10), legend_title_text="", hovermode="x unified" if unified else "closest")
    return fig


def headline():
    st.markdown('<div class="brand-kicker">Hicks Analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="brand-title">HVAC Performance Hub</div>', unsafe_allow_html=True)
    st.markdown('<div class="brand-subtitle">Revenue, technician productivity, service quality, sales, and maintenance agreements.</div>', unsafe_allow_html=True)


st.sidebar.markdown("## Hicks Analytics")
st.sidebar.caption("HVAC Performance Hub")
st.sidebar.divider()
page = st.sidebar.radio("View", ["Executive Overview", "Job Profitability", "Technician Performance", "Sales & Agreements"])
min_date, max_date = jobs.completed_date.min().date(), jobs.completed_date.max().date()
date_range = st.sidebar.date_input("Completed date", value=(min_date, max_date), min_value=min_date, max_value=max_date)
selected_cities = st.sidebar.multiselect("Service area", sorted(jobs.city.unique()), default=sorted(jobs.city.unique()))
selected_services = st.sidebar.multiselect("Service", sorted(jobs.service_name.unique()), default=sorted(jobs.service_name.unique()))
selected_techs = st.sidebar.multiselect("Technician", sorted(jobs.technician_name.unique()), default=sorted(jobs.technician_name.unique()))
member_filter = st.sidebar.selectbox("Customer membership", ["All customers", "Members", "Non-members"])
st.sidebar.markdown('<div class="demo-note">Portfolio demo · Synthetic Middle Tennessee HVAC data</div>', unsafe_allow_html=True)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = map(pd.Timestamp, date_range)
else:
    start_date = end_date = pd.Timestamp(date_range)
filtered = jobs[jobs.completed_date.between(start_date, end_date) & jobs.city.isin(selected_cities) & jobs.service_name.isin(selected_services) & jobs.technician_name.isin(selected_techs)].copy()
if member_filter == "Members":
    filtered = filtered[filtered.maintenance_member == 1]
elif member_filter == "Non-members":
    filtered = filtered[filtered.maintenance_member == 0]
if filtered.empty:
    st.warning("No completed jobs match the current filters.")
    st.stop()


def metrics(df):
    revenue, profit = df.billed_revenue.sum(), df.gross_profit.sum()
    return dict(revenue=revenue, profit=profit, margin=profit/revenue, jobs=len(df), ticket=revenue/len(df), ftf=df.first_time_fix_flag.mean(), callback=df.callback_flag.mean())


def metric_row(labels, values):
    for col, label, value in zip(st.columns(len(labels)), labels, values):
        col.metric(label, value, border=True)


headline()

if page == "Executive Overview":
    m = metrics(filtered)
    metric_row(["Revenue", "Gross Profit", "Gross Margin", "Jobs Completed", "Avg Ticket", "First-Time Fix"], [money(m["revenue"]), money(m["profit"]), pct(m["margin"]), f'{m["jobs"]:,}', money(m["ticket"]), pct(m["ftf"])])
    monthly = filtered.groupby(pd.Grouper(key="completed_date", freq="MS")).agg(Revenue=("billed_revenue", "sum"), Gross_Profit=("gross_profit", "sum")).reset_index()
    c1, c2 = st.columns([1.35, 1])
    with c1:
        long = monthly.melt(id_vars="completed_date", value_vars=["Revenue", "Gross_Profit"], var_name="Metric", value_name="Amount")
        long.Metric = long.Metric.str.replace("_", " ")
        fig = px.line(long, x="completed_date", y="Amount", color="Metric", markers=True, title="Revenue & Gross Profit Trend", color_discrete_sequence=["#1689b0", "#51c4b8"])
        fig.update_yaxes(tickprefix="$", tickformat=",.0f")
        st.plotly_chart(chart(fig), width="stretch")
    with c2:
        svc = filtered.groupby("service_name", as_index=False).billed_revenue.sum().sort_values("billed_revenue")
        fig = px.bar(svc, x="billed_revenue", y="service_name", orientation="h", title="Revenue by Service", color_discrete_sequence=["#1689b0"])
        fig.update_xaxes(tickprefix="$", tickformat=",.0f")
        st.plotly_chart(chart(fig), width="stretch")
    c3, c4 = st.columns(2)
    with c3:
        quality = filtered.groupby("technician_name").agg(First_Time_Fix=("first_time_fix_flag", "mean")).reset_index().sort_values("First_Time_Fix")
        fig = px.bar(quality, x="First_Time_Fix", y="technician_name", orientation="h", title="First-Time Fix by Technician", color_discrete_sequence=["#51c4b8"])
        fig.update_xaxes(tickformat=".0%", range=[.65, 1])
        st.plotly_chart(chart(fig), width="stretch")
    with c4:
        city = filtered.groupby("city").agg(Revenue=("billed_revenue", "sum"), Profit=("gross_profit", "sum")).assign(Margin=lambda x:x.Profit/x.Revenue).reset_index()
        fig = px.scatter(city, x="Revenue", y="Margin", size="Revenue", color="city", text="city", title="Service Area Revenue & Margin")
        fig.update_xaxes(tickprefix="$", tickformat=",.0f"); fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(chart(fig, unified=False), width="stretch")
    tech = filtered.groupby("technician_name").agg(FTF=("first_time_fix_flag", "mean"), Callback=("callback_flag", "mean"), Agreement=("agreement_sold_flag", "mean")).reset_index()
    low_ftf, high_cb, best_ag = tech.sort_values("FTF").iloc[0], tech.sort_values("Callback", ascending=False).iloc[0], tech.sort_values("Agreement", ascending=False).iloc[0]
    st.subheader("Operational Insights")
    i1, i2, i3 = st.columns(3)
    i1.markdown(f'<div class="insight-card"><strong>First-time fix opportunity</strong><br>{low_ftf.technician_name} is lowest at <b>{pct(low_ftf.FTF)}</b>; review parts availability and diagnostic coaching.</div>', unsafe_allow_html=True)
    i2.markdown(f'<div class="insight-card"><strong>Callback exposure</strong><br>{high_cb.technician_name} has the highest callback rate at <b>{pct(high_cb.Callback)}</b>.</div>', unsafe_allow_html=True)
    i3.markdown(f'<div class="insight-card"><strong>Agreement conversion</strong><br>{best_ag.technician_name} leads at <b>{pct(best_ag.Agreement)}</b>.</div>', unsafe_allow_html=True)

elif page == "Job Profitability":
    m = metrics(filtered)
    metric_row(["Jobs", "Gross Margin", "Jobs Losing Money", "Jobs >10% Labor Over", "Emergency Calls"], [f'{m["jobs"]:,}', pct(m["margin"]), f'{int((filtered.gross_profit<0).sum()):,}', f'{int((filtered.labor_variance_pct>.1).sum()):,}', f'{int(filtered.emergency_flag.sum()):,}'])
    c1, c2 = st.columns(2)
    with c1:
        fig = px.scatter(filtered, x="billed_revenue", y="gross_margin_pct", color="service_name", hover_data=["customer_name", "technician_name", "city"], title="Job Value vs Gross Margin")
        fig.update_xaxes(tickprefix="$", tickformat=",.0f"); fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(chart(fig, 430, False), width="stretch")
    with c2:
        svc = filtered.groupby("service_name").agg(Revenue=("billed_revenue", "sum"), Profit=("gross_profit", "sum"), Labor_Variance=("labor_variance_pct", "mean")).assign(Margin=lambda x:x.Profit/x.Revenue).reset_index().sort_values("Margin")
        fig = px.bar(svc, x="Margin", y="service_name", color="Labor_Variance", orientation="h", title="Service Margin & Labor Variance", color_continuous_scale="RdYlGn_r")
        fig.update_xaxes(tickformat=".0%")
        st.plotly_chart(chart(fig, 430), width="stretch")
    st.subheader("Job Detail")
    st.dataframe(filtered[["completed_date", "customer_name", "service_name", "technician_name", "city", "billed_revenue", "gross_profit", "gross_margin_pct", "labor_variance_pct", "first_time_fix_flag", "callback_flag"]].sort_values("gross_profit"), width="stretch", hide_index=True)

elif page == "Technician Performance":
    tech = filtered.groupby(["technician_name", "technician_role"]).agg(Jobs=("job_id", "count"), Revenue=("billed_revenue", "sum"), Profit=("gross_profit", "sum"), Hours=("actual_labor_hours", "sum"), First_Time_Fix=("first_time_fix_flag", "mean"), Callback_Rate=("callback_flag", "mean"), Agreement_Conversion=("agreement_sold_flag", "mean"), Rating=("customer_rating", "mean")).assign(Gross_Margin=lambda x:x.Profit/x.Revenue, Revenue_Per_Hour=lambda x:x.Revenue/x.Hours).reset_index()
    metric_row(["Technicians", "Top Revenue / Hour", "First-Time Fix", "Callback Rate", "Avg Rating"], [f"{len(tech):,}", money(tech.Revenue_Per_Hour.max()), pct(filtered.first_time_fix_flag.mean()), pct(filtered.callback_flag.mean()), f"{filtered.customer_rating.mean():.2f}"])
    c1, c2 = st.columns(2)
    with c1:
        fig = px.scatter(tech, x="Revenue_Per_Hour", y="First_Time_Fix", size="Revenue", color="Gross_Margin", hover_name="technician_name", title="Productivity vs Service Quality", color_continuous_scale="Teal")
        fig.update_xaxes(tickprefix="$", tickformat=",.0f"); fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(chart(fig, 430, False), width="stretch")
    with c2:
        long = tech.melt(id_vars="technician_name", value_vars=["First_Time_Fix", "Callback_Rate", "Agreement_Conversion"], var_name="Metric", value_name="Rate")
        long.Metric = long.Metric.str.replace("_", " ")
        fig = px.bar(long, x="Rate", y="technician_name", color="Metric", barmode="group", orientation="h", title="Quality & Sales Rates")
        fig.update_xaxes(tickformat=".0%")
        st.plotly_chart(chart(fig, 430), width="stretch")
    st.dataframe(tech.sort_values("Revenue", ascending=False), width="stretch", hide_index=True)

else:
    est = estimates[estimates.service_id.isin(filtered.service_id.unique())].copy()
    sent, won = est.estimates_sent.sum(), est.estimates_won.sum()
    member = memberships.iloc[0]
    metric_row(["Estimates Sent", "Estimate Win Rate", "Quoted Pipeline", "Active Agreements", "Agreement Renewal"], [f"{int(sent):,}", pct(won/sent), money(est.quoted_value.sum()), f"{int(member.active_memberships):,}", pct(member.renewal_rate)])
    c1, c2 = st.columns(2)
    by_service = est.groupby("service_name").agg(Estimates=("estimates_sent", "sum"), Won=("estimates_won", "sum"), Quoted=("quoted_value", "sum")).assign(Win_Rate=lambda x:x.Won/x.Estimates).reset_index()
    by_source = est.groupby("lead_source").agg(Estimates=("estimates_sent", "sum"), Won=("estimates_won", "sum"), Quoted=("quoted_value", "sum")).assign(Win_Rate=lambda x:x.Won/x.Estimates).reset_index()
    with c1:
        fig = px.bar(by_service.sort_values("Win_Rate"), x="Win_Rate", y="service_name", orientation="h", color="Quoted", title="Estimate Win Rate by Service", color_continuous_scale="Blues")
        fig.update_xaxes(tickformat=".0%"); st.plotly_chart(chart(fig, 430), width="stretch")
    with c2:
        fig = px.scatter(by_source, x="Estimates", y="Win_Rate", size="Quoted", color="lead_source", text="lead_source", title="Lead Source Volume & Conversion")
        fig.update_yaxes(tickformat=".0%"); st.plotly_chart(chart(fig, 430, False), width="stretch")
    eligible = filtered[(filtered.maintenance_member == 0) & filtered.service_category.isin(["Repair", "Maintenance"])]
    agreement_rate = eligible.agreement_sold_flag.mean() if len(eligible) else 0
    potential = int(len(eligible) * max(0, .25-agreement_rate))
    install = by_service[by_service.service_name == "System Replacement"]
    install_rate = install.Win_Rate.iloc[0] if len(install) else 0
    top_source = by_source.sort_values("Win_Rate", ascending=False).iloc[0]
    st.subheader("Growth Opportunities")
    i1, i2, i3 = st.columns(3)
    i1.markdown(f'<div class="insight-card"><strong>Agreement opportunity</strong><br>Reaching 25% conversion would add about <b>{potential:,}</b> agreements.</div>', unsafe_allow_html=True)
    i2.markdown(f'<div class="insight-card"><strong>Replacement close rate</strong><br>System replacement estimates convert at <b>{pct(install_rate)}</b>.</div>', unsafe_allow_html=True)
    i3.markdown(f'<div class="insight-card"><strong>Best lead source</strong><br>{top_source.lead_source} leads conversion at <b>{pct(top_source.Win_Rate)}</b>.</div>', unsafe_allow_html=True)
