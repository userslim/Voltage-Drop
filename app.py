import streamlit as st
import pandas as pd
import io
import math

# --- App Configuration ---
st.set_page_config(page_title="CR13 Voltage Drop Manager", layout="wide")
st.title("⚡ Station CR13: Multi-Connection Voltage Drop Manager")

st.markdown("""
Use this tool to verify multiple connections against the design limits in **PC1009CR13-ELS2101-**. 
* **Tie Cables:** Limit is **2.0%**.
* **Sub-Feeder:** Limit is **1.0% - 3.0%** (refer to schematic).
""")

# --- Cable Reference Library (Cu/XLPE/LSZH) ---
CABLE_LIBRARY = {
    "Size (mm²)": [50, 70, 95, 120, 150, 185, 240, 300, 400, 500, 630],
    "mV/A/m": [0.860, 0.600, 0.440, 0.350, 0.290, 0.240, 0.190, 0.160, 0.140, 0.120, 0.100]
}
df_lib = pd.DataFrame(CABLE_LIBRARY)

# --- Initial Data from your Load Schedules ---
default_data = [
    {"Connection": "Tie Cable 1", "Source": "MSB01", "Destination": "MSB03", "Load (kW)": 362.10, "Length (m)": 55.0, "Limit (%)": 2.0, "Cable Size": 300},
    {"Connection": "Tie Cable 2", "Source": "MSB04", "Destination": "MSB02", "Load (kW)": 255.00, "Length (m)": 40.0, "Limit (%)": 2.0, "Cable Size": 185},
    {"Connection": "Essential Feeder", "Source": "MSB02", "Destination": "EPSBC51", "Load (kW)": 47.06, "Length (m)": 80.0, "Limit (%)": 1.0, "Cable Size": 70},
]

# --- Editable Table Interface ---
st.subheader("📋 Connection Verification Table")
st.info("💡 You can edit cells directly or click '+' at the bottom to add new rows.")

# User inputs pf and voltage globally for the station
col_a, col_b = st.columns(2)
pf = col_a.slider("Station Power Factor (cos φ)", 0.8, 1.0, 0.85)
voltage = col_b.selectbox("System Voltage (V)", [400, 230], index=0)

edited_df = st.data_editor(
    pd.DataFrame(default_data),
    num_rows="dynamic", # Enables the "Add Row" feature
    column_config={
        "Cable Size": st.column_config.SelectboxColumn(options=df_lib["Size (mm²)"].tolist())
    },
    use_container_width=True
)

# --- Calculation Logic ---
def calculate_metrics(row):
    # 1. Current
    ib = (row["Load (kW)"] * 1000) / (math.sqrt(3) * voltage * pf)
    
    # 2. Lookup mV/A/m
    mv_am = df_lib.loc[df_lib["Size (mm²)"] == row["Cable Size"], "mV/A/m"].values[0]
    
    # 3. Calc Drop
    drop_v = (mv_am * ib * row["Length (m)"]) / 1000
    drop_perc = (drop_v / voltage) * 100
    
    # 4. Recommendation (What size actually works?)
    suitable_cables = df_lib[((df_lib["mV/A/m"] * ib * row["Length (m)"]) / 1000 / voltage * 100) <= row["Limit (%)"]]
    rec_size = suitable_cables["Size (mm²)"].iloc[0] if not suitable_cables.empty else "Parallel Required"
    
    return pd.Series([round(ib, 2), round(drop_perc, 3), rec_size])

