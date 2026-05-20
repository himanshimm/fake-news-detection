# save as test_model.py in your project root, then run: python test_model.py

import pandas as pd
import sys, os
sys.path.append("src")
from predict import predict
from sklearn.metrics import accuracy_score, f1_score, classification_report

print("Loading test set...")
test_df = pd.read_csv("data/processed/test.csv")

# Sample 500 rows so it doesn't take forever on CPU
test_df = test_df.sample(500, random_state=42).reset_index(drop=True)

print("Running predictions on 500 test articles...")
preds, labels = [], []

for i, row in test_df.iterrows():
    result = predict(row["combined"])
    preds.append(0 if result["label"] == "FAKE" else 1)
    labels.append(row["label"])
    if i % 50 == 0:
        print(f"  {i}/500...")

acc = accuracy_score(labels, preds)
f1  = f1_score(labels, preds, average="weighted")

print(f"\n── Results ──────────────────────────")
print(f"  Accuracy : {acc*100:.2f}%")
print(f"  F1 Score : {f1:.4f}")
print(f"─────────────────────────────────────")
print(classification_report(labels, preds, target_names=["FAKE", "REAL"]))