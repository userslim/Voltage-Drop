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
tab1, tab2 = st.tabs(["📋 Multi‑Connection Manager", "🔌 Transformer Feeder Audit"])

# ===============================
# TAB 1: Original Multi‑Connection Manager
# ===============================
with tab1:
    st.subheader("Multi‑Connection Voltage Drop Verification")
    st.markdown("""
    Verify multiple connections against the design limits in **PC1009CR13-ELS2101-**. 
    * **Tie Cables:** Limit is **2.0%**.
    * **Sub-Feeder:** Limit is **1.0% - 3.0%** (refer to schematic).
    """)

    # --- Initial Data from Load Schedules ---
    default_data = [
        {"Connection": "Tie Cable 1", "Source": "MSB01", "Destination": "MSB03", "Load (kW)": 362.10, "Length (m)": 55.0, "Limit (%)": 2.0, "Cable Size": 300},
        {"Connection": "Tie Cable 2", "Source": "MSB04", "Destination": "MSB02", "Load (kW)": 255.00, "Length (m)": 40.0, "Limit (%)": 2.0, "Cable Size": 185},
        {"Connection": "Essential Feeder", "Source": "MSB02", "Destination": "EPSBC51", "Load (kW)": 47.06, "Length (m)": 80.0, "Limit (%)": 1.0, "Cable Size": 70},
    ]

    # --- Editable Table Interface ---
    st.info("💡 You can edit cells directly or click '+' at the bottom to add new rows.")

    col_a, col_b = st.columns(2)
    pf_t1 = col_a.slider("Station Power Factor (cos φ)", 0.8, 1.0, 0.85, key="pf_t1")
    voltage_t1 = col_b.selectbox("System Voltage (V)", [400, 230], index=0, key="v_t1")

    edited_df = st.data_editor(
        pd.DataFrame(default_data),
        num_rows="dynamic",
        column_config={
            "Cable Size": st.column_config.SelectboxColumn(options=df_lib["Size (mm²)"].tolist())
        },
        use_container_width=True
    )

    # --- Calculation Logic ---
    def calculate_metrics(row):
        ib = (row["Load (kW)"] * 1000) / (math.sqrt(3) * voltage_t1 * pf_t1)
        mv_am = df_lib.loc[df_lib["Size (mm²)"] == row["Cable Size"], "mV/A/m"].values[0]
        drop_v = (mv_am * ib * row["Length (m)"]) / 1000
        drop_perc = (drop_v / voltage_t1) * 100
        suitable_cables = df_lib[((df_lib["mV/A/m"] * ib * row["Length (m)"]) / 1000 / voltage_t1 * 100) <= row["Limit (%)"]]
        rec_size = suitable_cables["Size (mm²)"].iloc[0] if not suitable_cables.empty else "Parallel Required"
        return pd.Series([round(ib, 2), round(drop_perc, 3), rec_size])

    if not edited_df.empty:
        edited_df[["Current (A)", "Actual Drop (%)", "Suggested Size"]] = edited_df.apply(calculate_metrics, axis=1)
        edited_df["Status"] = edited_df.apply(lambda x: "✅ PASS" if x["Actual Drop (%)"] <= x["Limit (%)"] else "❌ FAIL", axis=1)

        # --- Display Results ---
        st.dataframe(edited_df.style.applymap(
            lambda x: 'background-color: #ffcccc' if x == "❌ FAIL" else ('background-color: #ccffcc' if x == "✅ PASS" else ''),
            subset=['Status']
        ), use_container_width=True)

        # --- Excel Export with Formulas (as before) ---
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

            headers = list(edited_df.columns[:7]) + ['Current (A) [formula]', 'Actual Drop (%) [formula]', 'Status [formula]', 'Suggested Size (from app)']
            for col_num, header in enumerate(headers):
                worksheet.write(3, col_num, header)

            for r in range(len(edited_df)):
                for c in range(7):
                    worksheet.write(r+4, c, edited_df.iloc[r, c])

            # Cable library in columns M:N
            worksheet.write('M1', 'Cable Size (mm²)')
            worksheet.write('N1', 'mV/A/m')
            for i, size in enumerate(df_lib['Size (mm²)']):
                worksheet.write(i+1, 12, size)
                worksheet.write(i+1, 13, df_lib['mV/A/m'][i])

            for r in range(len(edited_df)):
                row_excel = r + 5
                current_formula = f'=(D{row_excel}*1000)/(SQRT(3)*$B$1*$B$2)'
                worksheet.write_formula(r+4, 7, current_formula)

                drop_formula = f'=((VLOOKUP(G{row_excel},$M:$N,2,FALSE)*H{row_excel}*E{row_excel})/1000)/$B$1*100'
                worksheet.write_formula(r+4, 8, drop_formula)

                status_formula = f'=IF(I{row_excel}<=F{row_excel},"✅ PASS","❌ FAIL")'
                worksheet.write_formula(r+4, 9, status_formula)

                worksheet.write(r+4, 10, edited_df.iloc[r, 9])

            worksheet.set_column(0, 10, 18)

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
    1. **Upsizing:** Move to the 'Suggested Size' indicated.
    2. **Parallel Runs:** If a single 630mm² cable still fails, use two cables in parallel.
    3. **Cable Material:** Always specify **Copper (Cu) XLPE/SWA/LSZH** for high-load tie connections.
    """)

# ===============================
# TAB 2: Transformer Feeder Audit
# ===============================
with tab2:
    st.subheader("Transformer to MSB: Voltage Drop Audit")
    st.info(f"Analysis for **2.6 MVA** Emergency Load over **291 m** route.")

    # --- Engineering Constants (simplified for this audit) ---
    CABLE_REF = {300: 0.160, 400: 0.140, 500: 0.120, 630: 0.100}

    col1, col2 = st.columns(2)
    with col1:
        load_kw = st.number_input("Maximum Demand (kW)", value=2333.0, key="load_kw")
        length = st.number_input("Cable Distance (m)", value=291.0, key="length")
    with col2:
        pf_t2 = st.number_input("Power Factor", value=0.85, key="pf_t2")
        voltage_t2 = 400  # fixed for this analysis
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

            # Helper to convert column index to letter (0->A, 1->B, ...)
            def xlsx_col(idx):
                return chr(65 + idx)

            # Write formulas at row 2 (data starts at row 2)
            ws.write(0, 6, "Calculated Ib (A)")
            # Formula: = (B2*1000) / (1.732*400*PF)
            # B2 is Demand (kW) (col 1), PF from input cell
            ws.write_formula(1, 6, f"=({xlsx_col(1)}2*1000)/(1.732*{voltage_t2}*{pf_t2})")

            ws.write(0, 7, "Actual Drop (%)")
            # Formula: ((mV/A/m * (Ib_per_cable) * Distance) / 1000) / Voltage * 100
            # mv_am is fixed from selected cable, Ib_per_cable = calculated Ib / parallel runs
            # G2 contains calculated Ib
            ws.write_formula(1, 7, f"=(({mv_am}*(G2/{xlsx_col(3)}2)*{xlsx_col(2)}2)/1000)/{voltage_t2}*100")

        return output.getvalue()

    st.download_button(
        label="📥 Download Transformer Audit Excel (with formulas)",
        data=export_audit(),
        file_name="Transformer_Feeder_Audit.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
