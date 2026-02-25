import streamlit as st
import pandas as pd
import io
import math

# --- App Configuration ---
st.set_page_config(page_title="CR13 Voltage Drop Suite", layout="wide")
st.title("⚡ Station CR13: Voltage Drop Analysis Suite")

# --- Cable Reference Library (Cu/XLPE/LSZH) ---
CABLE_LIBRARY = {
    "Size (mm²)": [50, 70, 95, 120, 150, 185, 240, 300, 400, 500, 630],
    "mV/A/m": [0.860, 0.600, 0.440, 0.350, 0.290, 0.240, 0.190, 0.160, 0.140, 0.120, 0.100],
    # Approx overall diameter (mm) for single-core LV cable
    "Diameter (mm)": [14, 16, 19, 21, 23, 26, 30, 34, 39, 44, 49],
    # Approx weight per km (kg/km) for single-core copper cable (approx)
    "Weight (kg/km)": [600, 800, 1100, 1400, 1700, 2100, 2800, 3500, 4500, 5600, 7000]
}
df_lib = pd.DataFrame(CABLE_LIBRARY)

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Multi‑Connection Manager",
    "🔌 Transformer Feeder Audit (Single)",
    "📊 Transformer Feeders (from Image)",
    "🚀 Busduct vs Cable Comparison"
])

# ===============================
# (Tabs 1,2,3 remain exactly as before – code omitted for brevity)
# ===============================
# ... (insert the existing code for tab1, tab2, tab3 here) ...
# For the full merged code, please see the previous assistant messages.
# We will now add tab4.