# Apply calculations to the dataframe
if not edited_df.empty:
    edited_df[["Current (A)", "Actual Drop (%)", "Suggested Size"]] = edited_df.apply(calculate_metrics, axis=1)
    
    # Apply Status Flag
    edited_df["Status"] = edited_df.apply(lambda x: "✅ PASS" if x["Actual Drop (%)"] <= x["Limit (%)"] else "❌ FAIL", axis=1)

    # --- Display Results ---
    st.dataframe(edited_df.style.applymap(
        lambda x: 'background-color: #ffcccc' if x == "❌ FAIL" else ('background-color: #ccffcc' if x == "✅ PASS" else ''),
        subset=['Status']
    ), use_container_width=True)

    # --- Excel Export with Formulas ---
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book

        # 1. Sheet with static values (as before)
        edited_df.to_excel(writer, sheet_name='Verification_Values', index=False)

        # 2. Sheet with live Excel formulas
        worksheet = workbook.add_worksheet('Verification_Formulas')
        writer.sheets['Verification_Formulas'] = worksheet

        # Write voltage and power factor at the top (used in formulas)
        worksheet.write('A1', 'Voltage (V):')
        worksheet.write('B1', voltage)
        worksheet.write('A2', 'Power Factor:')
        worksheet.write('B2', pf)

        # Headers (first 7 columns are inputs, then 3 formula columns, then static suggestion)
        headers = list(edited_df.columns[:7]) + ['Current (A) [formula]', 'Actual Drop (%) [formula]', 'Status [formula]', 'Suggested Size (from app)']
        for col_num, header in enumerate(headers):
            worksheet.write(3, col_num, header)

        # Write input data (first 7 columns) starting from row 4
        for r in range(len(edited_df)):
            for c in range(7):
                worksheet.write(r+4, c, edited_df.iloc[r, c])

        # Place the cable library somewhere (columns M:N) for VLOOKUP
        worksheet.write('M1', 'Cable Size (mm²)')
        worksheet.write('N1', 'mV/A/m')
        for i, size in enumerate(df_lib['Size (mm²)']):
            worksheet.write(i+1, 12, size)      # column M (index 12)
            worksheet.write(i+1, 13, df_lib['mV/A/m'][i])  # column N (index 13)

        # Write formulas for each row
        for r in range(len(edited_df)):
            row_excel = r + 5          # data starts at row 5 (header row 4, first data row 5)
            # Current formula: (Load_kW * 1000) / (SQRT(3) * Voltage * PF)
            current_formula = f'=(D{row_excel}*1000)/(SQRT(3)*$B$1*$B$2)'
            worksheet.write_formula(r+4, 7, current_formula)   # column H (index 7)

            # Drop % formula: first lookup mV/A/m, then compute drop V, then %
            # VLOOKUP(Grow, $M:$N, 2, FALSE) * Current * Length / 1000  -> then /Voltage *100
            drop_formula = f'=((VLOOKUP(G{row_excel},$M:$N,2,FALSE)*H{row_excel}*E{row_excel})/1000)/$B$1*100'
            worksheet.write_formula(r+4, 8, drop_formula)       # column I (index 8)

            # Status formula: =IF(Irow <= Frow, "✅ PASS", "❌ FAIL")
            status_formula = f'=IF(I{row_excel}<=F{row_excel},"✅ PASS","❌ FAIL")'
            worksheet.write_formula(r+4, 9, status_formula)     # column J (index 9)

            # Suggested Size – static value from the app's calculation
            worksheet.write(r+4, 10, edited_df.iloc[r, 9])      # column K (index 10)

        # Adjust column widths for readability
        worksheet.set_column(0, 10, 18)

    # Download button
    st.download_button(
        label="📥 Download Comprehensive Excel Report (with formulas)",
        data=output.getvalue(),
        file_name="Station_CR13_Voltage_Drop_Report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.warning("Please add at least one connection to see the analysis.")

st.divider()
st.subheader("🛠 Technical Recommendations for Compliance")
st.markdown("""
If a tie cable is failing the **2.0% limit**, consider the following modifications:
1.  **Upsizing:** Move to the 'Suggested Size' indicated in the table.
2.  **Parallel Runs:** If a single 630mm² cable is still failing, use two cables in parallel (e.g., 2 x 4C 240mm²) to halve the resistance.
3.  **Cable Material:** Always specify **Copper (Cu) XLPE/SWA/LSZH** for high-load tie connections.
""")
