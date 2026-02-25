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
    # Approx overall diameter (mm) for single-core LV cable (for busduct tab)
    "Diameter (mm)": [14, 16, 19, 21, 23, 26, 30, 34, 39, 44, 49],
    # Approx weight per km (kg/km) for single-core copper cable
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
# TAB 1: Multi‑Connection Manager (with parallel runs, connected load & max demand)
# ===============================
with tab1:
    st.subheader("Multi‑Connection Voltage Drop Verification")
    st.markdown("""
    Verify multiple connections against the design limits in **PC1009CR13-ELS2101-**. 
    * **Tie Cables:** Limit is **2.0%**.
    * **Sub-Feeder:** Limit is **1.0% - 3.0%** (refer to schematic).
    """)

    # --- Initial Data with Connected Load and Max Demand ---
    default_data = [
        {"Connection": "Tie Cable 1", "Source": "MSB01", "Destination": "MSB03",
         "Connected Load (kW)": 362.10, "Max Demand (kW)": 362.10,
         "Length (m)": 55.0, "Parallel Runs": 1, "Limit (%)": 2.0, "Cable Size": 300},
        {"Connection": "Tie Cable 2", "Source": "MSB04", "Destination": "MSB02",
         "Connected Load (kW)": 255.00, "Max Demand (kW)": 255.00,
         "Length (m)": 40.0, "Parallel Runs": 1, "Limit (%)": 2.0, "Cable Size": 185},
        {"Connection": "Essential Feeder", "Source": "MSB02", "Destination": "EPSBC51",
         "Connected Load (kW)": 47.06, "Max Demand (kW)": 47.06,
         "Length (m)": 80.0, "Parallel Runs": 1, "Limit (%)": 1.0, "Cable Size": 70},
    ]

    st.info("💡 You can edit cells directly or click '+' at the bottom to add new rows. 'Parallel Runs' means number of cables per phase.")

    col_a, col_b = st.columns(2)
    pf_t1 = col_a.slider("Station Power Factor (cos φ)", 0.8, 1.0, 0.85, key="pf_t1")
    voltage_t1 = col_b.selectbox("System Voltage (V)", [415, 400, 230], index=0, key="v_t1")

    edited_df = st.data_editor(
        pd.DataFrame(default_data),
        num_rows="dynamic",
        column_config={
            "Cable Size": st.column_config.SelectboxColumn(options=df_lib["Size (mm²)"].tolist()),
            "Parallel Runs": st.column_config.NumberColumn(min_value=1, step=1)
        },
        use_container_width=True
    )

    # --- Calculation Logic using Max Demand ---
    def calculate_metrics(row):
        # Total current based on Max Demand
        ib_total = (row["Max Demand (kW)"] * 1000) / (math.sqrt(3) * voltage_t1 * pf_t1)
        # Current per cable (for drop calculation)
        ib_per_cable = ib_total / row["Parallel Runs"]
        # Lookup mV/A/m
        mv_am = df_lib.loc[df_lib["Size (mm²)"] == row["Cable Size"], "mV/A/m"].values[0]
        # Voltage drop per cable (same as total drop)
        drop_v = (mv_am * ib_per_cable * row["Length (m)"]) / 1000
        drop_perc = (drop_v / voltage_t1) * 100

        # Suggestion: required parallel runs with same cable
        required_parallel = math.ceil((mv_am * ib_total * row["Length (m)"] * 100) / (1000 * voltage_t1 * row["Limit (%)"]))
        # Find smallest cable that works with current parallel runs
        suitable = df_lib[((df_lib["mV/A/m"] * ib_total * row["Length (m)"]) / (1000 * row["Parallel Runs"] * voltage_t1) * 100) <= row["Limit (%)"]]
        if not suitable.empty:
            rec_size = suitable["Size (mm²)"].iloc[0]
        else:
            rec_size = "Parallel Required"
        suggestion = f"Need {required_parallel} runs or upgrade to {rec_size} mm²"

        return pd.Series([round(ib_total, 2), round(drop_perc, 3), suggestion])

    if not edited_df.empty:
        # Apply calculations
        edited_df[["Current (A)", "Actual Drop (%)", "Suggestion"]] = edited_df.apply(calculate_metrics, axis=1)
        edited_df["Status"] = edited_df.apply(lambda x: "✅ PASS" if x["Actual Drop (%)"] <= x["Limit (%)"] else "❌ FAIL", axis=1)

        # Display with conditional formatting
        st.dataframe(edited_df.style.applymap(
            lambda x: 'background-color: #ffcccc' if x == "❌ FAIL" else ('background-color: #ccffcc' if x == "✅ PASS" else ''),
            subset=['Status']
        ), use_container_width=True)

        # --- Excel Export with Formulas (including Connected Load and Max Demand) ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            edited_df.to_excel(writer, sheet_name='Verification_Values', index=False)

            worksheet = workbook.add_worksheet('Verification_Formulas')
            writer.sheets['Verification_Formulas'] = worksheet

            worksheet.write('A1', 'Voltage (V):')
            worksheet.write('B1', voltage_t1)
            worksheet.write('A2', 'Power Factor:')
            worksheet.write('B2', pf_t1)

            # Headers: first 9 columns are inputs (Connection, Source, Destination, Connected Load, Max Demand, Length, Parallel Runs, Limit, Cable Size)
            headers = list(edited_df.columns[:9]) + ['Current (A) [formula]', 'Actual Drop (%) [formula]', 'Status [formula]', 'Suggestion (from app)']
            for col_num, header in enumerate(headers):
                worksheet.write(3, col_num, header)

            # Write input data (first 9 columns) starting from row 4
            for r in range(len(edited_df)):
                for c in range(9):
                    worksheet.write(r+4, c, edited_df.iloc[r, c])

            # Cable library in columns M:N
            worksheet.write('M1', 'Cable Size (mm²)')
            worksheet.write('N1', 'mV/A/m')
            for i, size in enumerate(df_lib['Size (mm²)']):
                worksheet.write(i+1, 12, size)
                worksheet.write(i+1, 13, df_lib['mV/A/m'][i])

            for r in range(len(edited_df)):
                row_excel = r + 5
                # Current formula: = (Max Demand *1000)/(SQRT(3)*$B$1*$B$2)   Max Demand is column E (index 4)
                current_formula = f'=(E{row_excel}*1000)/(SQRT(3)*$B$1*$B$2)'
                worksheet.write_formula(r+4, 9, current_formula)   # column J (index 9)

                # Drop % formula: = ((VLOOKUP(Irow, $M:$N, 2, FALSE) * Jrow * Frow) / (1000 * Grow)) / B1 * 100
                # I = Cable Size (col 8), J = Current (col 9), F = Length (col 5), G = Parallel Runs (col 6)
                drop_formula = f'=((VLOOKUP(I{row_excel},$M:$N,2,FALSE)*J{row_excel}*F{row_excel})/(1000*G{row_excel}))/B1*100'
                worksheet.write_formula(r+4, 10, drop_formula)      # column K (index 10)

                # Status formula: = IF(Krow <= Hrow, "✅ PASS", "❌ FAIL")   H = Limit (col 7)
                status_formula = f'=IF(K{row_excel}<=H{row_excel},"✅ PASS","❌ FAIL")'
                worksheet.write_formula(r+4, 11, status_formula)    # column L (index 11)

                # Suggestion (static from app)
                worksheet.write(r+4, 12, edited_df.iloc[r, 11])     # column M (index 12)

            worksheet.set_column(0, 12, 18)

        st.download_button(
            label="📥 Download Multi‑Connection Excel Report (with formulas)",
            data=output.getvalue(),
            file_name="Station_CR13_Multi_Connection_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("Please add at least one connection to see the analysis.")

    st.divider()
    st.subheader("🛠 Technical Recommendations for Compliance")
    st.markdown("""
    If a tie cable is failing the **2.0% limit**, consider:
    1. **Increasing parallel runs** (use multiple cables per phase).
    2. **Upsizing the cable** to a larger cross‑section.
    3. **Combining both** – the suggestion column gives you the minimum requirement.
    Always specify **Copper (Cu) XLPE/SWA/LSZH** for high-load tie connections.
    """)

# ===============================
# TAB 2: Transformer Feeder Audit (Single) – with Connected Load and Max Demand
# ===============================
with tab2:
    st.subheader("Transformer to MSB: Single Feeder Audit")
    st.info(f"Analysis for a single transformer feeder (e.g., emergency load over 291 m).")

    # --- Engineering Constants (simplified) ---
    CABLE_REF = {300: 0.160, 400: 0.140, 500: 0.120, 630: 0.100}

    col1, col2 = st.columns(2)
    with col1:
        connected_load = st.number_input("Connected Load (kW)", value=2500.0, key="conn_load")
        max_demand = st.number_input("Max Demand (kW)", value=2333.0, key="max_demand")
        length = st.number_input("Cable Distance (m)", value=291.0, key="length")
    with col2:
        pf_t2 = st.number_input("Power Factor", value=0.85, key="pf_t2")
        voltage_t2 = st.selectbox("System Voltage (V)", [415, 400, 230], index=0, key="v_t2")
        parallel_runs = st.number_input("Number of Parallel Runs (per phase)", min_value=1, value=10, key="parallel")
        selected_size = st.selectbox("Cable Size (mm²)", list(CABLE_REF.keys()), index=3, key="size")

    # --- Calculations using Max Demand ---
    ib_total = (max_demand * 1000) / (math.sqrt(3) * voltage_t2 * pf_t2)
    ib_per_cable = ib_total / parallel_runs
    mv_am = CABLE_REF[selected_size]
    v_drop_volts = (mv_am * ib_per_cable * length) / 1000
    v_drop_perc = (v_drop_volts / voltage_t2) * 100

    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Current ($I_b$)", f"{ib_total:.2f} A")
    c2.metric("Current per Cable", f"{ib_per_cable:.2f} A")
    c3.metric("Voltage Drop", f"{v_drop_perc:.2f}%")
    c4.metric("Status", "❌ FAIL" if v_drop_perc > 2.0 else "✅ PASS")

    if v_drop_perc > 2.0:
        st.error(f"Exceeds 2.0% limit by {(v_drop_perc - 2.0):.2f}%. Increase parallel runs or cable size.")
    else:
        st.success("Configuration meets the design criteria.")

    # --- Excel Export for the Audit (with formulas) ---
    def export_audit():
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            summary = pd.DataFrame([{
                "Description": "Transformer to MSB Tie",
                "Connected Load (kW)": connected_load,
                "Max Demand (kW)": max_demand,
                "Distance (m)": length,
                "Cables per Phase": parallel_runs,
                "Size (mm²)": selected_size,
                "Target Limit (%)": 2.0
            }])
            summary.to_excel(writer, index=False, sheet_name='Audit')
            ws = writer.sheets['Audit']

            def xlsx_col(idx):
                return chr(65 + idx)

            ws.write(0, 7, "Calculated Ib (A)")
            # Use Max Demand (column C) for current
            ws.write_formula(1, 7, f"=(C2*1000)/(1.732*{voltage_t2}*{pf_t2})")

            ws.write(0, 8, "Actual Drop (%)")
            # Drop formula: ((mV * (Ib / parallel) * length) / 1000) / V * 100
            ws.write_formula(1, 8, f"=(({mv_am}*(H2/D2)*B2)/1000)/{voltage_t2}*100")

        return output.getvalue()

    st.download_button(
        label="📥 Download Transformer Audit Excel (with formulas)",
        data=export_audit(),
        file_name="Transformer_Feeder_Audit.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ===============================
# TAB 3: Transformer Feeders (from Image) – with Connected Load and Max Demand
# ===============================
with tab3:
    st.subheader("Transformer to MSB Feeders (from CR13 Image)")
    st.info("""
    Based on the attached image: two transformers TX‑1 and TX‑2 feeding MSB‑01 and MSB‑02 with **8×4×630 mm²** cables over **291 m**.  
    The table below includes both Connected Load and Max Demand as per the image data.
    """)

    # Default data from image (Connected Load = first number, Max Demand = second number)
    default_transformer_data = [
        {"Transformer": "TX-1", "MSB": "MSB-01",
         "Connected Load (kW)": 2363, "Max Demand (kW)": 1907,
         "Length (m)": 291, "Parallel Runs": 2, "Cable Size": 630, "Limit (%)": 2.0},
        {"Transformer": "TX-2", "MSB": "MSB-02",
         "Connected Load (kW)": 2485, "Max Demand (kW)": 2333,
         "Length (m)": 291, "Parallel Runs": 2, "Cable Size": 630, "Limit (%)": 2.0},
    ]

    col1, col2 = st.columns(2)
    pf_t3 = col1.slider("Power Factor", 0.8, 1.0, 0.85, key="pf_t3")
    voltage_t3 = col2.selectbox("System Voltage (V)", [415, 400, 230], index=0, key="v_t3")

    edited_t3_df = st.data_editor(
        pd.DataFrame(default_transformer_data),
        num_rows="dynamic",
        column_config={
            "Cable Size": st.column_config.SelectboxColumn(options=df_lib["Size (mm²)"].tolist())
        },
        use_container_width=True
    )

    if not edited_t3_df.empty:
        # Calculation for each row using Max Demand
        def calc_t3(row):
            total_current = (row["Max Demand (kW)"] * 1000) / (math.sqrt(3) * voltage_t3 * pf_t3)
            mv_am = df_lib.loc[df_lib["Size (mm²)"] == row["Cable Size"], "mV/A/m"].values[0]
            # drop volts = (mV/A/m * total_current * length) / (1000 * parallel_runs)
            drop_v = (mv_am * total_current * row["Length (m)"]) / (1000 * row["Parallel Runs"])
            drop_perc = (drop_v / voltage_t3) * 100
            status = "✅ PASS" if drop_perc <= row["Limit (%)"] else "❌ FAIL"

            # Suggestion: required parallel runs with same cable
            required_N = math.ceil((mv_am * total_current * row["Length (m)"] * 100) / (1000 * voltage_t3 * row["Limit (%)"]))
            # Find smallest cable that works with current parallel runs
            suitable = df_lib[((df_lib["mV/A/m"] * total_current * row["Length (m)"]) / (1000 * row["Parallel Runs"] * voltage_t3) * 100) <= row["Limit (%)"]]
            rec_size = suitable["Size (mm²)"].iloc[0] if not suitable.empty else "Parallel Required"
            suggestion = f"Need {required_N} parallel runs or upgrade to {rec_size} mm²"
            return pd.Series([round(total_current, 2), round(drop_perc, 3), status, suggestion])

        edited_t3_df[["Total Current (A)", "Drop (%)", "Status", "Suggestion"]] = edited_t3_df.apply(calc_t3, axis=1)

        # Display with conditional formatting
        st.dataframe(edited_t3_df.style.applymap(
            lambda x: 'background-color: #ffcccc' if x == "❌ FAIL" else ('background-color: #ccffcc' if x == "✅ PASS" else ''),
            subset=['Status']
        ), use_container_width=True)

        # --- Excel Export with Formulas ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            edited_t3_df.to_excel(writer, sheet_name='Transformer_Feeders_Values', index=False)

            worksheet = workbook.add_worksheet('Formulas')
            writer.sheets['Formulas'] = worksheet

            worksheet.write('A1', 'Voltage (V):')
            worksheet.write('B1', voltage_t3)
            worksheet.write('A2', 'Power Factor:')
            worksheet.write('B2', pf_t3)

            # Headers: first 8 columns are inputs (Transformer, MSB, Connected Load, Max Demand, Length, Parallel Runs, Cable Size, Limit)
            headers = list(edited_t3_df.columns[:8]) + ['Total Current (A) [formula]', 'Drop (%) [formula]', 'Status [formula]', 'Suggestion (from app)']
            for col_num, header in enumerate(headers):
                worksheet.write(3, col_num, header)

            for r in range(len(edited_t3_df)):
                for c in range(8):
                    worksheet.write(r+4, c, edited_t3_df.iloc[r, c])

            # Cable library in columns M:N
            worksheet.write('M1', 'Cable Size (mm²)')
            worksheet.write('N1', 'mV/A/m')
            for i, size in enumerate(df_lib['Size (mm²)']):
                worksheet.write(i+1, 12, size)
                worksheet.write(i+1, 13, df_lib['mV/A/m'][i])

            for r in range(len(edited_t3_df)):
                row_excel = r + 5
                # Total current formula: = (Max Demand *1000)/(SQRT(3)*$B$1*$B$2)   Max Demand is column D (index 3)
                current_formula = f'=(D{row_excel}*1000)/(SQRT(3)*$B$1*$B$2)'
                worksheet.write_formula(r+4, 8, current_formula)   # column I (index 8)

                # Drop % formula: = ((VLOOKUP(Grow, $M:$N, 2, FALSE) * Irow * Erow) / (1000 * Frow)) / B1 * 100
                # G = Cable Size (col 6), I = Current (col 8), E = Length (col 4), F = Parallel Runs (col 5)
                drop_formula = f'=((VLOOKUP(G{row_excel},$M:$N,2,FALSE)*I{row_excel}*E{row_excel})/(1000*F{row_excel}))/B1*100'
                worksheet.write_formula(r+4, 9, drop_formula)       # column J (index 9)

                status_formula = f'=IF(J{row_excel}<=H{row_excel},"✅ PASS","❌ FAIL")'  # H = Limit (col 7)
                worksheet.write_formula(r+4, 10, status_formula)    # column K (index 10)

                worksheet.write(r+4, 11, edited_t3_df.iloc[r, 10])  # Suggestion static (col L)

            worksheet.set_column(0, 11, 18)

        st.download_button(
            label="📥 Download Transformer Feeders Excel Report (with formulas)",
            data=output.getvalue(),
            file_name="CR13_Transformer_Feeders_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("Add transformer feeders to analyze.")

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
