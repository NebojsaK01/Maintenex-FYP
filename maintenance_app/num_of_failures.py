import pandas as pd

# Load the dataset
df = pd.read_csv("bausch_and_lomb_style_sensor_data.csv")

# Filter rows where a failure occurred
failures = df[df["failure_event"]  == 1]

# Print all the failures removing the limit on row li,it and show all columns
pd.set_option('display.max_rows', None)   # Remove row limit
pd.set_option('display.max_columns', None) # Show all columns


# Set wide display to prevent line wrapping
pd.set_option('display.width', 1000)# wide enough


# Print the total num of fails
print(f"Total failures in dataset: {len(failures)} \n")

# Show first 100 failures ->> there's 100 failures total
print(failures.head(100))


"""

the normal range of the vars:

temp: 55-65
vibration: 0.05 -> 0.15
rpm: 1400 -> 1500
load: 50->70

index +2




"""