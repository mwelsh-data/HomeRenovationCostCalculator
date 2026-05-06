# app.py
# Streamlit MVP: Renovation selector → cost bands (materials + labor) + national providers
# No external APIs. Replace/extend the RENOVATION_DB dict as you collect better data.

import math
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Renovation Cost Estimator (MVP)", layout="wide")

# -----------------------
# Regional multipliers (rough, editable)
# -----------------------
REGION_MULT = {
    "National Avg": 1.00,
    "Northeast": 1.10,
    "Midwest": 0.95,
    "South": 0.97,
    "West": 1.12,
}

# Finish level multipliers (affects materials mostly)
FINISH_MULT = {
    "Basic": 0.90,
    "Standard": 1.00,
    "Premium": 1.20,
}

# -----------------------
# National / regional providers mapping (editable)
# -----------------------
PROVIDERS = {
    "Home Depot Home Services": ["Bathroom", "Kitchen", "Flooring", "Windows & Doors", "Roofing", "Exterior Paint"],
    "Lowe’s Installation Services": ["Bathroom", "Kitchen", "Flooring", "Windows & Doors", "Exterior Paint"],
    "Menards Home Services": ["Flooring", "Windows & Doors", "Roofing"],
    "Bath Fitter": ["Bathroom"],
    "Re-Bath": ["Bathroom"],
    "Mr. Handyman (Neighborly)": ["Bathroom", "Kitchen", "Interior Paint", "Exterior Paint", "Small Electrical"],
    "Window World": ["Windows & Doors"],
    "Renewal by Andersen": ["Windows & Doors"],
    "Empire Today": ["Flooring"],
    "LeafFilter": ["Exterior (Gutters)"],
}