# ===============================
# TAB 4: Busduct vs Cable Comparison
# ===============================
with tab4:
    st.subheader("Busduct vs. Multiple Parallel Cables")
    st.markdown("""
    When a large number of parallel cables are required (e.g., 15 runs per phase), 
    a busduct system often becomes more space‑efficient, easier to install, and 
    offers lower electrical losses. This tool compares the physical and electrical 
    characteristics of both options.
    """)

    col1, col2, col3 = st.columns(3)
    with col1:
        num_parallel = st.number_input("Parallel runs per phase", min_value=1, value=15, step=1)
        cable_size = st.selectbox("Cable size (mm²)", options=df_lib["Size (mm²)"].tolist(), index=len(df_lib)-1)
    with col2:
        length = st.number_input("Route length (m)", min_value=1, value=291, step=1)
        load_kw = st.number_input("Total load (kW)", min_value=0.0, value=2333.0, step=10.0)
    with col3:
        pf = st.number_input("Power factor", min_value=0.8, max_value=1.0, value=0.85, step=0.01)
        voltage = st.selectbox("System voltage (V)", [415, 400, 230], index=0)

    # Look up cable properties
    cable_row = df_lib[df_lib["Size (mm²)"] == cable_size].iloc[0]
    diam = cable_row["Diameter (mm)"]
    weight_kg_per_m = cable_row["Weight (kg/km)"] / 1000   # kg/m per core
    mv_am = cable_row["mV/A/m"]

    # Number of single cores (3 phases * parallel runs)
    total_cores = 3 * num_parallel

    # --- Space calculation ---
    # Assume single layer per tray – required width
    tray_width_mm = total_cores * diam
    # Check if exceeds typical max tray width (say 900mm)
    standard_tray_max = 900
    exceeds_tray = tray_width_mm > standard_tray_max

    # --- Weight calculation ---
    total_weight_kg = total_cores * weight_kg_per_m * length

    # --- Ampacity derating (simplified) ---
    # Rough derating factor based on number of layers. Assume single layer if width < 900, else multiple layers.
    if exceeds_tray:
        # Likely 2 layers
        derating_factor = 0.8   # typical for 2 layers
        layers = 2
    else:
        derating_factor = 1.0
        layers = 1

    # Total current
    ib_total = (load_kw * 1000) / (math.sqrt(3) * voltage * pf)
    # Required ampacity per core (before derating) = ib_total / num_parallel
    req_ampacity_per_core = ib_total / num_parallel
    # Derated ampacity needed = req_ampacity_per_core / derating_factor
    # (this would require a larger cable if derating is severe)

    # Voltage drop (without derating, for information)
    v_drop_perc = (mv_am * ib_total * length) / (1000 * num_parallel * voltage) * 100

    # --- Busduct comparison (estimated values) ---
    # Busduct typical width for same current: assume 1/3 of cable tray width
    busduct_width_mm = tray_width_mm / 3
    # Busduct weight approx 30% of cable weight
    busduct_weight_kg = total_weight_kg * 0.3
    # Power loss reduction: busduct typically 30% lower losses
    loss_reduction_pct = 30
    # Installation time: cables take 3x longer (estimate)
    install_time_factor = 3

    st.divider()
    st.subheader("📐 Space & Weight Analysis")

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Total cores", f"{total_cores}")
    col_b.metric("Required tray width", f"{tray_width_mm:.0f} mm", 
                 delta="Exceeds 900mm" if exceeds_tray else "Within limits")
    col_c.metric("Total cable weight", f"{total_weight_kg:.0f} kg")

    st.info(f"**Ampacity derating:** Due to {layers} layer{'s' if layers>1 else ''}, "
            f"a derating factor of {derating_factor:.1f} applies. "
            f"Each core must be sized for {req_ampacity_per_core/derating_factor:.0f} A "
            f"(instead of {req_ampacity_per_core:.0f} A) – this may require a larger cable.")

    st.subheader("⚡ Busduct Alternative")
    st.markdown(f"""
    * **Space saving:** Busduct width approx **{busduct_width_mm:.0f} mm** (vs. {tray_width_mm:.0f} mm for cables).
    * **Weight saving:** Busduct weight approx **{busduct_weight_kg:.0f} kg** (vs. {total_weight_kg:.0f} kg for cables).
    * **Lower losses:** Busduct typically has **30% lower power losses** – significant energy savings over time.
    * **Installation time:** Busduct can be installed in about **1/{install_time_factor} the time** of pulling and terminating 45 cables.
    * **Maintenance:** Simple annual IR scanning vs. difficult fault location in cables.
    * **Flexibility:** Easy to add tap‑offs with plug‑in units.
    """)

    st.subheader("📊 Comparison Summary")
    comparison_data = {
        "Parameter": [
            "Required width (mm)",
            "Total weight (kg)",
            "Voltage drop (%)",
            "Installation time factor",
            "Power loss (relative)",
            "Maintenance effort"
        ],
        "Cables (15 runs)": [
            f"{tray_width_mm:.0f}",
            f"{total_weight_kg:.0f}",
            f"{v_drop_perc:.2f}",
            "3 (baseline)",
            "1.0 (baseline)",
            "High"
        ],
        "Busduct": [
            f"{busduct_width_mm:.0f}",
            f"{busduct_weight_kg:.0f}",
            f"{v_drop_perc*0.7:.2f} (approx)",
            "1",
            "0.7",
            "Low"
        ]
    }
    df_compare = pd.DataFrame(comparison_data)
    st.table(df_compare)

    # --- Excel Export ---
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book

        # Sheet 1: Inputs and calculations
        calc_data = {
            "Parameter": [
                "Parallel runs per phase",
                "Cable size (mm²)",
                "Route length (m)",
                "Total load (kW)",
                "Power factor",
                "Voltage (V)",
                "Total current (A)",
                "Voltage drop (%)",
                "Cable diameter (mm)",
                "Total cores",
                "Required tray width (mm)",
                "Exceeds standard tray?",
                "Estimated layers",
                "Derating factor",
                "Total cable weight (kg)",
                "Busduct width (mm)",
                "Busduct weight (kg)",
                "Busduct loss factor"
            ],
            "Value": [
                num_parallel,
                cable_size,
                length,
                load_kw,
                pf,
                voltage,
                f"{ib_total:.1f}",
                f"{v_drop_perc:.2f}",
                diam,
                total_cores,
                f"{tray_width_mm:.0f}",
                "Yes" if exceeds_tray else "No",
                layers,
                derating_factor,
                f"{total_weight_kg:.0f}",
                f"{busduct_width_mm:.0f}",
                f"{busduct_weight_kg:.0f}",
                "0.7"
            ]
        }
        df_calc = pd.DataFrame(calc_data)
        df_calc.to_excel(writer, sheet_name='Calculations', index=False)

        # Sheet 2: Comparison table
        df_compare.to_excel(writer, sheet_name='Comparison', index=False)

        # Adjust column widths
        for sheet in ['Calculations', 'Comparison']:
            worksheet = writer.sheets[sheet]
            worksheet.set_column(0, 1, 30)

    st.download_button(
        label="📥 Download Busduct vs Cable Report",
        data=output.getvalue(),
        file_name="Busduct_vs_Cable_Comparison.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
