"""
Day 5 — Fine-tune RoBERTa on ISOT dataset
Run: python src/train.py
"""

import os
import pandas as pd
import numpy as np
import torch
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    EarlyStoppingCallback,
)
from torch.utils.data import Dataset
from sklearn.metrics import accuracy_score, f1_score, classification_report
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
BASE_MODEL   = "hamzab/roberta-fake-news-classification"
DATA_DIR     = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
OUTPUT_DIR   = os.path.join(os.path.dirname(__file__), "..", "models", "fine_tuned")
SUBSET_SIZE = 3000   # rows to sample for CPU training
MAX_LENGTH  = 256    # was 512 — halves memory + time
BATCH_SIZE  = 4      # was 8
NUM_EPOCHS  = 2      # was 3
LEARNING_RATE = 2e-5


# ── Label map ─────────────────────────────────────────────────────────────────
# ISOT: 0 = FAKE, 1 = REAL  (matches hamzab model convention)
ID2LABEL = {0: "FAKE", 1: "REAL"}
LABEL2ID = {"FAKE": 0, "REAL": 1}

# ── Device ────────────────────────────────────────────────────────────────────
device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Device: {device.upper()}")
if device == "cuda":
    logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
else:
    logger.info("No GPU found — training on CPU (this will take several hours, leave it overnight)")


# ── Dataset class ─────────────────────────────────────────────────────────────
class NewsDataset(Dataset):
    def __init__(self, df: pd.DataFrame, tokenizer, max_length: int):
        # Accept either 'text' or combine title + text if both exist
        if "text" in df.columns and "title" in df.columns:
            self.texts = (df["title"].fillna("") + " " + df["text"].fillna("")).tolist()
        elif "text" in df.columns:
            self.texts = df["text"].fillna("").tolist()
        else:
            raise ValueError("DataFrame must have a 'text' column")

        self.labels    = df["label"].astype(int).tolist()
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        enc = self.tokenizer(
            self.texts[idx],
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )
        return {
            "input_ids":      enc["input_ids"].squeeze(),
            "attention_mask": enc["attention_mask"].squeeze(),
            "labels":         torch.tensor(self.labels[idx], dtype=torch.long),
        }


# ── Metrics ───────────────────────────────────────────────────────────────────
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": round(accuracy_score(labels, preds), 4),
        "f1":       round(f1_score(labels, preds, average="weighted"), 4),
    }


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    # 1. Load splits
    logger.info("Loading train / val splits …")
    train_df = pd.read_csv(os.path.join(DATA_DIR, "train.csv"))
    val_df   = pd.read_csv(os.path.join(DATA_DIR, "val.csv"))
    
    logger.info(f"Sampled → Train: {len(train_df):,}, Val: {len(val_df):,}")
    logger.info(f"  Train: {len(train_df):,} rows")
    logger.info(f"  Val:   {len(val_df):,} rows")
    logger.info(f"  Label distribution (train):\n{train_df['label'].value_counts().to_string()}")

    # Sample for CPU training
    if SUBSET_SIZE and len(train_df) > SUBSET_SIZE:
        train_df = train_df.sample(n=SUBSET_SIZE, random_state=42).reset_index(drop=True)
        val_df   = val_df.sample(n=500, random_state=42).reset_index(drop=True)

    # 2. Tokenizer & model
    logger.info(f"Loading base model: {BASE_MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        num_labels=2,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
        ignore_mismatched_sizes=True,
    )
    model.to(device)

    # 3. Datasets
    train_dataset = NewsDataset(train_df, tokenizer, MAX_LENGTH)
    val_dataset   = NewsDataset(val_df,   tokenizer, MAX_LENGTH)

    # 4. Training arguments
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,

        # Core hyper-params
        num_train_epochs=NUM_EPOCHS,
        learning_rate=LEARNING_RATE,
        weight_decay=0.01,
        warmup_ratio=0.1,

        # Batch sizes
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,

        # Evaluation & checkpointing
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        greater_is_better=True,
        save_total_limit=2,          # keep only the 2 best checkpoints

        # Speed-ups
        fp16=torch.cuda.is_available(),   # mixed precision if GPU present
        dataloader_num_workers=0,          # safe default for Windows

        # Logging
        logging_dir=os.path.join(OUTPUT_DIR, "logs"),
        logging_steps=200,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
    )

    # 5. Train
    logger.info("=" * 60)
    logger.info("Starting fine-tuning …")
    logger.info("=" * 60)
    trainer.train()

    # 6. Save final model + tokenizer
    logger.info(f"Saving fine-tuned model → {OUTPUT_DIR}")
    trainer.save_model(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    logger.info("Model saved ✓")

    # 7. Final evaluation
    logger.info("Running final evaluation on validation set …")
    results = trainer.evaluate()
    logger.info(f"Val accuracy : {results['eval_accuracy']:.4f}")
    logger.info(f"Val F1       : {results['eval_f1']:.4f}")

    # 8. Full classification report
    preds_out = trainer.predict(val_dataset)
    preds  = np.argmax(preds_out.predictions, axis=-1)
    labels = preds_out.label_ids

    print("\n── Classification Report ──────────────────────────────")
    print(classification_report(labels, preds, target_names=["FAKE", "REAL"]))
    print("─" * 55)

    logger.info("✅  Day 5 fine-tuning complete!")
    logger.info(f"   Fine-tuned model saved at: {os.path.abspath(OUTPUT_DIR)}")
    logger.info("   Update src/predict.py to load from this path.")


if __name__ == "__main__":
    main()
