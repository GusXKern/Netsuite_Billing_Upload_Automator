import streamlit as st
import pandas as pd
import sqlite3
import os

# -------------------------------------------------------------------------
# THE ONE TRUE PATH (FORCE DETECTOR)
# -------------------------------------------------------------------------
TRUE_DB_PATH = r"C:\Users\guske\Desktop\Python_Projects\billing_system.db"


# --- HELPER FUNCTIONS FROM LOCAL_RUN.PY ---
def clean_string_key(val):
    if pd.isna(val):
        return ""
    return str(val).lower().strip().replace(",", "").replace(".", "").replace(" ", "")

def force_integer_item(val):
    if pd.isna(val):
        return 0
    try:
        val_str = str(val).split('.')[0]
        return int(''.join(filter(str.isdigit, val_str)))
    except ValueError:
        return 0

# --- THE CORE TRANSFORMATION ENGINE ---
def process_billing_dataframe(df_billing):
    """Processes the billing dataframe using rules pulled dynamically from SQLite."""
    # Step 1: Fetch Database Tables using our forced global path
    conn = sqlite3.connect(TRUE_DB_PATH)
    df_rules = pd.read_sql_query("SELECT * FROM price_level_rules", conn)
    df_custs = pd.read_sql_query("SELECT * FROM customers_db", conn)
    df_items = pd.read_sql_query("SELECT * FROM items_db", conn)
    df_prices = pd.read_sql_query("SELECT * FROM prices_db", conn)
    conn.close()
    
    # Step 2: Scoring Engine (Price Levels)
    assigned_levels = []
    for idx, row in df_billing.iterrows():
        cust, county, billing_type = row["Customer"], row["County"], row["Type"]
        clean_cust = clean_string_key(cust)
        best_rule = "Base Price"
        highest_score = -1
        
        for r_idx, rule in df_rules.iterrows():
            score = 0
            rule_cust = clean_string_key(rule["customer_name"])
            if rule_cust == clean_cust: score += 2
            elif rule_cust == "default": score += 1
            else: continue
            
            if str(rule["county"]).strip() == str(county).strip(): score += 2
            elif str(rule["county"]).strip() == "ANY": score += 1
            else: continue
            
            if str(rule["type"]).strip() == str(billing_type).strip(): score += 2
            elif str(rule["type"]).strip() == "ANY": score += 1
            else: continue
            
            if score > highest_score:
                highest_score = score
                best_rule = rule["price_level_name"]
        assigned_levels.append(best_rule)
        
    df_billing["Price Level"] = assigned_levels
    df_billing["CA Line?"] = df_billing["State"].apply(lambda x: "YES" if x == "CA" else "NO")
    
    # Step 3: Quantity Aggregation
    df_grouped = df_billing.groupby(
        ["Customer", "Item", "Price Level", "CA Line?"], as_index=False
    ).agg({"Units": "sum"}).rename(columns={"Units": "Qty"})
    
    # Step 4: Prepare Uniform Match Keys
    df_grouped["_match_item"] = df_grouped["Item"].apply(force_integer_item)
    df_items["_match_item"] = df_items["item_code"].apply(force_integer_item)
    df_prices["_match_item"] = df_prices["item_code"].apply(force_integer_item)
    
    df_grouped["_match_cust"] = df_grouped["Customer"].apply(clean_string_key)
    df_custs["_match_cust"] = df_custs["customer_name"].apply(clean_string_key)
    df_prices["_match_cust"] = df_prices["customer_name"].apply(clean_string_key)
    
    df_grouped["_match_pl"] = df_grouped["Price Level"].astype(str).str.strip()
    df_prices["_match_pl"] = df_prices["price_level_name"].astype(str).str.strip()

    # Step 5: Join Tables
    df_items_clean = df_items.drop_duplicates(subset=["_match_item"])
    df_custs_clean = df_custs.drop_duplicates(subset=["_match_cust"])
    
    df_grouped = pd.merge(df_grouped, df_custs_clean[["_match_cust", "netsuite_id"]], on="_match_cust", how="left")
    df_grouped = df_grouped.rename(columns={"netsuite_id": "Customer ID"})
    
    df_grouped = pd.merge(df_grouped, df_items_clean[["_match_item", "netsuite_internal_id", "line_order"]], on="_match_item", how="left")
    df_grouped = df_grouped.rename(columns={"netsuite_internal_id": "Item ID", "line_order": "Line Order"})
    
    df_grouped = pd.merge(df_grouped, df_prices[["_match_cust", "_match_item", "_match_pl", "price"]], on=["_match_cust", "_match_item", "_match_pl"], how="left")

    # Step 6: Fallback Handling
    df_grouped["Line Order"] = df_grouped["Line Order"].fillna(1).astype(int)
    df_grouped["Customer ID"] = df_grouped["Customer ID"].fillna("NS-CUST-0000")
    df_grouped["price"] = df_grouped["price"].fillna(100.00)
    df_grouped["Total_Calculated_Value"] = df_grouped["Qty"] * df_grouped["price"]
    
    # Step 7: Build Export Format
    def get_ext_id(name):
        return f"0526-{''.join([w[0] for w in name.replace(',', '').split()]).upper()[:3]}"
        
    df_grouped["External ID"] = df_grouped["Customer"].apply(get_ext_id)
    df_grouped["Date"] = "5/31/2026"
    df_grouped["Trade Credit"] = "Net 15"
    df_grouped["Due Date"] = "6/15/2026"
    
    final_cols = [
        "External ID", "Date", "Customer", "Item", "Line Order", 
        "CA Line?", "Qty", "Price Level", "Customer ID", 
        "Item ID", "Trade Credit", "Due Date", "price", "Total_Calculated_Value"
    ]
    
    return df_grouped[final_cols]


