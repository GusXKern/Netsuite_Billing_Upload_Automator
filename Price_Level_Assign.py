import pandas as pd

def assign_price_levels(billing_path, rules_path):
    df_billing = pd.read_csv(billing_path)
    df_rules = pd.read_csv(rules_path)
    
    assigned_levels = []
    
    for idx, row in df_billing.iterrows():
        cust = row["Customer"]
        county = row["County"]
        billing_type = row["Type"]
        
        best_rule = "{Customer} Flat Rate Rule" # Fallback text string
        highest_score = -1
        
        for r_idx, rule in df_rules.iterrows():
            score = 0
            
            # --- 1. Evaluate Customer ---
            if rule["Customer"] == cust:
                score += 2
            elif rule["Customer"] == "DEFAULT":
                score += 1
            else:
                continue
                
            # --- 2. Evaluate County ---
            if rule["County"] == county:
                score += 2
            elif rule["County"] == "ANY":
                score += 1
            else:
                continue
                
            # --- 3. Evaluate Type ---
            if rule["Type"] == billing_type:
                score += 2
            elif rule["Type"] == "ANY":
                score += 1
            else:
                continue
            
            if score > highest_score:
                highest_score = score
                best_rule = rule["Price_Level_Name"]
        
        # Automatically inject the row's actual customer name into the naming template
        final_price_level = best_rule.replace("{Customer}", cust)
        
        assigned_levels.append(final_price_level)
        
    df_billing["NetSuite_Price_Level"] = assigned_levels
    return df_billing

# Let's run it!
df_final = assign_price_levels("raw_billing_data.csv", "price_level_rules.csv")

# Filter the view to check if Peterson Inc mapped properly
print(df_final.head(15))
import pandas as pd

def build_netsuite_upload(df_final):
    # --- STEP 1: CREATE THE "CA LINE?" FLAG ---
    # If the state is CA, mark YES. Otherwise, mark NO.
    df_final["CA Line?"] = df_final["State"].apply(lambda x: "YES" if x == "CA" else "NO")
    
    # --- STEP 2: AGGREGATE / GROUP BY ---
    # We group by our unique constraints and SUM the 'Units' column
    df_grouped = df_final.groupby(
        ["Customer", "Item", "NetSuite_Price_Level", "CA Line?"], 
        as_index=False
    ).agg({
        "Units": "sum"  # This adds up your quantities for matching lines
    })
    
    # Rename 'Units' to 'Qty' to match your NetSuite mockup
    df_grouped.rename(columns={"Units": "Qty"}, inplace=True)
    
    # --- STEP 3: CONSTRUCT NETSUITE INVOICE METADATA ---
    
    # Create the External ID (e.g., "0526-PBO" based on May 2026 current date)
    # Let's generate it dynamically using a short code helper
    def generate_external_id(customer_name):
        # Grab first letter of each word in company name up to 3 chars
        clean_name = "".join([word[0] for word in customer_name.replace(",", "").split()]).upper()[:3]
        return f"0526-{clean_name}"
    
    df_grouped["External ID"] = df_grouped["Customer"].apply(generate_external_id)
    
    # Standard static dates & placeholders for your upcoming DB merges
    df_grouped["Date"] = "5/31/2026"
    df_grouped["Line Order"] = 1 # NetSuite can often default this or auto-increment
    df_grouped["Customer ID"] = "" # Left blank for your database merge step later
    df_grouped["Item ID"] = ""     # Left blank for your database merge step later
    df_grouped["Trade Credit"] = "Net 15"
    df_grouped["Due Date"] = "6/15/2026"
    
    # --- STEP 4: REORDER COLUMNS TO MATCH MOCKUP ---
    final_columns = [
        "External ID", "Date", "Customer", "Item", "Line Order", 
        "CA Line?", "Qty", "NetSuite_Price_Level", "Customer ID", 
        "Item ID", "Trade Credit", "Due Date"
    ]
    
    df_netsuite_ready = df_grouped[final_columns]
    
    # Rename the column heading to match your mockup exactly
    df_netsuite_ready.rename(columns={"NetSuite_Price_Level": "Price Level"}, inplace=True)
    
    return df_netsuite_ready

# --- TEST IT RUNNING ---
# Assuming 'df_final' is the dataframe returned from your previous price level engine script
df_upload_file = build_netsuite_upload(df_final)

# Show the aggregated results
print(df_upload_file.head(10))

# Save it to check your work in Excel
#df_upload_file.to_csv("netsuite_upload_prototype.csv", index=False)
df_final.to_csv("Just_PLs.csv", index=False)