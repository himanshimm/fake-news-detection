"""
Day 1 - Step 1: Data Exploration & Preprocessing
ISOT Fake News Dataset
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-GUI backend — saves to file instead of opening a window
import matplotlib.pyplot as plt
import seaborn as sns
import os
import re

# ── Paths ──────────────────────────────────────────────────────────────────
RAW_DIR       = "data/raw"
PROCESSED_DIR = "data/processed"
os.makedirs(PROCESSED_DIR, exist_ok=True)


# ── 1. Load ────────────────────────────────────────────────────────────────
def load_data():
    true_df = pd.read_csv(f"{RAW_DIR}/True.csv")
    fake_df = pd.read_csv(f"{RAW_DIR}/Fake.csv")

    true_df["label"] = 1   # 1 = Real
    fake_df["label"] = 0   # 0 = Fake

    df = pd.concat([true_df, fake_df], ignore_index=True)
    print(f"✅ Loaded {len(df):,} articles  ({true_df.shape[0]:,} real, {fake_df.shape[0]:,} fake)")
    return df


# ── 2. Explore ─────────────────────────────────────────────────────────────
def explore(df):
    print("\n📊 Shape:", df.shape)
    print("\n📋 Columns:", df.columns.tolist())
    print("\n🔍 Sample:\n", df.head(3))
    print("\n❓ Nulls:\n", df.isnull().sum())
    print("\n📌 Label distribution:\n", df["label"].value_counts())
    print("\n🗂  Subject distribution:\n", df["subject"].value_counts())

    # Word-count stats
    df["text_len"] = df["text"].astype(str).apply(lambda x: len(x.split()))
    print(f"\n📝 Avg text length  — Real: {df[df.label==1]['text_len'].mean():.0f} words  |  Fake: {df[df.label==0]['text_len'].mean():.0f} words")

    return df


# ── 3. Clean ───────────────────────────────────────────────────────────────
def clean_text(text: str) -> str:
    text = str(text)
    # Remove Reuters-style datelines like "WASHINGTON (Reuters) - "
    text = re.sub(r"^[A-Z\s]+\(Reuters\)\s*-\s*", "", text)
    # Collapse extra whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Combine title + text (gives the model more signal)
    df["combined"] = df["title"].fillna("") + " " + df["text"].fillna("")
    df["combined"] = df["combined"].apply(clean_text)

    # Drop rows with very short combined text (likely corrupted)
    before = len(df)
    df = df[df["combined"].str.split().str.len() >= 20].reset_index(drop=True)
    print(f"\n🧹 Removed {before - len(df)} rows with <20 words. Remaining: {len(df):,}")

    # Keep only needed columns
    df = df[["title", "text", "combined", "subject", "label"]]

    return df


# ── 4. Split & Save ────────────────────────────────────────────────────────
def split_and_save(df: pd.DataFrame):
    from sklearn.model_selection import train_test_split

    train_df, temp_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df["label"])
    val_df, test_df   = train_test_split(temp_df, test_size=0.5, random_state=42, stratify=temp_df["label"])

    train_df.to_csv(f"{PROCESSED_DIR}/train.csv", index=False)
    val_df.to_csv(f"{PROCESSED_DIR}/val.csv",   index=False)
    test_df.to_csv(f"{PROCESSED_DIR}/test.csv",  index=False)

    print(f"\n💾 Saved splits:")
    print(f"   Train : {len(train_df):,}")
    print(f"   Val   : {len(val_df):,}")
    print(f"   Test  : {len(test_df):,}")


# ── 5. Quick visualisation ────────────────────────────────────────────────
def visualise(df: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    fig.suptitle("ISOT Dataset — Quick Look", fontsize=14, fontweight="bold")

    # Label distribution
    counts = df["label"].map({1: "Real", 0: "Fake"}).value_counts()
    axes[0].bar(counts.index, counts.values, color=["#4CAF50", "#F44336"])
    axes[0].set_title("Class Distribution")
    axes[0].set_ylabel("Count")
    for i, v in enumerate(counts.values):
        axes[0].text(i, v + 100, f"{v:,}", ha="center", fontweight="bold")

    # Text length by label
    df["text_len"] = df["combined"].str.split().str.len()
    df["label_str"] = df["label"].map({1: "Real", 0: "Fake"})
    axes[1].hist(
        [df[df.label==1]["text_len"], df[df.label==0]["text_len"]],
        bins=50, label=["Real", "Fake"], color=["#4CAF50", "#F44336"], alpha=0.7
    )
    axes[1].set_title("Text Length Distribution")
    axes[1].set_xlabel("Word count")
    axes[1].set_ylabel("Frequency")
    axes[1].legend()

    plt.tight_layout()
    plt.savefig(f"{PROCESSED_DIR}/eda_overview.png", dpi=150)
    print(f"\n📈 EDA chart saved → {PROCESSED_DIR}/eda_overview.png")


# ── Main ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    df = load_data()
    df = explore(df)
    df = preprocess(df)
    split_and_save(df)
    visualise(df)
    print("\n✅ Day 1 preprocessing complete!")