# --- STREAMLIT USER INTERFACE ---
st.set_page_config(page_title="Billing Data Pipeline", page_icon="📊", layout="wide")

st.title("📊 NetSuite Billing Transformation Pipeline")
st.markdown("Upload your raw billing CSV data file below to map NetSuite IDs, evaluate matrix pricing rules, and generate your finalized import template.")

# Sidebar Status & Live Table Inspector
st.sidebar.header("System Status")
if os.path.exists(TRUE_DB_PATH):
    st.sidebar.success("✅ SQLite Database Located")
    
    try:
        conn = sqlite3.connect(TRUE_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]
        conn.close()
        
        if tables:
            st.sidebar.write("🟢 **Live Tables Found:**", tables)
        else:
            st.sidebar.warning("⚠️ Database file is open but contains ZERO tables.")
    except Exception as e:
        st.sidebar.error(f"Error inspecting tables: {e}")
else:
    st.sidebar.error("❌ Database file completely missing at this path!")

# Main File Uploader Layout
uploaded_file = st.file_uploader("Choose raw billing CSV file", type=["csv"])

if uploaded_file is not None:
    try:
        raw_df = pd.read_csv(uploaded_file)
        
        st.subheader("Raw Data Preview")
        st.dataframe(raw_df.head(5), use_container_width=True)
        
        if st.button("🚀 Process Billing File", type="primary"):
            with st.spinner("Executing rule matrices and mapping internal configurations..."):
                # Call pipeline using the unified engine configuration
                final_output_df = process_billing_dataframe(raw_df)
                
                st.success("🎉 Billing sheet generated successfully!")
                
                st.subheader("Processed Output Preview (First 10 Rows)")
                st.dataframe(final_output_df.head(10), use_container_width=True)
                
                csv_data = final_output_df.to_csv(index=False).encode('utf-8')
                
                st.download_button(
                    label="📥 Download Final NetSuite Sheet",
                    data=csv_data,
                    file_name="final_sheet.csv",
                    mime="text/csv",
                )
    except Exception as e:
        st.error(f"An error occurred while processing the file: {e}")