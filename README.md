# Background
In my previous role, I worked on building tools to automate various accounting functions. Using mostly advanced Google Sheets formulas and Google Apps Script I was able to take previously time consuming manual tasks and turn them into easily understandable and shareable spreadsheet-based tools. While in this role, the project I spent the most time on was rebuilding our tool to automate the creation of invoices in Netsuite. 

(Add part about why I did this project: Make fake data, add price levels to raw data using mapping, setting up SQL database with tables that have mapping logic, then making streamlit webpage)

# Tools I Used

- **Python:** Everything from the fake data to the webpage to upload the raw data was made in Python! 
- **Visual Studio Code:** Used to run all the code.
- **Git & GitHub:** Essential for version control and sharing my Python scripts and analysis, ensuring collaboration and project tracking.

While coding, I also made extensive use of online tutorials and the free AI Google Gemini, especially to help with the faker, sqllite3, and streamlit portions of the code. Combined, I was able to use the AI to introduce me to the best ways to perform specific tasks (ex. "What's the best way to use SQL and Python together) with online resources then allowing me to learn and troubleshoot issues I ran into with the initial AI-assisted code. Ultimately, this was a project for learning how to use Python, so I still went out of my way to understand exactly how everything functions and fits together, and in the end, I learned a ton!

Check out the Python code I used here: [AdventureWorks Queries](Adventureworks.session.sql)

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

### 3. Create SQL Tables with Mapping for Upload Page
### 4. Use Streamlit to Make a Webpage to Upload and Transform Fake Data


```sql
SELECT ROUND(SUM(salesterritory.salesytd),2) AS Total_Sales
FROM sales.salesterritory
```
![Output](Photos/1.png)

### 2. Sales by Region
```sql
SELECT ROUND(SUM(salesterritory.salesytd),2) AS Region_Sales, salesterritory.group
FROM sales.salesterritory
GROUP BY salesterritory.group
```
![Output](Photos/3.png)

### 3. Sales by Year
```sql
SELECT
ROUND(SUM(totaldue),2) AS Sales,
DATE_PART('year', salesorderheader.modifieddate::date) AS year_sold
FROM sales.salesorderheader
GROUP BY year_sold
ORDER BY Sales DESC
```
![Output](Photos/4.png)

### 4. Sales By Store
```sql
-- Step 1: Join to match PersonID for each BuisnessEntityID
SELECT
s.businessentityid,
be.personid,
s.name,
s.salespersonid
FROM sales.store AS s
LEFT JOIN person.businessentitycontact AS be ON
s.businessentityid = be.businessentityid
```
![Output](Photos/5.png)

```sql
-- Step 2: Join to match CustomerID for each PersonID
WITH id_table AS
(SELECT
s.businessentityid,
be.personid,
s.name,
s.salespersonid
FROM sales.store AS s
LEFT JOIN person.businessentitycontact AS be ON
s.businessentityid = be.businessentityid)

SELECT 
id_table.name,
cid.customerid
FROM id_table
LEFT JOIN sales.customer AS cid ON
id_table.personID = cid.personID
```
![Output](Photos/6.png)

```sql
--Step 3: Join Sales Table using CustomerID to Find Sales by Store 
WITH sales_by_store AS 
(
    WITH id_table AS
    (SELECT
    s.businessentityid,
    be.personid,
    s.name,
    s.salespersonid
    FROM sales.store AS s
    LEFT JOIN person.businessentitycontact AS be ON
    s.businessentityid = be.businessentityid)

    SELECT 
    id_table.name,
    cid.customerid
    FROM id_table
    LEFT JOIN sales.customer AS cid ON
    id_table.personID = cid.personID
)

SELECT 
    sales_by_store.name,
    ROUND(SUM(salesorderheader.totaldue),2) AS tot_store_sales
FROM sales_by_store
INNER JOIN sales.salesorderheader ON
sales_by_store.customerID = salesorderheader.customerID
GROUP BY sales_by_store.name
ORDER BY tot_store_sales DESC
```
![Output](Photos/7.png)

### 5. Total Order Quantity
```sql
SELECT COUNT(DISTINCT salesorderdetail.salesorderdetailid) AS Total_Orders
FROM sales.salesorderdetail
```
![Output](Photos/9.png)

### 6. Total Number of Products
```sql
SELECT COUNT(DISTINCT product.productid) AS tot_products
FROM production.product
```
![Output](Photos/10.png)

### 7. Count of Products and Average Profit by Category
```sql
SELECT pro_cat.productcategoryID, 
pro_cat.name,
COUNT(pro_cat.productcategoryID) AS pro_cat_count,
ROUND(AVG(product.listprice),2) AS avg_list_price,
ROUND(AVG(product.standardcost),2) AS avg_cost,
ROUND(AVG(product.listprice),2)-ROUND(AVG(product.standardcost),2) as avg_profit
FROM production.product
INNER JOIN production.productsubcategory AS sub_cat ON --Inner Join so we can get rid of products with no listed category
product.productsubcategoryID = sub_cat.productsubcategoryID
INNER JOIN production.productcategory AS pro_cat ON
sub_cat.productcategoryID = pro_cat.productcategoryID
GROUP BY pro_cat.productcategoryID
ORDER BY avg_profit DESC, pro_cat_count DESC
```
![Output](Photos/11.png)

### 8. Count of Products and Average Profit by Subcategory 
```sql
SELECT sub_cat.productsubcategoryID, 
sub_cat.name,
COUNT(sub_cat.productsubcategoryID) AS sub_cat_count, 
ROUND(AVG(product.listprice),2) AS avg_list_price,
ROUND(AVG(product.standardcost),2) AS avg_cost,
ROUND(AVG(product.listprice),2)-ROUND(AVG(product.standardcost),2) as avg_profit
FROM production.product
INNER JOIN production.productsubcategory AS sub_cat ON --Inner Join so we can get rid of products with no listed category
product.productsubcategoryID = sub_cat.productsubcategoryID
INNER JOIN production.productcategory AS pro_cat ON
sub_cat.productcategoryID = pro_cat.productcategoryID
GROUP BY sub_cat.productsubcategoryID
ORDER BY avg_profit DESC, sub_cat_count DESC
```
![Output](Photos/12.png)

# What I Learned

From working on this project, I've learned many important basic and advanced SQL skills:

- **🧩 Working With Large Databases:** Worked with queries where I needed to merge more than two tables, using WITH clauses to make temporary results sets. This also improved my understanding of large relational databases. Deciding which tables to use in my joins to efficiently get all of the information I needed was a fun and rewarding challenge to tackle. 
- **📊 Data Aggregation:** Used GROUP BY and aggregate functions like COUNT() and AVG() to find key insights in the data.
- **💡 Analytical Wizardry:** Leveled up my real-world puzzle-solving skills, turning questions into actionable, insightful SQL queries.


### Closing Thoughts
This project only touches the surface of all the insights that could be mined from the AdventureWorks database. I learned so much even just figuring out how to use PSQL and diagnose error messages I was recieving when trying to load the database into PostgreSql. This project has given me the confidence to work on future projects using databases with dozens of tables.
