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


# --- STEP 2: CREATE THE RAW BILLING DATA ---

num_billing_rows = 200  # Generate 200 rows of fake billing data
billing_data = []

for i in range(num_billing_rows):
    # Pick a random client name from the DataFrame
    cust_name = random.choice(df_clients["client_name"])
    
    # Pick random elements directly from our dictionary lists
    item = random.choice(data_mappings["Item"])
    location = random.choice(data_mappings["Location"])
    state = random.choice(data_mappings["State"])
    county = random.choice(data_mappings["County"])
    type_val = random.choice(data_mappings["Type"]) # Renamed to 'type_val' to avoid overriding Python's built-in type() function
    
    # Generate realistic transactional data (Fixed typo 'radint' to 'randint')
    units = round(random.randint(1, 10), 1)
    date = fake.date_between(start_date='-25d', end_date='today')
    
    billing_data.append({
        "Customer": cust_name,
        "Item": item,
        "Location": location,
        "State": state,
        "County": county,
        "Type": type_val,
        "Units": units,          
        "billing_date": date
    })

df_billing = pd.DataFrame(billing_data)


# --- STEP 3: SAVE EVERYTHING TO CSV ---

# Optional: Save your client mapping file if you want to use it for database setup later
df_clients.to_csv("client_mappings.csv", index=False)

# Save the raw billing data
df_billing.to_csv("raw_billing_data.csv", index=False)

print("Test data generated successfully!")
print(f"Generated {num_clients} clients, and {num_billing_rows} billing records.")