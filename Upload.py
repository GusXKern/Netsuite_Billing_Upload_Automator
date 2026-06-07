import pandas as pd

# Fetch the exact client names we generated previously
df_clients = pd.read_csv("client_mappings.csv")
customer_list = df_clients["client_name"].tolist()

# Define the rule matrix
rules = [
    # Rule for Powell (Ignores County and Type)
    {
        "Customer": customer_list[0], 
        "County": "ANY", 
        "Type": "ANY", 
        "Price_Level_Name": "Powell Flat Rate Rule"
    },
    
    # Rules for Johnson-Clark (Explicitly depends on County and Type)
    {"Customer": customer_list[1], "County": "County X", "Type": "A", "Price_Level_Name": "JC-CX-TypeA"},
    {"Customer": customer_list[1], "County": "County X", "Type": "B", "Price_Level_Name": "JC-CX-TypeB"},
    {"Customer": customer_list[1], "County": "County Y", "Type": "A", "Price_Level_Name": "JC-CY-TypeA"},
    {"Customer": customer_list[1], "County": "County Y", "Type": "B", "Price_Level_Name": "JC-CY-TypeB"},
    
    # Rules for Peterson Inc (Depends on County, ignores Type)
    {"Customer": "Peterson Inc", "County": "County X", "Type": "ANY", "Price_Level_Name": "PI-CX"},
    {"Customer": "Peterson Inc", "County": "County Y", "Type": "ANY", "Price_Level_Name": "PI-CY"},
    
    # DYNAMIC CATCH-ALL: Uses a placeholder string for the customer name
    {"Customer": "DEFAULT", "County": "ANY", "Type": "ANY", "Price_Level_Name": "{Customer} Flat Rate Rule"}
]

df_rules = pd.DataFrame(rules)
df_rules.to_csv("price_level_rules.csv", index=False)
print("Created price_level_rules.csv successfully!")