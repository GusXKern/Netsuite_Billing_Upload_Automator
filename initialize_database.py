import sqlite3
import pandas as pd
import os

def create_database_v2():
    """Builds the SQLite tables and fills them with baseline NetSuite mappings."""
    # Force the database file to stay in the exact folder this script is in
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "billing_system.db")
    
    if os.path.exists(db_path):
            try:
                os.remove(db_path)
                print("Successfully deleted old database cache.")
            except Exception as e:
                print(f"Note: Could not clear live cache file automatically: {e}")
                print("Please manually close your Streamlit app terminal window first!")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Enable foreign keys support in SQLite
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # 1. Customers Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers_db (
            customer_name TEXT PRIMARY KEY,
            netsuite_id TEXT NOT NULL
        )
    ''')
    
    # 2. Items Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items_db (
            item_code TEXT PRIMARY KEY,
            netsuite_internal_id TEXT NOT NULL,
            line_order INTEGER NOT NULL
        )
    ''')
    
    # 3. Price Level Names Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_levels_db (
            price_level_name TEXT PRIMARY KEY,
            netsuite_internal_id_pl TEXT NOT NULL
        )
    ''')
    
    # 4. Rules Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_level_rules (
            rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            county TEXT NOT NULL,
            type TEXT NOT NULL,
            price_level_name TEXT NOT NULL,
            FOREIGN KEY (customer_name) REFERENCES customers_db (customer_name)
        )
    ''')
    
    # 5. Prices Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prices_db (
            customer_name TEXT,
            item_code TEXT,
            price_level_name TEXT,
            price REAL NOT NULL,
            PRIMARY KEY (customer_name, item_code, price_level_name),
            FOREIGN KEY (customer_name) REFERENCES customers_db (customer_name),
            FOREIGN KEY (item_code) REFERENCES items_db (item_code),
            FOREIGN KEY (price_level_name) REFERENCES price_levels_db (price_level_name)
        )
    ''')
    
    # --- SEED DATA LOGIC ---
    # Try to dynamically load client names from your mapping file if it exists
    client_map_path = os.path.join(base_dir, "client_mappings.csv")
    if os.path.exists(client_map_path):
        df_clients = pd.read_csv(client_map_path)
        customer_list = df_clients["client_name"].tolist()
        pbo_name = customer_list[0] if len(customer_list) > 0 else "Powell, Barnes and Owens"
        jc_name = customer_list[1] if len(customer_list) > 1 else "Johnson-Clark"
    else:
        pbo_name = "Powell, Barnes and Owens"
        jc_name = "Johnson-Clark"
    
    # Seed Customers
    cursor.executemany("INSERT OR IGNORE INTO customers_db VALUES (?, ?)", [
        (pbo_name, "NS-CUST-9901"), 
        (jc_name, "NS-CUST-9902"),
        ("Barnes LLC", "NS-CUST-9903"),
        ("Peterson Inc", "NS-CUST-9904"),
        ("Baird, Hayes and Arias", "NS-CUST-9905"),
        ("DEFAULT", "NS-CUST-0000")
    ])
    
    # Seed Items
    cursor.executemany("INSERT OR IGNORE INTO items_db VALUES (?, ?, ?)", [
        ("1001", "NS-ITEM-101",1), ("1002", "NS-ITEM-102",2), ("1003", "NS-ITEM-103",3), ("1004", "NS-ITEM-104",4),("1005", "NS-ITEM-105",5)
    ])
    
    # Seed Price Levels
    cursor.executemany("INSERT OR IGNORE INTO price_levels_db VALUES (?, ?)", [
        ("Powell Flat Rate Rule", "NS-PL-01"),
        ("JC-CX-TypeA", "NS-PL-02"),
        ("JC-CX-TypeB", "NS-PL-03"),
        ("PI-CX", "NS-PL-04"),
        ("Base Price", "NS-PL-00")
    ])
    
    # Seed Rules
    cursor.executemany('''
        INSERT OR IGNORE INTO price_level_rules (customer_name, county, type, price_level_name)
        VALUES (?, ?, ?, ?)
    ''', [
        (pbo_name, "ANY", "ANY", "Powell Flat Rate Rule"),
        (jc_name, "County X", "A", "JC-CX-TypeA"),
        (jc_name, "County X", "B", "JC-CX-TypeB"),
        ("Peterson Inc", "County X", "ANY", "PI-CX"),
        ("DEFAULT", "ANY", "ANY", "Base Price")
    ])
    
    # Seed Prices
    cursor.executemany('''
        INSERT OR IGNORE INTO prices_db VALUES (?, ?, ?, ?)
    ''', [
        (pbo_name, "1001", "Powell Flat Rate Rule", 150.00),
        (pbo_name, "1002", "Powell Flat Rate Rule", 175.00),
        (jc_name, "1001", "JC-CX-TypeA", 110.00),
        (jc_name, "1001", "JC-CX-TypeB", 130.00),
        ("DEFAULT", "1001", "Base Price", 100.00),
        ("DEFAULT", "1002", "Base Price", 100.00)
    ])
    
    conn.commit()
    conn.close()
    print(" Database Schema V2 initialized perfectly!")


def run_billing_pipeline_v2(raw_billing_csv_path):
    """Processes raw transaction CSV files using rules pulled dynamically from SQLite."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "billing_system.db")
    
    conn = sqlite3.connect(db_path)
    df_rules = pd.read_sql_query("SELECT * FROM price_level_rules", conn)
    df_custs = pd.read_sql_query("SELECT * FROM customers_db", conn)
    df_items = pd.read_sql_query("SELECT * FROM items_db", conn)
    df_prices = pd.read_sql_query("SELECT * FROM prices_db", conn)
    conn.close()
    
    df_billing = pd.read_csv(raw_billing_csv_path)
    
    # 1. Scoring Engine Strategy
    assigned_levels = []
    for idx, row in df_billing.iterrows():
        cust, county, billing_type = row["Customer"], row["County"], row["Type"]
        best_rule = "Base Price"
        highest_score = -1
        
        for r_idx, rule in df_rules.iterrows():
            score = 0
            if rule["customer_name"] == cust: score += 2
            elif rule["customer_name"] == "DEFAULT": score += 1
            else: continue
                
            if rule["county"] == county: score += 2
            elif rule["county"] == "ANY": score += 1
            else: continue
                
            if rule["type"] == billing_type: score += 2
            elif rule["type"] == "ANY": score += 1
            else: continue
            
            if score > highest_score:
                highest_score = score
                best_rule = rule["price_level_name"]
                
        assigned_levels.append(best_rule)
        
    df_billing["Price Level"] = assigned_levels
    df_billing["CA Line?"] = df_billing["State"].apply(lambda x: "YES" if x == "CA" else "NO")
    
    # 2. Aggregator
    df_grouped = df_billing.groupby(
        ["Customer", "Item", "Price Level", "CA Line?"], as_index=False
    ).agg({"Units": "sum"}).rename(columns={"Units": "Qty"})
    
    df_grouped["Item"] = df_grouped["Item"].astype(str)
    
    # 3. Join Prices Matrix
    df_grouped = pd.merge(
        df_grouped, df_prices,
        left_on=["Customer", "Item", "Price Level"],
        right_on=["customer_name", "item_code", "price_level_name"],
        how="left"
    )
    df_grouped["price"] = df_grouped["price"].fillna(100.00)
    df_grouped["Total_Calculated_Value"] = df_grouped["Qty"] * df_grouped["price"]
    
    # 4. Map IDs
    cust_map = dict(zip(df_custs["customer_name"], df_custs["netsuite_id"]))
    item_map = dict(zip(df_items["item_code"], df_items["netsuite_internal_id"]))
    
    df_grouped["Customer ID"] = df_grouped["Customer"].map(cust_map).fillna(cust_map.get("DEFAULT"))
    df_grouped["Item ID"] = df_grouped["Item"].map(item_map)
    
    # 5. Build NetSuite Columns
    def get_ext_id(name):
        return f"0526-{''.join([w[0] for w in name.replace(',', '').split()]).upper()[:3]}"
        
    df_grouped["External ID"] = df_grouped["Customer"].apply(get_ext_id)
    df_grouped["Date"] = "5/31/2026"
    df_grouped["Line Order"] = 1
    df_grouped["Trade Credit"] = "Net 15"
    df_grouped["Due Date"] = "6/15/2026"
    
    final_cols = [
        "External ID", "Date", "Customer", "Item", "Line Order", 
        "CA Line?", "Qty", "Price Level", "Customer ID", 
        "Item ID", "Trade Credit", "Due Date", "price", "Total_Calculated_Value"
    ]
    
    return df_grouped[final_cols]


# --- SCRIPT EXECUTION BLOCK ---
if __name__ == "__main__":
    # 1. This function is now explicitly defined right above!
    create_database_v2() 
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    billing_file_path = os.path.join(base_dir, "raw_billing_data.csv")
    
    if not os.path.exists(billing_file_path):
        print(f" Notice: '{billing_file_path}' not found in this folder yet.")
        print("Database built successfully, but pipeline skipped until raw_billing_data.csv is provided.")
    else:
        print(" Running billing transformation pipeline...")
        final_sheet = run_billing_pipeline_v2(billing_file_path)
        
        output_path = os.path.join(base_dir, "final_sheet.csv")
        final_sheet.to_csv(output_path, index=False)
        print(" Pipeline completed successfully! Created final_sheet.csv")