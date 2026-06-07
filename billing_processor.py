import pandas as pd
import sqlite3
import os
import streamlit as st  # Imported for direct visual inspection!

def clean_string_key(val):
    if pd.isna(val):
        return ""
    return str(val).lower().strip().replace(",", "").replace(".", "").replace(" ", "")

def run_billing_pipeline_v2(raw_billing_csv_path):
    # -------------------------------------------------------------------------
    # STEP 1: FETCH DATABASE TABLES
    # -------------------------------------------------------------------------
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "billing_system.db")
    
    conn = sqlite3.connect(db_path)
    df_rules = pd.read_sql_query("SELECT * FROM price_level_rules", conn)
    df_custs = pd.read_sql_query("SELECT * FROM customers_db", conn)
    df_items = pd.read_sql_query("SELECT * FROM items_db", conn)
    df_prices = pd.read_sql_query("SELECT * FROM prices_db", conn)
    conn.close()
    
    df_billing = pd.read_csv(raw_billing_csv_path)
    
    # -------------------------------------------------------------------------
    # STEP 2: SCORING ENGINE
    # -------------------------------------------------------------------------
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
    
    # -------------------------------------------------------------------------
    # STEP 3: QUANTITY AGGREGATION
    # -------------------------------------------------------------------------
    df_grouped = df_billing.groupby(
        ["Customer", "Item", "Price Level", "CA Line?"], as_index=False
    ).agg({"Units": "sum"}).rename(columns={"Units": "Qty"})
    
    # -------------------------------------------------------------------------
    # STEP 4: CLEAN AND ALIGN STRINGS
    # -------------------------------------------------------------------------
    df_grouped["_match_item"] = df_grouped["Item"].astype(str).str.strip().str.replace(".0", "", regex=False)
    df_grouped["_match_cust"] = df_grouped["Customer"].apply(clean_string_key)
    df_grouped["_match_pl"] = df_grouped["Price Level"].astype(str).str.strip()
    
    df_items["_match_item"] = df_items["item_code"].astype(str).str.strip().str.replace(".0", "", regex=False)
    df_custs["_match_cust"] = df_custs["customer_name"].apply(clean_string_key)
    
    df_prices["_match_item"] = df_prices["item_code"].astype(str).str.strip().str.replace(".0", "", regex=False)
    df_prices["_match_cust"] = df_prices["customer_name"].apply(clean_string_key)
    df_prices["_match_pl"] = df_prices["price_level_name"].astype(str).str.strip()

    # 🚨 LIVE VISUAL DEBUGGING BLOCKS 🚨
    st.write("## 🛠️ Visual Debugging Terminal")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("**From Your Database (`df_items`):**")
        st.dataframe(df_items[["_match_item", "line_order"]])
    with col2:
        st.write("**From Your Uploaded CSV (`df_grouped`):**")
        st.dataframe(df_grouped[["_match_item", "Item", "Qty"]].head(5))

    # -------------------------------------------------------------------------
    # STEP 5: UNIFIED MERGE
    # -------------------------------------------------------------------------
    df_grouped = pd.merge(df_grouped, df_custs[["_match_cust", "netsuite_id"]], on="_match_cust", how="left").rename(columns={"netsuite_id": "Customer ID"})
    
    # Let's see what happens RIGHT when we merge line_order
    df_grouped = pd.merge(df_grouped, df_items[["_match_item", "netsuite_internal_id", "line_order"]], on="_match_item", how="left")
    
    st.write("**Right after merging `line_order` (Before filling fallbacks):**")
    st.dataframe(df_grouped[["_match_item", "line_order"]].head(5))

    df_grouped = df_grouped.rename(columns={"netsuite_internal_id": "Item ID", "line_order": "Line Order"})
    
    df_grouped = pd.merge(df_grouped, df_prices[["_match_cust", "_match_item", "_match_pl", "price"]], on=["_match_cust", "_match_item", "_match_pl"], how="left")

    # -------------------------------------------------------------------------
    # STEP 6: BACKUPS, FALLBACKS & CALCULATIONS
    # -------------------------------------------------------------------------
    df_grouped["Line Order"] = df_grouped["Line Order"].fillna(1).astype(int)
    df_grouped["Customer ID"] = df_grouped["Customer ID"].fillna("NS-CUST-0000")
    df_grouped["price"] = df_grouped["price"].fillna(100.00)
    df_grouped["Total_Calculated_Value"] = df_grouped["Qty"] * df_grouped["price"]
    
    # -------------------------------------------------------------------------
    # STEP 7: ASSEMBLE OUTPUT FILE SPECIFICATIONS
    # -------------------------------------------------------------------------
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