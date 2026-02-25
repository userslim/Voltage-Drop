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
    "mV/A/m": [0.860, 0.600, 0.440, 0.350, 0.290, 0.240, 0.190, 0.160, 0.140, 0.120, 0.100]
}
df_lib = pd.DataFrame(CABLE_LIBRARY)

# Create tabs
tab1, tab2, tab3 = st.tabs(["📋 Multi‑Connection Manager", "🔌 Transformer Feeder Audit (Single)", "📊 Transformer Feeders (from Image)"])

# ===============================
# TAB 1: Multi‑Connection Manager (with parallel runs)
# ===============================
with tab1:
    st.subheader("Multi‑Connection Voltage Drop Verification")
    st.markdown("""
    Verify multiple connections against the design limits in **PC1009CR13-ELS2101-**. 
    * **Tie Cables:** Limit is **2.0%**.
    * **Sub-Feeder:** Limit is **1.0% - 3.0%** (refer to schematic).
    """)

    # --- Initial Data from Load Schedules (now with Parallel Runs) ---
    default_data = [
        {"Connection": "Tie Cable 1", "Source": "MSB01", "Destination": "MSB03", "Load (kW)": 362.10, "Length (m)": 55.0, "Parallel Runs": 1, "Limit (%)": 2.0, "Cable Size": 300},
        {"Connection": "Tie Cable 2", "Source": "MSB04", "Destination": "MSB02", "Load (kW)": 255.00, "Length (m)": 40.0, "Parallel Runs": 1, "Limit (%)": 2.0, "Cable Size": 185},
        {"Connection": "Essential Feeder", "Source": "MSB02", "Destination": "EPSBC51", "Load (kW)": 47.06, "Length (m)": 80.0, "Parallel Runs": 1, "Limit (%)": 1.0, "Cable Size": 70},
    ]

    st.info("💡 You can edit cells directly or click '+' at the bottom to add new rows. 'Parallel Runs' means number of cables per phase.")

    col_a, col_b = st.columns(2)
    pf_t1 = col_a.slider("Station Power Factor (cos φ)", 0.8, 1.0, 0.85, key="pf_t1")
    voltage_t1 = col_b.selectbox("System Voltage (V)", [400, 230], index=0, key="v_t1")

    edited_df = st.data_editor(
        pd.DataFrame(default_data),
        num_rows="dynamic",
        column_config={
            "Cable Size": st.column_config.SelectboxColumn(options=df_lib["Size (mm²)"].tolist()),
            "Parallel Runs": st.column_config.NumberColumn(min_value=1, step=1)
        },
        use_container_width=True
    )

    # --- Calculation Logic with parallel runs ---
    def calculate_metrics(row):
        # Total current
        ib_total = (row["Load (kW)"] * 1000) / (math.sqrt(3) * voltage_t1 * pf_t1)
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

        # --- Excel Export with Formulas (including parallel runs) ---
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

            # Headers: first 8 columns are inputs (now including Parallel Runs)
            headers = list(edited_df.columns[:8]) + ['Current (A) [formula]', 'Actual Drop (%) [formula]', 'Status [formula]', 'Suggestion (from app)']
            for col_num, header in enumerate(headers):
                worksheet.write(3, col_num, header)

            # Write input data (first 8 columns) starting from row 4
            for r in range(len(edited_df)):
                for c in range(8):
                    worksheet.write(r+4, c, edited_df.iloc[r, c])

            # Cable library in columns M:N
            worksheet.write('M1', 'Cable Size (mm²)')
            worksheet.write('N1', 'mV/A/m')
            for i, size in enumerate(df_lib['Size (mm²)']):
                worksheet.write(i+1, 12, size)
                worksheet.write(i+1, 13, df_lib['mV/A/m'][i])

            for r in range(len(edited_df)):
                row_excel = r + 5
                # Current formula: = (Load*1000)/(SQRT(3)*Voltage*PF)   Load is column D (index 3)
                current_formula = f'=(D{row_excel}*1000)/(SQRT(3)*$B$1*$B$2)'
                worksheet.write_formula(r+4, 8, current_formula)   # column I (index 8)

                # Drop % formula: = ((VLOOKUP(Hrow, $M:$N, 2, FALSE) * Irow * Erow) / (1000 * Frow)) / B1 * 100
                # H = Cable Size (col 7), I = Current (col 8), E = Length (col 4), F = Parallel Runs (col 5)
                drop_formula = f'=((VLOOKUP(H{row_excel},$M:$N,2,FALSE)*I{row_excel}*E{row_excel})/(1000*F{row_excel}))/B1*100'
                worksheet.write_formula(r+4, 9, drop_formula)       # column J (index 9)

                # Status formula: = IF(Jrow <= Grow, "✅ PASS", "❌ FAIL")   G = Limit (col 6)
                status_formula = f'=IF(J{row_excel}<=G{row_excel},"✅ PASS","❌ FAIL")'
                worksheet.write_formula(r+4, 10, status_formula)    # column K (index 10)

                # Suggestion (static from app)
                worksheet.write(r+4, 11, edited_df.iloc[r, 10])     # column L (index 11)

            worksheet.set_column(0, 11, 18)

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
# TAB 2: Transformer Feeder Audit (Single)
# ===============================
with tab2:
    st.subheader("Transformer to MSB: Single Feeder Audit")
    st.info(f"Analysis for a single transformer feeder (e.g., emergency load over 291 m).")

    # --- Engineering Constants (simplified) ---
    CABLE_REF = {300: 0.160, 400: 0.140, 500: 0.120, 630: 0.100}

    col1, col2 = st.columns(2)
    with col1:
        load_kw = st.number_input("Maximum Demand (kW)", value=2333.0, key="load_kw")
        length = st.number_input("Cable Distance (m)", value=291.0, key="length")
    with col2:
        pf_t2 = st.number_input("Power Factor", value=0.85, key="pf_t2")
        voltage_t2 = 400  # fixed
        parallel_runs = st.number_input("Number of Parallel Runs (per phase)", min_value=1, value=10, key="parallel")
        selected_size = st.selectbox("Cable Size (mm²)", list(CABLE_REF.keys()), index=3, key="size")

    # --- Calculations ---
    ib_total = (load_kw * 1000) / (math.sqrt(3) * voltage_t2 * pf_t2)
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
                "Demand (kW)": load_kw,
                "Distance (m)": length,
                "Cables per Phase": parallel_runs,
                "Size (mm²)": selected_size,
                "Target Limit (%)": 2.0
            }])
            summary.to_excel(writer, index=False, sheet_name='Audit')
            ws = writer.sheets['Audit']

            def xlsx_col(idx):
                return chr(65 + idx)

            ws.write(0, 6, "Calculated Ib (A)")
            ws.write_formula(1, 6, f"=({xlsx_col(1)}2*1000)/(1.732*{voltage_t2}*{pf_t2})")

            ws.write(0, 7, "Actual Drop (%)")
            ws.write_formula(1, 7, f"=(({mv_am}*(G2/{xlsx_col(3)}2)*{xlsx_col(2)}2)/1000)/{voltage_t2}*100")

        return output.getvalue()

    st.download_button(
        label="📥 Download Transformer Audit Excel (with formulas)",
        data=export_audit(),
        file_name="Transformer_Feeder_Audit.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ===============================
# TAB 3: Transformer Feeders (from Image)
# ===============================
with tab3:
    st.subheader("Transformer to MSB Feeders (from CR13 Image)")
    st.info("""
    Based on the attached image: two transformers TX‑1 and TX‑2 feeding MSB‑01 and MSB‑02 with **8×4×630 mm²** cables over **291 m**.  
    Edit the table below to adjust parameters. The cable library includes mV/A/m values for all standard sizes.
    """)

    # Default data from image (using emergency load values)
    default_transformer_data = [
        {"Transformer": "TX-1", "MSB": "MSB-01", "Load (kW)": 1907, "Length (m)": 291, "Parallel Runs": 2, "Cable Size": 630, "Limit (%)": 2.0},
        {"Transformer": "TX-2", "MSB": "MSB-02", "Load (kW)": 2333, "Length (m)": 291, "Parallel Runs": 2, "Cable Size": 630, "Limit (%)": 2.0},
    ]

    col1, col2 = st.columns(2)
    pf_t3 = col1.slider("Power Factor", 0.8, 1.0, 0.85, key="pf_t3")
    voltage_t3 = col2.selectbox("System Voltage (V)", [400, 230], index=0, key="v_t3")

    edited_t3_df = st.data_editor(
        pd.DataFrame(default_transformer_data),
        num_rows="dynamic",
        column_config={
            "Cable Size": st.column_config.SelectboxColumn(options=df_lib["Size (mm²)"].tolist())
        },
        use_container_width=True
    )

    if not edited_t3_df.empty:
        # Calculation for each row
        def calc_t3(row):
            total_current = (row["Load (kW)"] * 1000) / (math.sqrt(3) * voltage_t3 * pf_t3)
            mv_am = df_lib.loc[df_lib["Size (mm²)"] == row["Cable Size"], "mV/A/m"].values[0]
            # drop volts = (mV/A/m * total_current * length) / (1000 * parallel_runs)
            drop_v = (mv_am * total_current * row["Length (m)"]) / (1000 * row["Parallel Runs"])
            drop_perc = (drop_v / voltage_t3) * 100
            status = "✅ PASS" if drop_perc <= row["Limit (%)"] else "❌ FAIL"

            # Simple suggestion: required parallel runs to meet limit with same cable
            required_N = math.ceil((mv_am * total_current * row["Length (m)"] * 100) / (1000 * voltage_t3 * row["Limit (%)"]))
            # Also find smallest cable that works with current parallel runs
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

            # Headers: first 7 columns are inputs, then calculated
            headers = list(edited_t3_df.columns[:7]) + ['Total Current (A) [formula]', 'Drop (%) [formula]', 'Status [formula]', 'Suggestion (from app)']
            for col_num, header in enumerate(headers):
                worksheet.write(3, col_num, header)

            for r in range(len(edited_t3_df)):
                for c in range(7):
                    worksheet.write(r+4, c, edited_t3_df.iloc[r, c])

            # Cable library in columns M:N
            worksheet.write('M1', 'Cable Size (mm²)')
            worksheet.write('N1', 'mV/A/m')
            for i, size in enumerate(df_lib['Size (mm²)']):
                worksheet.write(i+1, 12, size)
                worksheet.write(i+1, 13, df_lib['mV/A/m'][i])

            for r in range(len(edited_t3_df)):
                row_excel = r + 5
                # Total current formula: = (C*1000)/(SQRT(3)*$B$1*$B$2) where C is Load (kW) column (index 2)
                current_formula = f'=(C{row_excel}*1000)/(SQRT(3)*$B$1*$B$2)'
                worksheet.write_formula(r+4, 7, current_formula)

                # Drop % formula: = ((VLOOKUP(Frow, $M:$N, 2, FALSE) * Hrow * Drow) / (1000 * Erow)) / B1 * 100
                # F = Cable Size, H = Total Current, D = Length, E = Parallel Runs
                drop_formula = f'=((VLOOKUP(F{row_excel},$M:$N,2,FALSE)*H{row_excel}*D{row_excel})/(1000*E{row_excel}))/B1*100'
                worksheet.write_formula(r+4, 8, drop_formula)

                status_formula = f'=IF(I{row_excel}<=G{row_excel},"✅ PASS","❌ FAIL")'  # G = Limit
                worksheet.write_formula(r+4, 9, status_formula)

                worksheet.write(r+4, 10, edited_t3_df.iloc[r, 10])  # Suggestion static

            worksheet.set_column(0, 10, 18)

        st.download_button(
            label="📥 Download Transformer Feeders Excel Report (with formulas)",
            data=output.getvalue(),
            file_name="CR13_Transformer_Feeders_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("Add transformer feeders to analyze.")
