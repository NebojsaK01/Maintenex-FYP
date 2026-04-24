import pandas as pd
#import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import spearmanr, linregress

# Load data
df = pd.read_csv("synthetic_sensor_data.csv")

# Keep only the main sensor columns
cols = ["temperature", "vibration", "rpm", "load"]
data = df[cols].copy()

print("===== BASIC DATA SUMMARY =====")
print(data.describe())
print()




# 1. CORRELATION MATRIX

print("===== CORRELATION MATRIX (Pearson) =====")
corr = data.corr(method="pearson")
print(corr)
print()

print("===== MONOTONIC RELATIONSHIPS (Spearman) =====")
pairs = [
    ("load", "temperature"),
    ("load", "vibration"),
    ("load", "rpm"),
    ("temperature", "vibration"),
    ("temperature", "rpm"),
    ("vibration", "rpm")
]

for x, y in pairs:
    rho, p = spearmanr(data[x], data[y])
    print(f"{x} vs {y}: Spearman rho = {rho:.4f}, p-value = {p:.4e}")
print()




# 2. BINNED TREND ANALYSIS

print("===== BINNED LOAD TREND ANALYSIS =====")

# Create load bins
bins = [35, 45, 55, 65, 75, 85, 95, 100]
labels = ["35-45", "45-55", "55-65", "65-75", "75-85", "85-95", "95-100"]

df["load_bin"] = pd.cut(df["load"], bins=bins, labels=labels, include_lowest=True)

trend_table = df.groupby("load_bin", observed=False).agg(
    avg_temperature=("temperature", "mean"),
    avg_vibration=("vibration", "mean"),
    avg_rpm=("rpm", "mean"),
    count=("load", "count")
).reset_index()

print(trend_table)
print()




# 3. LINEAR TREND TESTS

print("===== LINEAR TREND TESTS =====")

def trend_test(x, y, name):
    slope, intercept, r_value, p_value, std_err = linregress(df[x], df[y])
    print(
        f"{name}: slope={slope:.6f}, r={r_value:.4f}, "
        f"r^2={r_value**2:.4f}, p={p_value:.4e}"
    )

trend_test("load", "temperature", "Load -> Temperature")
trend_test("load", "vibration", "Load -> Vibration")
trend_test("load", "rpm", "Load -> RPM")
print()




# 4. VISUAL TESTS

fig, axes = plt.subplots(2, 2, figsize=(12, 10))

# Scatter: Load vs Temperature
axes[0, 0].scatter(df["load"], df["temperature"], alpha=0.15, s=10)
axes[0, 0].set_title("Load vs Temperature")
axes[0, 0].set_xlabel("Load")
axes[0, 0].set_ylabel("Temperature")

# Scatter: Load vs Vibration
axes[0, 1].scatter(df["load"], df["vibration"], alpha=0.15, s=10)
axes[0, 1].set_title("Load vs Vibration")
axes[0, 1].set_xlabel("Load")
axes[0, 1].set_ylabel("Vibration")

# Scatter: Load vs RPM
axes[1, 0].scatter(df["load"], df["rpm"], alpha=0.15, s=10)
axes[1, 0].set_title("Load vs RPM")
axes[1, 0].set_xlabel("Load")
axes[1, 0].set_ylabel("RPM")

# Binned means plot
axes[1, 1].plot(trend_table["load_bin"].astype(str), trend_table["avg_temperature"], marker="o", label="Avg Temp")
axes[1, 1].plot(trend_table["load_bin"].astype(str), trend_table["avg_vibration"], marker="o", label="Avg Vib")
axes[1, 1].plot(trend_table["load_bin"].astype(str), trend_table["avg_rpm"], marker="o", label="Avg RPM")
axes[1, 1].set_title("Average Sensor Values by Load Bin")
axes[1, 1].set_xlabel("Load Bin")
axes[1, 1].set_ylabel("Average Value")
axes[1, 1].legend()

plt.tight_layout()
plt.savefig("synthetic_data_validation.png", dpi=300)
plt.show()

print("Saved plot as synthetic_data_validation.png")
print()


# 5. SIMPLE INTERPRETATION

print("===== INTERPRETATION GUIDE =====")
print("Good synthetic data should show:")
print("- Temperature rising gradually as load increases")
print("- Vibration rising gradually as load increases")
print("- RPM staying more stable than temperature/vibration")
print("- Correlations and bin trends that are smooth, not step-like")

