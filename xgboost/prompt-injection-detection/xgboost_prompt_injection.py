"""
XGBoost Prompt Injection Detection — SageMaker Framework Mode Training Script

Trains an XGBoost classifier to detect prompt injection attacks using TF-IDF
features from the deepset/prompt-injections Hugging Face dataset.

This script runs inside the SageMaker XGBoost DLC container.
"""

import argparse
import os
import pickle

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report, f1_score


def parse_args():
    parser = argparse.ArgumentParser()
    # XGBoost hyperparameters
    parser.add_argument("--max-depth", type=int, default=6)
    parser.add_argument("--eta", type=float, default=0.3)
    parser.add_argument("--num-round", type=int, default=100)
    parser.add_argument("--scale-pos-weight", type=float, default=1.0)
    parser.add_argument("--max-features", type=int, default=5000)
    # SageMaker environment
    parser.add_argument("--model-dir", type=str, default=os.environ.get("SM_MODEL_DIR", "/opt/ml/model"))
    parser.add_argument("--train", type=str, default=os.environ.get("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train"))
    parser.add_argument("--test", type=str, default=os.environ.get("SM_CHANNEL_TEST", "/opt/ml/input/data/test"))
    return parser.parse_args()


def load_data(path):
    """Load CSV data from a SageMaker input channel."""
    files = [os.path.join(path, f) for f in os.listdir(path) if f.endswith(".csv")]
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def main():
    args = parse_args()

    # Load train/test splits
    train_df = load_data(args.train)
    test_df = load_data(args.test)
    print(f"Train: {len(train_df)} samples, Test: {len(test_df)} samples")
    print(f"Label distribution (train): {train_df['label'].value_counts().to_dict()}")

    # TF-IDF feature extraction
    vectorizer = TfidfVectorizer(max_features=args.max_features, ngram_range=(1, 2))
    X_train = vectorizer.fit_transform(train_df["text"].fillna(""))
    X_test = vectorizer.transform(test_df["text"].fillna(""))
    y_train = train_df["label"].values
    y_test = test_df["label"].values

    # Train XGBoost
    dtrain = xgb.DMatrix(X_train, label=y_train)
    dtest = xgb.DMatrix(X_test, label=y_test)

    params = {
        "max_depth": args.max_depth,
        "eta": args.eta,
        "objective": "binary:logistic",
        "eval_metric": "auc",
        "scale_pos_weight": args.scale_pos_weight,
    }

    model = xgb.train(
        params,
        dtrain,
        num_boost_round=args.num_round,
        evals=[(dtrain, "train"), (dtest, "test")],
        verbose_eval=10,
    )

    # Evaluate
    preds = (model.predict(dtest) > 0.5).astype(int)
    print("\n--- Classification Report ---")
    print(classification_report(y_test, preds, target_names=["safe", "injection"]))
    print(f"F1 Score: {f1_score(y_test, preds):.4f}")

    # Save model and vectorizer
    model.save_model(os.path.join(args.model_dir, "xgboost-model"))
    with open(os.path.join(args.model_dir, "tfidf_vectorizer.pkl"), "wb") as f:
        pickle.dump(vectorizer, f)
    print(f"Model saved to {args.model_dir}")


if __name__ == "__main__":
    main()
