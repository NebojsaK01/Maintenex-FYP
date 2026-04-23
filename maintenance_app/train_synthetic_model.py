import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report, roc_auc_score

# Load dataset
df = pd.read_csv("synthetic_sensor_data.csv")

# Build a practical machine-risk target from the CSV fields the app actually uses.
# This is not "guaranteed failure"; it is "risky operating condition".
def risk_score(row):
    score = 0

    # Temperature
    if row["temperature"] > 75:
        score += 1
    if row["temperature"] > 82:
        score += 2

    # Vibration
    if row["vibration"] > 0.18:
        score += 1
    if row["vibration"] > 0.25:
        score += 2

    # RPM
    if row["rpm"] > 1480 or row["rpm"] < 1420:
        score += 1
    if row["rpm"] > 1500 or row["rpm"] < 1380:
        score += 2

    # Load
    if row["load"] > 85:
        score += 1
    if row["load"] > 95:
        score += 2

    # Days since service from CSV timeline
    days_since_service = row["day_in_cycle"] - 1
    if days_since_service > 120:
        score += 1
    if days_since_service > 160:
        score += 2

    return score

df["risk_score_raw"] = df.apply(risk_score, axis=1)

# Binary target: high-risk condition
# This threshold makes the output responsive but not insane.
df["risk_target"] = (df["risk_score_raw"] >= 3).astype(int)

# Feature used by the app
df["days_since_service"] = df["day_in_cycle"] - 1

FEATURES = [
    "temperature",
    "vibration",
    "rpm",
    "load",
    "days_since_service"
]

TARGET = "risk_target"

X = df[FEATURES]
y = df[TARGET]

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

base_model = RandomForestClassifier(
    n_estimators=500,
    max_depth=10,
    min_samples_leaf=2,
    class_weight={0: 1, 1: 3},
    random_state=42,
    n_jobs=-1
)

# Calibrate probabilities so the percentages feel smoother
model = CalibratedClassifierCV(
    estimator=base_model,
    method="isotonic",
    cv=3
)

model.fit(X_train, y_train)

y_pred = model.predict(X_test)
y_prob = model.predict_proba(X_test)[:, 1]

print("Classification Report:")
print(classification_report(y_test, y_pred, digits=4))
print("ROC-AUC:", round(roc_auc_score(y_test, y_prob), 4))

joblib.dump(model, "synthetic_risk_model.pkl")
print("Model saved as synthetic_risk_model.pkl")



"""

I initially trained a Random Forest classifier to predict machine risk, 
but since the target was derived from rule-based thresholds, the model 
learned those rules directly and produced binary outputs. 
I then replaced it with a continuous risk scoring function to improve smoothness and usability.



The ML model achieved high accuracy but lacked practical usability due to step-like predictions. 
A deterministic scoring system provided better control and interpretability.


The ML model was used to validate relationships between sensor inputs and machine risk,
but a deterministic scoring model was used in the final system for better interpretability and user experience.
"""