# -----------------------
# Renovation menu + cost library
# unit: "sqft", "lft" (linear ft), "fixture", "each", "door", "window"
# costs: per-unit MATERIALS (low, high) and LABOR (low, high)
# numbers are ballpark placeholders for demo — replace as you gather better data.
# -----------------------
RENOVATION_DB = {
    "Bathroom": {
        "New prefabricated shower (kit)": {
            "unit": "each",
            "materials": (700, 1800),
            "labor": (1000, 2500),
            "notes": "Acrylic/fiberglass kit + basic plumbing tie-in."
        },
        "Custom tile shower (3x5 ft)": {
            "unit": "each",
            "materials": (1800, 4200),
            "labor": (2500, 6500),
            "notes": "Pan, waterproofing, tile, niche. Assumes existing drain location."
        },
        "Tub-to-shower conversion": {
            "unit": "each",
            "materials": (1200, 3000),
            "labor": (2200, 5500),
            "notes": "Remove tub, install shower base/walls, modest plumbing move."
        },
        "Vanity replacement (48 in)": {
            "unit": "each",
            "materials": (400, 1600),
            "labor": (250, 650),
            "notes": "Vanity + top + faucet swap; excludes major plumbing rework."
        },
        "Toilet replacement": {
            "unit": "fixture",
            "materials": (150, 450),
            "labor": (150, 350),
            "notes": "Standard toilet swap with wax ring and supply line."
        },
        "Tile floor (bath)": {
            "unit": "sqft",
            "materials": (3.5, 8.0),
            "labor": (6.0, 12.0),
            "notes": "Thinset, tile, grout; includes surface prep allowance."
        },
    },
    "Kitchen": {
        "Cabinet refacing (10x10 footprint)": {
            "unit": "each",
            "materials": (2000, 5000),
            "labor": (2500, 6000),
            "notes": "New doors/drawers/veneers; keeps boxes."
        },
        "New cabinets (linear)": {
            "unit": "lft",
            "materials": (120, 350),
            "labor": (150, 350),
            "notes": "Box + fronts + hardware per linear foot; hanging/install."
        },
        "Countertops (quartz)": {
            "unit": "sqft",
            "materials": (40, 95),
            "labor": (25, 45),
            "notes": "Includes templating and install; undermount sink cutout extra."
        },
        "Backsplash (tile)": {
            "unit": "sqft",
            "materials": (4, 12),
            "labor": (10, 22),
            "notes": "Tile + thinset + grout; simple layout."
        },
        "Appliance swap (per unit)": {
            "unit": "each",
            "materials": (600, 1800),
            "labor": (120, 300),
            "notes": "Delivery, haul-away, install. Gas range add-on may apply."
        },
        "LVP flooring (kitchen)": {
            "unit": "sqft",
            "materials": (2.0, 4.5),
            "labor": (2.0, 3.5),
            "notes": "Click-lock LVP + underlayment, simple layout."
        },
    },
    "Flooring": {
        "LVP (whole home)": {
            "unit": "sqft",
            "materials": (1.8, 4.0),
            "labor": (1.8, 3.2),
            "notes": "Baseboards/trim add-ons not included."
        },
        "Carpet (with pad)": {
            "unit": "sqft",
            "materials": (1.5, 3.0),
            "labor": (0.8, 1.8),
            "notes": "Includes removal/haul-away allowance."
        },
        "Hardwood refinish": {
            "unit": "sqft",
            "materials": (1.0, 2.0),
            "labor": (3.0, 5.5),
            "notes": "Sand, stain, 2–3 coats; repairs extra."
        },
    },
    "Interior Paint": {
        "Walls + ceiling (per room ~12x12)": {
            "unit": "each",
            "materials": (50, 140),
            "labor": (250, 600),
            "notes": "Minor patching; includes tape and plastic."
        },
        "Trim/doors (per door)": {
            "unit": "door",
            "materials": (10, 25),
            "labor": (60, 140),
            "notes": "Door + casing both sides."
        },
    },
    "Exterior Paint": {
        "Full house repaint (per sqft living area)": {
            "unit": "sqft",
            "materials": (0.9, 1.8),
            "labor": (1.8, 3.8),
            "notes": "Two coats; scraping/repair extra. Uses living sqft as proxy."
        },
    },
    "Windows & Doors": {
        "Vinyl window replacement": {
            "unit": "window",
            "materials": (180, 420),
            "labor": (160, 380),
            "notes": "Retrofit install; custom sizes or capping extra."
        },
        "Entry door replacement": {
            "unit": "door",
            "materials": (250, 800),
            "labor": (220, 520),
            "notes": "Prehung; lockset extra if upgraded."
        },
        "Patio slider replacement": {
            "unit": "door",
            "materials": (450, 1200),
            "labor": (350, 800),
            "notes": "Standard 2-panel slider; disposal included."
        },
    },
    "Roofing": {
        "Asphalt shingle reroof": {
            "unit": "sqft",
            "materials": (1.8, 3.5),
            "labor": (2.2, 4.0),
            "notes": "Tear-off + underlayment; per roof sqft (approx. 1.2x living sqft)."
        },
    },
    "Small Electrical": {
        "Add standard circuit (incl. 4 outlets)": {
            "unit": "each",
            "materials": (120, 240),
            "labor": (800, 1600),
            "notes": "Assumes panel capacity available."
        },
        "Recessed lights (per can)": {
            "unit": "each",
            "materials": (25, 65),
            "labor": (90, 220),
            "notes": "IC-rated LED; attic access assumed."
        },
    },
    "Exterior (Gutters)": {
        "Seamless aluminum gutters": {
            "unit": "lft",
            "materials": (2.5, 5.0),
            "labor": (3.0, 6.0),
            "notes": "Downspouts included; gutter guards extra."
        },
        "Gutter guards": {
            "unit": "lft",
            "materials": (3.0, 8.0),
            "labor": (2.0, 5.0),
            "notes": "Price varies widely by brand/profile."
        },
    },
}

# -----------------------
# Helpers
# -----------------------
def calc_cost(unit, qty, materials_range, labor_range, region_mult, finish_mult):
    # Apply multipliers (finish impacts materials more)
    materials_lo = materials_range[0] * finish_mult * region_mult
    materials_hi = materials_range[1] * finish_mult * region_mult
    labor_lo = labor_range[0] * region_mult
    labor_hi = labor_range[1] * region_mult

    total_lo = qty * (materials_lo + labor_lo)
    total_hi = qty * (materials_hi + labor_hi)
    return {
        "Materials Low": round(qty * materials_lo, 2),
        "Materials High": round(qty * materials_hi, 2),
        "Labor Low": round(qty * labor_lo, 2),
        "Labor High": round(qty * labor_hi, 2),
        "Total Low": round(total_lo, 2),
        "Total High": round(total_hi, 2),
    }

def unit_label(u):
    return {
        "sqft": "Square feet",
        "lft": "Linear feet",
        "fixture": "Fixtures",
        "each": "Quantity",
        "door": "Doors",
        "window": "Windows",
    }.get(u, "Quantity")

