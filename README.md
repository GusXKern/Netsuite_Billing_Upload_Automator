# Background
In my previous role, I worked on building tools to automate various accounting functions. Using mostly advanced Google Sheets formulas and Google Apps Script I was able to take previously time consuming manual tasks and turn them into easily understandable and shareable spreadsheet-based tools. While in this role, the project I spent the most time on was rebuilding our tool to automate the creation of invoices in Netsuite. 

(Add part about why I did this project: Make fake data, add price levels to raw data using mapping, setting up SQL database with tables that have mapping logic, then making streamlit webpage)

# Tools I Used

- **Python:** Everything from the fake data to the webpage to upload the raw data was made in Python! 
- **Visual Studio Code:** Used to run all the code.
- **Git & GitHub:** Essential for version control and sharing my Python scripts and analysis, ensuring collaboration and project tracking.

While coding, I also made extensive use of online tutorials and the free AI Google Gemini, especially to help with the faker, sqllite3, and streamlit portions of the code. Combined, I was able to use the AI to introduce me to the best ways to perform specific tasks (ex. "What's the best way to use SQL and Python together) with online resources then allowing me to learn and troubleshoot issues I ran into with the initial AI-assisted code. Ultimately, this was a project for learning how to use Python, so I still went out of my way to understand exactly how everything functions and fits together, and in the end, I learned a ton!


# Key Steps


### 1. Generate Fake Raw Data
#### Rationale:
- In order to mimic the kinds of raw data that we were provided while limiting complexity and keeping any client data/processes confidential, I had to make my own raw data from scratch. In the spirit of optimization, I used the Python package 'Faker' to help me quickly and easily generate the necessary fake data. Specifically, the code was able to generate five random company names, and assign a random item code, location, state, county, type, number of units, and billing date from a set list of criteria for each row.
- As an example of how the code works, here is the first portion of the code:
```python
import pandas as pd
import random
from faker import Faker

# Initialize Faker for realistic fake names
fake = Faker()
random.seed(42) # Keeps data consistent every time you run it

# --- STEP 1: CREATE THE MAPPING DATA ---

# 1. Client Mappings (Kept as a DataFrame since it's uniform)
num_clients = 5
client_data = {
    "internal_client_id": [f"CLI-{100 + i}" for i in range(num_clients)],
    "client_name": [fake.company() for _ in range(num_clients)]
}
df_clients = pd.DataFrame(client_data)

# 2. Setup Mappings (Kept as a standard dictionary of lists)
data_mappings = {
    "Item": ["1001", "1002", "1003", "1004", "1005"],
    "Location": ["Practice 1", "Practice 2", "Practice 3"],
    "State": ["NY", "CA", "OK", "TX"],
    "County": ["County X", "County Y"],
    "Type": ["A", "B"]
}
```

- Using faker, we can generate 5 random firm names. Each row then includes a random item from each of the parts of the Setup Mappings. After running, it looks like this:
![First Few Rows of the Generated Raw Data](Photos/Test_Data.png)

### 2. Make and Test Price Level Mapping
For the next step, I wanted to test out the most important feature of the upload template before working on the rest: assigning Price Levels. In real life, each customer might have a variety of unique pricing tiers triggered based on location, the type of services provided, etc. For this project, I assigned each price level to a unique combination of Customer, County, and Type and mapped it in a CSV:
![Price Level Mapping](Photos/)

As you can see above, Johnson-Clark and Peterson Inc each have multiple price levels, with Johnson-Clark having different pricing for each County-Type combination, and Peterson Inc having a different price for each county. The other three firms just use the base pricing for that specific customer (ex. Powell, Barnes and Owens). 

In the code below, we use this CSV and 
```Python
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
```
In order to take the mapping in the CSV and turn it into something that can look at the raw data row by row and assign the correct Price Level, we use a classification algorithm. For each row of the raw data, the score starts at 0 and then the three criteria are evaluated for each of the Price Levels on the price level CSV. 

For example, for this row in the raw data, each row of the Price Level mapping is given a score based on how many matches there are, with a match in any category being worth 2, versus the default of 1. I manually added a score column so you can see how it ends up picking the correct Price Level.
![Price Level Mapping](Photos/)
![Price Level Mapping](Photos/)
And here is how it assigns the Price Levels to the Johnson-Clark rows:
![Alt Text](Python_NS_Billing_Upload_Automation/JC_PLs.png)
### 3. Create SQL Tables with Mapping for Upload Page
Now that we have seen how our mappings stored in a table can be used in a function to assign Price Levels, we can flesh out the rest of the mapping required to make the final upload form. Instead of making a bunch of different CSV files, as we did before with Price Levels, we will make a SQL database and store all the mappings in tables that we can relate to each other through foreign keys.

After mapping out all the required tables and connections:
![Tables Mapped Out](Photos/)
And then built them using Python and sqlite3:
```Python
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
```

After making the tables, I added some test rows so I could make sure the final upload maker was working correctly. For example, I added a few non-default prices to the prices_db table:
```Python
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
```
Once the code is run, the tables are stored in billing_system.db, ready to be queried as needed.

### 4. Use Streamlit to Make a Webpage to Upload and Transform Fake Data
Now that all of the tables are made, we can make the final upload form! At first, I just used Python to pull from the SQL tables and make the final CSV, but given this project's origins as a continuation of a project I originally made for clients with limited technical backgrounds, I wanted to try something different.

Instead, using Streamlit, I wanted to make a webpage that would allow you to simply upload a CSV of the raw data and have it spit out a completed upload page with all the code running in the background. In order to do this, I would first need to make the logic necessary to populate all the needed columns of the upload:
```Python
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
```
The key element of the above code block is how it aggregates the total number of units for each unique Customer/Item/Price Level/CA Line? combination. Everything else is just taking from various tables, looking at the item code, price level, etc. and pulling the requisite information. For example, in the prior section we saw that one of the rows of the price_db was:
```Python
(jc_name, "1001", "JC-CX-TypeA", 110.00)
```
An aggregate row of the final upload that had Johnson-Clark for Customer, 1001 for Item, and JC-CX-TypeA for Price Level, would then be assigned a price of $110.


Lastly, we use Streamlit to make the user interface:
```Python
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
```
And in the end, the user is able to easily transform the raw data file into an uploadable CSV:'
![The Final Site Upload Steps](/Python NS Billing Upload Automation/GIF.gif)


# What I Learned

Building this end-to-end automation pipeline allowed me to bridge the gap between traditional accounting workflows and modern data engineering. Through this project, I leveled up several core technical competencies:

- **🏗️ Relational Database Schema Design:** Instead of relying on messy, disconnected flat files, I learned how to architect a centralized SQLite database. I mastered utilizing primary keys, mapping out foreign key constraints to enforce data integrity, and establishing a single source of truth for corporate finance logic.
- **🎛️ Feature Engineering & Heuristic Mapping:** I learned how to design a deterministic scoring algorithm (a rule-based heuristic classifier) in Python to handle multi-dimensional matching (Customer, County, and Type). This taught me how to program complex business logic that gracefully handles edge-cases and fallbacks without breaking the pipeline.
- **📊 Advanced Data Aggregation with Pandas:** I deepened my understanding of vectorized data manipulation by using Pandas to handle group-by operations, conditional data flags (`CA Line?`), and structural table merges—replacing resource-heavy loop iterations with clean, scalable, join-based logic.
- **🖥️ Full-Stack Prototyping with Streamlit:** I learned how to wrap complex back-end data pipelines into intuitive, user-friendly web interfaces. This bridged the gap between engineering and operations, proving that powerful backend code can be made easily accessible to non-technical business stakeholders.


### Closing Thoughts

This project was super fun and something I've wanted to do as soon as I finished the Google Advanced Data Analytics course. I think a good next step would be to see how possible it is to use Streamlit and sqllite3 to make it possible for someone to easily add new customers, prices, etc. to the tables. I could imagine building out a whole Python-based system that allows for mapping to be easily updated by people with limited technical backgrounds!
