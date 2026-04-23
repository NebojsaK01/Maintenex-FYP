import math

def smooth_score(value, low_start, high_end):
    if value <= low_start:
        return 0.0
    if value >= high_end:
        return 1.0

    x = (value - low_start) / (high_end - low_start)
    return x * x * (3 - 2 * x)


def rpm_risk_score(rpm):
    ideal_low = 1420
    ideal_high = 1480
    critical_low = 1380
    critical_high = 1500

    if ideal_low <= rpm <= ideal_high:
        return 0.0

    if rpm < ideal_low:
        return smooth_score(ideal_low - rpm, 0, ideal_low - critical_low)

    return smooth_score(rpm - ideal_high, 0, critical_high - ideal_high)


def get_risk(temp, vib, rpm, load, days):
    temp_score = smooth_score(temp, 65, 90)
    vib_score = smooth_score(vib, 0.10, 0.40)
    load_score = smooth_score(load, 60, 98)
    days_score = smooth_score(days, 20, 180)
    rpm_score = rpm_risk_score(rpm)

    weighted = (
        temp_score * 0.24 +
        vib_score * 0.30 +
        rpm_score * 0.16 +
        load_score * 0.18 +
        days_score * 0.12
    )

    combo_bonus = 0.0

    if temp > 75 and vib > 0.18:
        combo_bonus += 0.08
    if load > 85 and days > 120:
        combo_bonus += 0.07
    if vib > 0.25 and rpm_score > 0.5:
        combo_bonus += 0.08
    if temp > 82 and load > 90:
        combo_bonus += 0.07

    raw_risk = min(1.0, weighted + combo_bonus)
    risk = min(1.0, math.pow(raw_risk, 0.6)) # Non-linear scaling for better mid-range sensitivity

    return risk * 100


print("===== SLIDER BEHAVIOR TESTS =====\n")


# Temperature
print("Temperature Increase Test:")
for t in [50, 60, 70, 80, 90]:
    print(f"Temp={t} -> {get_risk(t, 0.10, 1450, 70, 30):.2f}%")
print()


# Vibration
print("Vibration Increase Test:")
for v in [0.05, 0.10, 0.20, 0.30, 0.45]:
    print(f"Vibration={v} -> {get_risk(65, v, 1450, 70, 30):.2f}%")
print()


# Load
print("Load Increase Test:")
for l in [40, 60, 75, 90, 98]:
    print(f"Load={l} -> {get_risk(65, 0.10, 1450, l, 30):.2f}%")
print()


# Days
print("Days Since Service Test:")
for d in [0, 30, 60, 120, 180]:
    print(f"Days={d} -> {get_risk(65, 0.10, 1450, 70, d):.2f}%")
print()


# Extreme vs Safe
print("Extreme vs Safe:")
safe = get_risk(60, 0.08, 1450, 60, 10)
extreme = get_risk(95, 0.45, 1550, 98, 180)

print(f"Safe: {safe:.2f}%")
print(f"Extreme: {extreme:.2f}%")