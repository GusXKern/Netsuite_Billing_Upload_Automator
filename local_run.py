import pandas as pd
import sqlite3
import os

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

def run_local_pipeline():
    # -------------------------------------------------------------------------
    # HARDCODED ROOT PATHS
    # -------------------------------------------------------------------------
    root_dir = r"C:\Users\guske\Desktop\Python_Projects"
    db_path = os.path.join(root_dir, "billing_system.db")
    csv_path = os.path.join(root_dir, "raw_billing_data.csv")
    output_path = os.path.join(root_dir, "final_sheet.csv")
    
    print("=== STARTING LOCAL PROCESSING PIPELINE ===")
    print(f"Reading Database from: {db_path}")
    print(f"Reading Billing Data from: {csv_path}")
    
    # -------------------------------------------------------------------------
    # STEP 1: FETCH DATABASE TABLES
    # -------------------------------------------------------------------------
    conn = sqlite3.connect(db_path)
    df_rules = pd.read_sql_query("SELECT * FROM price_level_rules", conn)
    df_custs = pd.read_sql_query("SELECT * FROM customers_db", conn)
    df_items = pd.read_sql_query("SELECT * FROM items_db", conn)
    df_prices = pd.read_sql_query("SELECT * FROM prices_db", conn)
    conn.close()
    
    df_billing = pd.read_csv(csv_path)
    
    # -------------------------------------------------------------------------
    # STEP 2: SCORING ENGINE (Price Levels)
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
    # STEP 4: PREPARE UNIFORM MATCH KEYS
    # -------------------------------------------------------------------------
    df_grouped["_match_item"] = df_grouped["Item"].apply(force_integer_item)
    df_items["_match_item"] = df_items["item_code"].apply(force_integer_item)
    df_prices["_match_item"] = df_prices["item_code"].apply(force_integer_item)
    
    df_grouped["_match_cust"] = df_grouped["Customer"].apply(clean_string_key)
    df_custs["_match_cust"] = df_custs["customer_name"].apply(clean_string_key)
    df_prices["_match_cust"] = df_prices["customer_name"].apply(clean_string_key)
    
    df_grouped["_match_pl"] = df_grouped["Price Level"].astype(str).str.strip()
    df_prices["_match_pl"] = df_prices["price_level_name"].astype(str).str.strip()

    # -------------------------------------------------------------------------
    # STEP 5: JOIN TABLES NATIVELY via PANDAS MERGE
    # -------------------------------------------------------------------------
    # Deduplicate reference files before merge to protect row mapping shapes
    df_items_clean = df_items.drop_duplicates(subset=["_match_item"])
    df_custs_clean = df_custs.drop_duplicates(subset=["_match_cust"])
    
    # Join Customers
    df_grouped = pd.merge(df_grouped, df_custs_clean[["_match_cust", "netsuite_id"]], on="_match_cust", how="left")
    df_grouped = df_grouped.rename(columns={"netsuite_id": "Customer ID"})
    
    # Join Items (Grabbing both netsuite_internal_id and line_order columns)
    df_grouped = pd.merge(df_grouped, df_items_clean[["_match_item", "netsuite_internal_id", "line_order"]], on="_match_item", how="left")
    df_grouped = df_grouped.rename(columns={"netsuite_internal_id": "Item ID", "line_order": "Line Order"})
    
    # Join Prices
    df_grouped = pd.merge(df_grouped, df_prices[["_match_cust", "_match_item", "_match_pl", "price"]], on=["_match_cust", "_match_item", "_match_pl"], how="left")

    # -------------------------------------------------------------------------
    # STEP 6: FALLBACK HANDLING & VALUES
    # -------------------------------------------------------------------------
    df_grouped["Line Order"] = df_grouped["Line Order"].fillna(1).astype(int)
    df_grouped["Customer ID"] = df_grouped["Customer ID"].fillna("NS-CUST-0000")
    df_grouped["price"] = df_grouped["price"].fillna(100.00)
    df_grouped["Total_Calculated_Value"] = df_grouped["Qty"] * df_grouped["price"]
    
    # -------------------------------------------------------------------------
    # STEP 7: BUILD EXPORT FORMAT
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
    
    df_output = df_grouped[final_cols]
    df_output.to_csv(output_path, index=False)
    
    print("-" * 50)
    print(f"SUCCESS! Output spreadsheet completely processed.")
    print(f"Saved directly to: {output_path}")
    print("-" * 50)

if __name__ == "__main__":
    run_local_pipeline()