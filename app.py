import streamlit as st
import pandas as pd
import io
import math

# App Title
st.set_page_config(page_title="CR13 Tie Cable Calculator", layout="wide")
st.title("⚡ Station CR13: Tie Cable Voltage Drop & Cable Selector")

st.markdown("""
As per **PC1009CR13-ELS2101-**, the maximum allowable voltage drop for **Tie Cables** is **2.0%**. 
This tool suggests the correct cable size to meet that requirement.
""")

# --- Cable Data (Standard mV/A/m for Cu/XLPE 3-Phase @ 90°C) ---
# Source: BS 7671 / IEC 60364
CABLE_DATA = {
    "Size (mm²)": [50, 70, 95, 120, 150, 185, 240, 300, 400, 500, 630],
    "mV/A/m": [0.860, 0.600, 0.440, 0.350, 0.290, 0.240, 0.190, 0.160, 0.140, 0.120, 0.100]
}
df_cables = pd.DataFrame(CABLE_DATA)

# --- Sidebar Inputs ---
st.sidebar.header("📊 Input Parameters")
load_kw = st.sidebar.number_input("Design Load (kW)", value=362.10, help="Found in Load Schedule")
length = st.sidebar.number_input("Route Length (m)", value=60.0, step=5.0)
pf = st.sidebar.slider("Power Factor (cos φ)", 0.8, 1.0, 0.85)
voltage = 400  # Fixed for Tie Cables as per schematic

# --- Calculations ---
ib = (load_kw * 1000) / (math.sqrt(3) * voltage * pf)
max_allowed_v_drop = (2.0 / 100) * voltage # 8.0V

# Find suitable cable
df_cables['Actual_Drop_Volts'] = (df_cables['mV/A/m'] * ib * length) / 1000
df_cables['Actual_Drop_Percent'] = (df_cables['Actual_Drop_Volts'] / voltage) * 100
df_cables['Status'] = df_cables['Actual_Drop_Percent'].apply(lambda x: "✅ PASS" if x <= 2.0 else "❌ FAIL")

# Recommended Cable
recommended = df_cables[df_cables['Status'] == "✅ PASS"].iloc[0] if not df_cables[df_cables['Status'] == "✅ PASS"].empty else None

# --- Main Dashboard ---
c1, c2, c3 = st.columns(3)
c1.metric("Design Current (Ib)", f"{ib:.2f} A")
c2.metric("Target Limit", "2.00%")
if recommended is not None:
    c3.metric("Suggested Min. Cable", f"{recommended['Size (mm²)']} mm²")
else:
    c3.error("No single cable size meets 2% limit. Consider parallel cables.")

st.divider()

# Result Table
st.subheader("Comparison Table: Cable Size vs. Voltage Drop")
st.table(df_cables[['Size (mm²)', 'mV/A/m', 'Actual_Drop_Percent', 'Status']].style.format({"Actual_Drop_Percent": "{:.2f}%"}))

# Export to Excel
output = io.BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    df_cables.to_excel(writer, index=False, sheet_name='Cable_Verification')
    
st.download_button(
    label="📥 Export Analysis to Excel",
    data=output.getvalue(),
    file_name="CR13_Voltage_Drop_Analysis.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)