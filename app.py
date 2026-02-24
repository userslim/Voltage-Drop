import streamlit as st
import pandas as pd
import io
import math

# --- App Configuration ---
st.set_page_config(page_title="CR13 Voltage Drop Auditor", layout="wide")
st.title("⚡ Station CR13: Voltage Drop Auditor & Excel Reporter")

st.markdown("""
Enter the cable details below. The exported Excel file will contain **live formulas** so your client can audit the math themselves.
""")

# --- Cable Reference Library (mV/A/m for Cu/XLPE) ---
CABLE_REF = {
    50: 0.860, 70: 0.600, 95: 0.440, 120: 0.350, 150: 0.290, 
    185: 0.240, 240: 0.190, 300: 0.160, 400: 0.140, 500: 0.120, 630: 0.100
}

# --- Sidebar Global Constants ---
st.sidebar.header("Global Settings")
voltage = st.sidebar.selectbox("System Voltage (V)", [400, 230], index=0)
pf = st.sidebar.slider("Power Factor (pf)", 0.8, 1.0, 0.85)

# --- Dynamic Data Table ---
default_rows = [
    {"Connection": "Tie Cable 1", "Source": "MSB01", "Destination": "MSB03", "Load (kW)": 362.10, "Length (m)": 60, "Limit (%)": 2.0, "Size (mm²)": 300},
    {"Connection": "Tie Cable 2", "Source": "MSB04", "Destination": "MSB02", "Load (kW)": 255.00, "Length (m)": 45, "Limit (%)": 2.0, "Size (mm²)": 240}
]

st.subheader("📋 Connection Manager")
df_input = st.data_editor(
    pd.DataFrame(default_rows),
    num_rows="dynamic",
    column_config={
        "Size (mm²)": st.column_config.SelectboxColumn(options=list(CABLE_REF.keys()))
    },
    use_container_width=True
)

# --- Logic for Real-time Display (Streamlit) ---
def get_calculation(row):
    mv_am = CABLE_REF[row["Size (mm²)"]]
    # Ib = P / (sqrt(3) * V * pf)
    ib = (row["Load (kW)"] * 1000) / (math.sqrt(3) * voltage * pf)
    v_drop = (mv_am * ib * row["Length (m)"]) / 1000
    v_drop_perc = (v_drop / voltage) * 100
    return pd.Series([round(ib, 2), round(v_drop_perc, 3)])

if not df_input.empty:
    df_input[['Current (A)', 'Actual Drop (%)']] = df_input.apply(get_calculation, axis=1)
    df_input['Status'] = df_input.apply(lambda x: "✅ PASS" if x['Actual Drop (%)'] <= x['Limit (%)'] else "❌ FAIL", axis=1)
    st.dataframe(df_input, use_container_width=True)

# --- Excel Export with LIVE FORMULAS ---
def export_to_excel(df):
    output = io.BytesIO()
    workbook = pd.ExcelWriter(output, engine='xlsxwriter')
    
    # We write a clean sheet first to set headers
    df_export = df[['Connection', 'Source', 'Destination', 'Load (kW)', 'Length (m)', 'Size (mm²)', 'Limit (%)']].copy()
    df_export.to_excel(workbook, index=False, sheet_name='Audit_Report')
    
    ws = workbook.sheets['Audit_Report']
    
    # Define Column Indices (A=0, B=1...)
    # D=Load, E=Length, F=Size, G=Limit
    # We will add: H=mV/A/m, I=Current(A), J=Actual Drop(%)
    ws.write(0, 7, "mV/A/m")
    ws.write(0, 8, "Current Ib (A)")
    ws.write(0, 9, "Actual Drop (%)")
    ws.write(0, 10, "Status")

    for i, row in enumerate(df.values, start=2): # Excel rows start at 1, but we have header
        # 1. Look up mV/A/m based on size (Column F) using VLOOKUP or Hardcoded for simplicity
        size = row[5]
        mv_val = CABLE_REF[size]
        ws.write(i-1, 7, mv_val)
        
        # 2. Formula for Ib (Amps): =(D{i}*1000) / (1.732 * Voltage * pf)
        # Column D is Load (index 3)
        ws.write_formula(i-1, 8, f"=({xlsx_col(3)}{i}*1000)/(1.732*{voltage}*{pf})")
        
        # 3. Formula for % Drop: =((H{i} * I{i} * E{i})/1000) / Voltage * 100
        # H is index 7 (mV), I is index 8 (Amps), E is index 4 (Length)
        ws.write_formula(i-1, 9, f"=(({xlsx_col(7)}{i}*{xlsx_col(8)}{i}*{xlsx_col(4)}{i})/1000)/{voltage}*100")
        
        # 4. Status Formula
        ws.write_formula(i-1, 10, f'=IF({xlsx_col(9)}{i}<={xlsx_col(6)}{i}, "PASS", "FAIL")')

    workbook.close()
    return output.getvalue()

def xlsx_col(idx):
    return chr(65 + idx) # Helper to convert 0->A, 1->B...

if st.button("Generate Audit Report for Client"):
    excel_data = export_to_excel(df_input)
    st.download_button("📥 Download Excel with Formulas", excel_data, "Voltage_Drop_Audit.xlsx")
