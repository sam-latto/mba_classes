import pandas
import os
from pathlib import Path

print(os.getcwd())

# Resolve CSV path relative to repo root
repo_root = Path(__file__).resolve().parent.parent
csv_path = repo_root / "data" / "course_data.csv"

df = pandas.read_csv(csv_path)

# Print Column Names
print("Columns:", df.columns.tolist())

# Print Number of Rows
# mber of rows:", len(df))

# Convert skills to a list 
skills = df['skills'].dropna().tolist()
# print("Skills:", skills)

# Convert bid_points to a list
bid_points = df['bid_points'].dropna().tolist()

# Compute the average of the last number in each bid_points entry
def extract_last_number(bp_str):
    last_num = []
    for num in bp_str:
        new_num = num.split(',')
        # Get the last number
        last_num.append(int(new_num[-1]))

    return sum(last_num) / len(last_num)



print(extract_last_number(bid_points))