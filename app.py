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

    # --- Excel Export ---
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        edited_df.to_excel(writer, index=False, sheet_name='Verification_Report')
    
    st.download_button(
        label="📥 Download Comprehensive Excel Report",
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
