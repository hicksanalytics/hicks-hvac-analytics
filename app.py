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
.block-container{padding-top:1.25rem;max-width:1480px}.brand-kicker{font-size:.76rem;letter-spacing:.15em;text-transform:uppercase;color:#45a9ce;font-weight:700}.brand-title{font-size:2.15rem;font-weight:760;line-height:1.1}.brand-subtitle{opacity:.68;margin-bottom:1.2rem}.insight-card{border:1px solid rgba(100,130,150,.22);border-radius:14px;padding:1rem 1.1rem;min-height:125px;background:rgba(65,156,195,.035)}.insight-card strong{color:#2d7fa2}div[data-testid="stMetric"]{border:1px solid rgba(105,130,150,.19);padding:.75rem .85rem;border-radius:14px}.demo-note{font-size:.8rem;opacity:.65;border-top:1px solid rgba(120,120,120,.2);padding-top:.75rem}.story-hero{background:linear-gradient(135deg,rgba(8,82,120,.97),rgba(20,130,165,.84));color:white;border-radius:20px;padding:1.6rem 1.8rem;margin:.4rem 0 1.2rem;box-shadow:0 12px 34px rgba(8,82,120,.17)}.story-hero h2{color:white;margin:0 0 .45rem}.story-hero p{color:rgba(255,255,255,.88);margin:0;max-width:860px}.story-callout{border-left:5px solid #45c4b8;background:rgba(69,196,184,.09);border-radius:0 14px 14px 0;padding:1rem 1.15rem;margin:.8rem 0 1.1rem}.story-step{text-transform:uppercase;letter-spacing:.1em;font-size:.74rem;font-weight:700;opacity:.7}
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
min_date, max_date = jobs.completed_date.min().date(), jobs.completed_date.max().date()
all_cities = sorted(jobs.city.unique())
all_services = sorted(jobs.service_name.unique())
all_techs = sorted(jobs.technician_name.unique())
experience = st.sidebar.radio("Experience", ["Guided Demo", "Explore Dashboard"], help="Follow an owner story or explore the complete dashboard.")
if experience == "Guided Demo":
    page = "Guided Demo"
    date_range = (min_date, max_date)
    selected_cities, selected_services, selected_techs = all_cities, all_services, all_techs
    member_filter = "All customers"
    st.sidebar.info("You are in the guided owner story. Switch to Explore Dashboard for filters and detailed views.")
else:
    page = st.sidebar.radio("View", ["Executive Overview", "Job Profitability", "Technician Performance", "Sales & Agreements"])
    date_range = st.sidebar.date_input("Completed date", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    selected_cities = st.sidebar.multiselect("Service area", all_cities, default=all_cities)
    selected_services = st.sidebar.multiselect("Service", all_services, default=all_services)
    selected_techs = st.sidebar.multiselect("Technician", all_techs, default=all_techs)
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


def technician_summary(df):
    return (
        df.groupby(["technician_name", "technician_role"])
        .agg(
            Jobs=("job_id", "count"), Revenue=("billed_revenue", "sum"),
            Profit=("gross_profit", "sum"), Hours=("actual_labor_hours", "sum"),
            First_Time_Fix=("first_time_fix_flag", "mean"),
            Callback_Rate=("callback_flag", "mean"), Callback_Jobs=("callback_flag", "sum"),
            Agreement_Conversion=("agreement_sold_flag", "mean"), Rating=("customer_rating", "mean"),
        )
        .assign(Gross_Margin=lambda x:x.Profit/x.Revenue, Revenue_Per_Hour=lambda x:x.Revenue/x.Hours)
        .reset_index()
    )


def change_story_step(delta):
    st.session_state.hvac_story_step = min(4, max(0, st.session_state.hvac_story_step + delta))


def story_navigation(step):
    st.write("")
    left, middle, right = st.columns([1, 2.4, 1])
    with left:
        if step > 0:
            st.button("← Previous", width="stretch", on_click=change_story_step, args=(-1,))
    with middle:
        st.progress(step / 4, text=f"Guided story · Step {step + 1} of 5")
    with right:
        if step < 4:
            st.button("Next →", type="primary", width="stretch", on_click=change_story_step, args=(1,))


def render_guided_demo(df):
    if "hvac_story_step" not in st.session_state:
        st.session_state.hvac_story_step = 0
    story_df = df[df["completed_date"].dt.to_period("M") < df["completed_date"].max().to_period("M")].copy()
    tech = technician_summary(story_df)
    focus = tech.sort_values(["First_Time_Fix", "Callback_Rate"], ascending=[True, False]).iloc[0]
    benchmark = tech.sort_values("First_Time_Fix", ascending=False).iloc[0]
    focus_jobs = story_df[story_df.technician_name == focus.technician_name].copy()
    portfolio_ftf = story_df.first_time_fix_flag.mean()
    step = st.session_state.hvac_story_step

    st.markdown(f'''<div class="story-hero"><div class="story-step">Interactive owner story</div><h2>Callbacks are climbing—but what is really driving them?</h2><p>Step into the HVAC owner's seat, isolate the service-quality gap, test an improvement target, and turn the finding into a coaching plan.</p></div>''', unsafe_allow_html=True)

    if step == 0:
        st.subheader("Your Monday-morning question")
        st.write("The schedule is packed, yet technicians are returning to jobs that should have been resolved on the first visit. Your goal is to identify where callbacks are consuming capacity and weakening the customer experience.")
        m = metrics(story_df)
        metric_row(["Revenue reviewed", "Gross profit", "First-time fix", "Callback rate"], [money(m["revenue"]), money(m["profit"]), pct(m["ftf"]), pct(m["callback"])])
        st.markdown('<div class="story-callout"><strong>Your mission:</strong> find the technician-quality gap, understand its operating cost, and model a realistic improvement.</div>', unsafe_allow_html=True)

    elif step == 1:
        st.subheader("The warning sign")
        metric_row(["Technician needing attention", "First-time fix", "Callback rate", "Gap vs team"], [focus.technician_name, pct(focus.First_Time_Fix), pct(focus.Callback_Rate), f"{(focus.First_Time_Fix-portfolio_ftf)*100:+.1f} pts"])
        chart_data = tech.sort_values("First_Time_Fix").copy()
        chart_data["Status"] = chart_data.technician_name.apply(lambda x: "Investigate" if x == focus.technician_name else "Other technicians")
        fig = px.bar(chart_data, x="First_Time_Fix", y="technician_name", color="Status", orientation="h", title="First-Time Fix by Technician", color_discrete_map={"Investigate":"#f59e0b","Other technicians":"#1689b0"})
        fig.update_xaxes(tickformat=".0%", range=[.65,1])
        st.plotly_chart(chart(fig, 390), width="stretch")
        st.markdown(f'<div class="story-callout"><strong>What the owner should notice:</strong> {focus.technician_name} trails {benchmark.technician_name} by <strong>{(benchmark.First_Time_Fix-focus.First_Time_Fix)*100:.1f} points</strong> in first-time fix. That gap creates repeat truck rolls and lost appointment capacity.</div>', unsafe_allow_html=True)

    elif step == 2:
        st.subheader("Follow the evidence")
        c1, c2 = st.columns([1.25,1])
        with c1:
            fig = px.scatter(tech, x="First_Time_Fix", y="Callback_Rate", size="Revenue", color="Rating", text="technician_name", title="First-Time Fix vs Callback Rate", color_continuous_scale="RdYlGn")
            fig.update_xaxes(tickformat=".0%"); fig.update_yaxes(tickformat=".0%"); fig.update_traces(textposition="top center")
            st.plotly_chart(chart(fig, 420, False), width="stretch")
        with c2:
            st.metric("Callback jobs", f"{int(focus.Callback_Jobs):,}", border=True)
            st.metric("Customer rating", f"{focus.Rating:.2f}", border=True)
            st.metric("Revenue / tech hour", money(focus.Revenue_Per_Hour), border=True)
            st.markdown(f'<div class="story-callout"><strong>Diagnosis:</strong> {focus.technician_name} combines the team\'s lowest first-time-fix rate with a {focus.Callback_Rate:.1%} callback rate. Review diagnostic consistency, parts readiness, and repeat service categories before treating this as a sales problem.</div>', unsafe_allow_html=True)

    elif step == 3:
        st.subheader("Test a decision before making it")
        st.caption(f"Model targeted diagnostic coaching and parts-readiness improvements for {focus.technician_name}. Financial impact uses observed labor cost on callback-flagged jobs.")
        callback_reduction = st.slider("Reduction in callback jobs", 10, 60, 35, 5, format="%d%%")
        ftf_gain = st.slider("First-time-fix improvement", 2, 15, 8, 1, format="%d points")
        callback_jobs = focus_jobs[focus_jobs.callback_flag == 1]
        avoided_callbacks = focus.Callback_Jobs * callback_reduction / 100
        avg_callback_hours = callback_jobs.actual_labor_hours.mean() if len(callback_jobs) else 0
        avg_callback_labor = callback_jobs.labor_cost.mean() if len(callback_jobs) else 0
        months = max(1, story_df.completed_date.dt.to_period("M").nunique())
        annual_labor_savings = avoided_callbacks * avg_callback_labor / months * 12
        annual_capacity_hours = avoided_callbacks * avg_callback_hours / months * 12
        modeled_ftf = min(1, focus.First_Time_Fix + ftf_gain / 100)
        metric_row(["Callbacks avoided", "Annual labor protected", "Annual capacity recovered", "Modeled first-time fix"], [f"{avoided_callbacks:,.0f}", money(annual_labor_savings), f"{annual_capacity_hours:,.0f} hrs", pct(modeled_ftf)])
        comparison = pd.DataFrame({"Scenario":["Current","Modeled"], "First-Time Fix":[focus.First_Time_Fix,modeled_ftf]})
        fig = px.bar(comparison, x="Scenario", y="First-Time Fix", color="Scenario", title="Current vs Modeled First-Time Fix", color_discrete_map={"Current":"#94a3b8","Modeled":"#1689b0"})
        fig.update_yaxes(tickformat=".0%", range=[0,1]); fig.update_layout(showlegend=False)
        st.plotly_chart(chart(fig, 340), width="stretch")
        st.caption("Illustrative scenario based on synthetic portfolio data. It is a decision aid, not a guaranteed forecast.")

    else:
        st.subheader("Turn the insight into an operating plan")
        c1, c2, c3 = st.columns(3)
        c1.markdown('<div class="insight-card"><strong>1 · Diagnose</strong><br><br>Review callback jobs by service, failure type, parts used, and original diagnosis. Separate process issues from individual coaching needs.</div>', unsafe_allow_html=True)
        c2.markdown('<div class="insight-card"><strong>2 · Act</strong><br><br>Create a diagnostic checklist, stage common parts, and coach the technician on the service categories driving repeat visits.</div>', unsafe_allow_html=True)
        c3.markdown('<div class="insight-card"><strong>3 · Measure</strong><br><br>Track first-time fix, callbacks, ratings, and revenue per technician hour weekly to verify sustained improvement.</div>', unsafe_allow_html=True)
        st.success("This is the Hicks Analytics approach: connect field-service data, surface the decision, quantify the opportunity, and build a repeatable management rhythm.")
        a1, a2, _ = st.columns([1.2,1.1,2])
        with a1:
            st.link_button("Build this for my business", "https://hicksanalytics.com/#contact", type="primary", width="stretch")
        with a2:
            if st.button("Restart the story", width="stretch"):
                st.session_state.hvac_story_step = 0
                st.rerun()
    story_navigation(step)


headline()

if page == "Guided Demo":
    render_guided_demo(filtered)

elif page == "Executive Overview":
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
