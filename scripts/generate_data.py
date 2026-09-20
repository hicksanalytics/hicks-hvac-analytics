from pathlib import Path
import random

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RNG = np.random.default_rng(42)
random.seed(42)

START = pd.Timestamp("2025-01-01")
END = pd.Timestamp("2026-08-31")

CITIES = ["Nashville", "Franklin", "Brentwood", "Nolensville", "Spring Hill"]
CITY_WEIGHTS = [0.34, 0.23, 0.16, 0.12, 0.15]
LEAD_SOURCES = ["Google", "Referral", "Organic", "Home Services Marketplace", "Direct Mail"]

SERVICES = [
    (1, "AC Repair", "Repair", 485, 2.2, 105, 0.48),
    (2, "Heating Repair", "Repair", 525, 2.4, 115, 0.47),
    (3, "System Replacement", "Installation", 9850, 18.0, 5150, 0.36),
    (4, "Ductwork", "Installation", 2450, 10.0, 780, 0.42),
    (5, "Seasonal Tune-Up", "Maintenance", 189, 1.3, 28, 0.55),
    (6, "Indoor Air Quality", "Add-On", 1180, 3.5, 475, 0.44),
    (7, "Commercial Service", "Commercial", 1125, 4.5, 280, 0.45),
]


def clipped(value, low, high):
    return float(np.clip(value, low, high))