# -----------------------
# UI – left: selectors; right: results
# -----------------------
st.title("🏠 Renovation Cost Estimator (MVP)")
st.caption("Pick a renovation → get ballpark **materials + labor** ranges with **region** and **finish** multipliers. National providers are suggested for quick contact.")

colL, colR = st.columns([5, 7], gap="large")

with colL:
    st.subheader("1) Choose renovation")
    top = st.selectbox("Category", list(RENOVATION_DB.keys()), index=0)
    sub = st.selectbox("Scope", list(RENOVATION_DB[top].keys()), index=0)

    scope = RENOVATION_DB[top][sub]
    u = scope["unit"]

    st.subheader("2) Quantities & options")
    # Quantity input tailored to unit
    default_qty = {
        "sqft": 150,
        "lft": 40,
        "each": 1,
        "fixture": 1,
        "door": 1,
        "window": 8,
    }.get(u, 1)

    qty = st.number_input(unit_label(u), min_value=1.0 if u in ("sqft","lft") else 1, value=float(default_qty) if u in ("sqft","lft") else int(default_qty), step=1.0 if u in ("sqft","lft") else 1, format="%.0f" if u not in ("sqft","lft") else "%.0f")
    region = st.selectbox("Region", list(REGION_MULT.keys()), index=0)
    finish = st.selectbox("Finish level", list(FINISH_MULT.keys()), index=1)
    st.caption(f"Notes: {scope.get('notes','—')}")

    if st.button("Estimate"):
        st.session_state["do_est"] = True
    else:
        st.session_state["do_est"] = st.session_state.get("do_est", False)

with colR:
    st.subheader("Results")
    if st.session_state.get("do_est"):
        res = calc_cost(
            unit=u,
            qty=float(qty),
            materials_range=scope["materials"],
            labor_range=scope["labor"],
            region_mult=REGION_MULT[region],
            finish_mult=FINISH_MULT[finish],
        )
        # Table
        df = pd.DataFrame(
            [
                ["Materials", res["Materials Low"], res["Materials High"]],
                ["Labor", res["Labor Low"], res["Labor High"]],
                ["TOTAL", res["Total Low"], res["Total High"]],
            ],
            columns=["Component", "Low ($)", "High ($)"]
        )
        st.dataframe(df, use_container_width=True)

        # Quick context
        st.markdown(
            f"""
**Scope**: *{top} → {sub}*  
**Unit**: {unit_label(u)} • **Qty**: {int(qty) if u not in ('sqft','lft') else int(qty)}  
**Region**: {region} (×{REGION_MULT[region]:.2f}) • **Finish**: {finish} (×{FINISH_MULT[finish]:.2f} on materials)
"""
        )

        # CSV download
        out = pd.DataFrame([{
            "Category": top,
            "Scope": sub,
            "Unit": unit_label(u),
            "Quantity": qty,
            "Region": region,
            "Finish": finish,
            **res
        }])
        st.download_button(
            "⬇️ Download estimate (CSV)",
            data=out.to_csv(index=False).encode("utf-8"),
            file_name="renovation_estimate.csv",
            mime="text/csv",
        )

        # Providers
        st.markdown("### National Providers (shortlist)")
        providers = [p for p, cats in PROVIDERS.items() if any(cat in top for cat in cats)]
        if not providers:
            # Fallback by broad mapping
            providers = [p for p, cats in PROVIDERS.items() if top.split()[0] in " ".join(cats)]
        if providers:
            prov_df = pd.DataFrame({"Provider": providers, "Likely Service Category": top})
            st.dataframe(prov_df, use_container_width=True)
            st.caption("Tip: in a production app, link each provider to its service landing page or affiliate flow.")
        else:
            st.info("No national providers listed for this category yet. Add them in the PROVIDERS mapping.")

st.markdown("---")
with st.expander("How to extend this"):
    st.markdown(
        """
- Replace **RENOVATION_DB** numbers with researched unit costs (RSMeans-like) or your own dataset.
- For kitchens/baths, add toggles for **finish level** items (stone vs. laminate, frameless vs. framed).
- Add **contingency** (%) to totals and a **confidence** score (High/Med/Low).
- Let users bundle scopes (e.g., tile floor + vanity + toilet) and see a combined total with line items.
- Wire a **lead form** to route scope + contact to a provider (or to your ops inbox during the hackathon).
- Later, fuse in live pricing from big-box APIs/affiliate feeds if available.
"""
    )