def main():
    RAW.mkdir(parents=True, exist_ok=True)

    technicians = pd.DataFrame([
        (1, "Marcus Reed", "Senior Technician", "Nashville", 0.94, 0.91, 4.8, 34),
        (2, "Elena Brooks", "Senior Technician", "Franklin", 0.97, 0.94, 4.9, 35),
        (3, "Troy Wallace", "Service Technician", "Nolensville", 1.02, 0.86, 4.6, 29),
        (4, "Devon Price", "Service Technician", "Spring Hill", 1.06, 0.83, 4.5, 28),
        (5, "Caleb Morgan", "Install Lead", "Nashville", 0.96, 0.89, 4.7, 36),
        (6, "Maya Bennett", "Service Technician", "Brentwood", 0.99, 0.90, 4.8, 31),
        (7, "Noah Jenkins", "Install Lead", "Franklin", 1.01, 0.87, 4.6, 35),
        (8, "Isaiah Turner", "Service Technician", "Nashville", 1.10, 0.79, 4.3, 27),
    ], columns=["technician_id", "technician_name", "role", "home_base", "efficiency_factor", "first_time_fix_skill", "rating_baseline", "hourly_cost"])

    services = pd.DataFrame(SERVICES, columns=["service_id", "service_name", "service_category", "base_price", "estimated_hours", "base_material_cost", "target_margin"])

    customer_rows = []
    for customer_id in range(1, 1451):
        city = random.choices(CITIES, weights=CITY_WEIGHTS, k=1)[0]
        customer_rows.append({
            "customer_id": customer_id,
            "customer_name": f"Customer {customer_id:04d}",
            "customer_type": random.choices(["Residential", "Commercial"], [0.88, 0.12])[0],
            "city": city,
            "signup_date": START - pd.Timedelta(days=random.randint(10, 1600)),
            "lead_source": random.choices(LEAD_SOURCES, [0.34, 0.25, 0.18, 0.13, 0.10])[0],
            "maintenance_member": int(RNG.random() < 0.31),
        })
    customers = pd.DataFrame(customer_rows)

    jobs = []
    estimates = []
    job_id = 1
    estimate_id = 1
    dates = pd.date_range(START, END, freq="D")

    for date in dates:
        seasonal = 1.0 + 0.58 * np.sin((date.dayofyear - 105) / 365 * 2 * np.pi) ** 2
        weekday_factor = 0.72 if date.dayofweek >= 5 else 1.0
        daily_jobs = int(RNG.poisson(17 * seasonal * weekday_factor))

        for _ in range(daily_jobs):
            customer = customers.iloc[int(RNG.integers(0, len(customers)))]
            service_weights = [0.29, 0.16, 0.09, 0.08, 0.25, 0.08, 0.05]
            service = services.iloc[random.choices(range(len(services)), weights=service_weights, k=1)[0]]
            tech_pool = technicians
            if service.service_category == "Installation":
                tech_pool = technicians[technicians.role == "Install Lead"]
            tech = tech_pool.iloc[int(RNG.integers(0, len(tech_pool)))]

            emergency = int(service.service_category == "Repair" and RNG.random() < 0.24)
            member = int(customer.maintenance_member)
            price_multiplier = RNG.lognormal(mean=0, sigma=0.18)
            if customer.customer_type == "Commercial":
                price_multiplier *= 1.75
            quoted_revenue = round(service.base_price * price_multiplier, 2)
            won_prob = 0.73 if service.service_category != "Installation" else 0.49
            won_prob += 0.07 if member else 0
            won = RNG.random() < won_prob

            estimates.append({
                "estimate_id": estimate_id,
                "customer_id": int(customer.customer_id),
                "service_id": int(service.service_id),
                "estimate_date": date - pd.Timedelta(days=int(RNG.integers(0, 13))),
                "quoted_revenue": quoted_revenue,
                "estimate_status": "Won" if won else random.choice(["Lost", "Open"]),
                "won_date": date if won else pd.NaT,
                "lead_source": customer.lead_source,
            })

            if won:
                estimated_hours = clipped(service.estimated_hours * RNG.normal(1, 0.12), 0.5, 40)
                actual_hours = clipped(estimated_hours * RNG.normal(tech.efficiency_factor, 0.16), 0.4, 48)
                material_cost = max(8, service.base_material_cost * price_multiplier * RNG.normal(1, 0.11))
                labor_cost = actual_hours * tech.hourly_cost
                discount = 0.10 if member and service.service_category == "Repair" else 0
                billed_revenue = quoted_revenue * (1 - discount) * RNG.normal(1.0, 0.035)
                first_time_fix = int(RNG.random() < tech.first_time_fix_skill - (0.05 if emergency else 0))
                callback = int((not first_time_fix and RNG.random() < 0.62) or RNG.random() < 0.018)
                travel_minutes = int(clipped(RNG.normal(29 if customer.city == tech.home_base else 43, 12), 8, 95))
                response_minutes = int(clipped(RNG.normal(82 if emergency else 240, 55), 20, 620))
                rating = clipped(RNG.normal(tech.rating_baseline - callback * 0.55, 0.25), 2.5, 5.0)
                agreement_sold = int(not member and service.service_category in ["Repair", "Maintenance"] and RNG.random() < (0.17 + 0.08 * (tech.first_time_fix_skill - 0.8)))

                jobs.append({
                    "job_id": job_id,
                    "estimate_id": estimate_id,
                    "customer_id": int(customer.customer_id),
                    "service_id": int(service.service_id),
                    "technician_id": int(tech.technician_id),
                    "completed_date": date,
                    "city": customer.city,
                    "customer_type": customer.customer_type,
                    "maintenance_member": member,
                    "emergency_flag": emergency,
                    "billed_revenue": round(billed_revenue, 2),
                    "estimated_labor_hours": round(estimated_hours, 2),
                    "actual_labor_hours": round(actual_hours, 2),
                    "labor_cost": round(labor_cost, 2),
                    "material_cost": round(material_cost, 2),
                    "first_time_fix_flag": first_time_fix,
                    "callback_flag": callback,
                    "agreement_sold_flag": agreement_sold,
                    "travel_minutes": travel_minutes,
                    "response_minutes": response_minutes,
                    "customer_rating": round(rating, 1),
                })
                job_id += 1

            estimate_id += 1

    jobs_df = pd.DataFrame(jobs)
    estimates_df = pd.DataFrame(estimates)

    membership_rows = []
    membership_id = 1
    for _, customer in customers[customers.maintenance_member == 1].iterrows():
        start_date = max(pd.Timestamp(customer.signup_date), START - pd.Timedelta(days=random.randint(30, 500)))
        annual_value = random.choice([189, 229, 279])
        renewed = int(RNG.random() < 0.79)
        membership_rows.append({
            "membership_id": membership_id,
            "customer_id": int(customer.customer_id),
            "start_date": start_date,
            "annual_value": annual_value,
            "renewed_flag": renewed,
            "status": "Active" if renewed or start_date > END - pd.Timedelta(days=365) else "Expired",
        })
        membership_id += 1
    memberships = pd.DataFrame(membership_rows)

    for name, frame in {
        "customers": customers,
        "services": services,
        "technicians": technicians,
        "estimates": estimates_df,
        "jobs": jobs_df,
        "memberships": memberships,
    }.items():
        frame.to_csv(RAW / f"{name}.csv", index=False)

    print(f"Generated {len(jobs_df):,} completed HVAC jobs and {len(estimates_df):,} estimates.")


if __name__ == "__main__":
    main()
