"""
External classifier validation for cover query indistinguishability.

Addresses the #1 gap from review: "same model generates and evaluates."
Trains a DistilBERT classifier on (real, cover) pairs to test whether
a dedicated ML model can distinguish what a prompted LLM adversary cannot.

Usage:
  # Step 1: Generate labeled training data (no LLM needed, uses cover_generator)
  python classifier_validation.py generate --n-sets 1000

  # Step 2: Train DistilBERT classifier
  python classifier_validation.py train

  # Step 3: Evaluate
  python classifier_validation.py evaluate

  # All-in-one:
  python classifier_validation.py run --n-sets 1000

Requirements:
  pip install torch transformers datasets scikit-learn
"""

import argparse
import json
import random
from collections import Counter
from pathlib import Path

from cover_generator import generate_cover_set_raw, sanitize_query, classify_domain
from dataset import SANITIZED_QUERIES, SENSITIVE_QUERIES, NON_SENSITIVE_QUERIES

DATA_DIR = Path(__file__).parent / "data"
RESULTS_DIR = Path(__file__).parent / "results"
MODEL_DIR = Path(__file__).parent / "models"


# ─────────────────────────────────────────────
# Phase 1: Data Generation
# ─────────────────────────────────────────────

def generate_training_data(n_sets: int = 1000, k: int = 4, seed: int = 42):
    """Generate labeled (real=1, cover=0) query pairs using the v5 algorithm.

    Uses only the cover_generator module — no LLM calls needed.
    Critical: source queries are balanced across top-4 domains so the classifier
    cannot exploit domain distribution as a signal for "real" vs "cover."
    """
    random.seed(seed)

    # Build a pool of sanitized queries
    query_pool = list(SANITIZED_QUERIES)
    for q in SENSITIVE_QUERIES:
        sanitized = sanitize_query(q)
        if len(sanitized.split()) >= 5:
            query_pool.append(sanitized)
    query_pool.extend(NON_SENSITIVE_QUERIES)
    query_pool = list(set(query_pool))

    # Group queries by domain and balance sampling across top-4
    from cover_generator import TOP_DOMAINS
    domain_buckets: dict[str, list[str]] = {d: [] for d in TOP_DOMAINS}
    other_queries = []
    for q in query_pool:
        d = classify_domain(q)
        if d in domain_buckets:
            domain_buckets[d].append(q)
        else:
            other_queries.append(q)

    bucket_sizes = {d: len(qs) for d, qs in domain_buckets.items()}
    print(f"Query pool size: {len(query_pool)}")
    print(f"  Domain buckets: {bucket_sizes}")

    examples = []
    set_id = 0
    domains_cycle = TOP_DOMAINS * (n_sets // len(TOP_DOMAINS) + 1)

    for i in range(n_sets):
        # Cycle through top-4 domains equally so each is "real" 25% of the time
        target_domain = domains_cycle[i]
        bucket = domain_buckets[target_domain]
        if not bucket:
            base_query = random.choice(query_pool)
        else:
            base_query = random.choice(bucket)
        query_seed = seed + i

        try:
            shuffled, real_idx, domain, template, cover_domains = generate_cover_set_raw(
                base_query, k=k, seed=query_seed, presanitized=True
            )
        except Exception as e:
            print(f"  Set {i}: generation failed ({e}), skipping")
            continue

        for j, query in enumerate(shuffled):
            label = 1 if j == real_idx else 0
            examples.append({
                "text": query,
                "label": label,
                "set_id": set_id,
                "domain": classify_domain(query),
                "position_in_set": j,
            })

        set_id += 1

        if (i + 1) % 200 == 0:
            print(f"  Generated {i+1}/{n_sets} sets ({len(examples)} examples)")

    # Stats
    labels = Counter(e["label"] for e in examples)
    domains = Counter(e["domain"] for e in examples)
    print(f"\nGenerated {len(examples)} examples across {set_id} sets")
    print(f"  Labels: real={labels[1]}, cover={labels[0]}")
    print(f"  Domains: {dict(domains)}")

    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / "classifier_training_data.json"
    with open(out_path, "w") as f:
        json.dump(examples, f, indent=2)
    print(f"Saved to {out_path}")

    return examples


# ─────────────────────────────────────────────
# Phase 2: Training
# ─────────────────────────────────────────────

def train_classifier(
    data_path: str | None = None,
    model_name: str = "distilbert-base-uncased",
    epochs: int = 10,
    batch_size: int = 16,
    lr: float = 2e-5,
    patience: int = 3,
    seed: int = 42,
):
    """Fine-tune DistilBERT on real-vs-cover classification."""
    try:
        import torch
        from torch.utils.data import DataLoader, Dataset
        from transformers import (
            AutoTokenizer, AutoModelForSequenceClassification,
            get_linear_schedule_with_warmup,
        )
        from sklearn.model_selection import GroupShuffleSplit
    except ImportError:
        print("ERROR: Training requires: pip install torch transformers scikit-learn")
        return None

    random.seed(seed)
    torch.manual_seed(seed)

    # Load data
    if data_path is None:
        data_path = DATA_DIR / "classifier_training_data.json"
    with open(data_path) as f:
        examples = json.load(f)

    texts = [e["text"] for e in examples]
    labels = [e["label"] for e in examples]
    set_ids = [e["set_id"] for e in examples]

    # Split by set_id (queries from same set never in both train and test)
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=seed)
    train_idx, temp_idx = next(splitter.split(texts, labels, groups=set_ids))

    # Split temp into val/test
    temp_texts = [texts[i] for i in temp_idx]
    temp_labels = [labels[i] for i in temp_idx]
    temp_sets = [set_ids[i] for i in temp_idx]
    splitter2 = GroupShuffleSplit(n_splits=1, test_size=0.5, random_state=seed)
    val_idx_rel, test_idx_rel = next(splitter2.split(temp_texts, temp_labels, groups=temp_sets))
    val_idx = [temp_idx[i] for i in val_idx_rel]
    test_idx = [temp_idx[i] for i in test_idx_rel]

    print(f"Split: train={len(train_idx)}, val={len(val_idx)}, test={len(test_idx)}")
    print(f"  Train label distribution: {Counter(labels[i] for i in train_idx)}")
    print(f"  Test label distribution:  {Counter(labels[i] for i in test_idx)}")

    # Tokenize
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    class QueryDataset(Dataset):
        def __init__(self, indices):
            self.indices = indices

        def __len__(self):
            return len(self.indices)

        def __getitem__(self, idx):
            i = self.indices[idx]
            enc = tokenizer(texts[i], truncation=True, max_length=128,
                            padding="max_length", return_tensors="pt")
            return {
                "input_ids": enc["input_ids"].squeeze(0),
                "attention_mask": enc["attention_mask"].squeeze(0),
                "labels": torch.tensor(labels[i], dtype=torch.long),
            }

    train_loader = DataLoader(QueryDataset(train_idx), batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(QueryDataset(val_idx), batch_size=batch_size)
    test_loader = DataLoader(QueryDataset(test_idx), batch_size=batch_size)

    # Model
    device = torch.device("mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2)
    model.to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    total_steps = len(train_loader) * epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=int(0.1 * total_steps), num_training_steps=total_steps
    )

    # Training loop with early stopping
    best_val_loss = float("inf")
    patience_counter = 0

    for epoch in range(epochs):
        model.train()
        total_loss = 0
        for batch in train_loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            outputs = model(**batch)
            loss = outputs.loss
            loss.backward()
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()
            total_loss += loss.item()

        avg_train_loss = total_loss / len(train_loader)

        # Validation
        model.eval()
        val_loss = 0
        val_correct = 0
        val_total = 0
        with torch.no_grad():
            for batch in val_loader:
                batch = {k: v.to(device) for k, v in batch.items()}
                outputs = model(**batch)
                val_loss += outputs.loss.item()
                preds = outputs.logits.argmax(dim=-1)
                val_correct += (preds == batch["labels"]).sum().item()
                val_total += len(batch["labels"])

        avg_val_loss = val_loss / len(val_loader)
        val_acc = val_correct / val_total

        print(f"  Epoch {epoch+1}/{epochs}: train_loss={avg_train_loss:.4f} val_loss={avg_val_loss:.4f} val_acc={val_acc:.1%}")

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            patience_counter = 0
            # Save best model
            MODEL_DIR.mkdir(exist_ok=True)
            model.save_pretrained(MODEL_DIR / "best_classifier")
            tokenizer.save_pretrained(MODEL_DIR / "best_classifier")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"  Early stopping at epoch {epoch+1}")
                break

    # Save test indices for evaluation
    with open(DATA_DIR / "test_indices.json", "w") as f:
        json.dump([int(i) for i in test_idx], f)

    print(f"\nBest model saved to {MODEL_DIR / 'best_classifier'}")
    return model


# ─────────────────────────────────────────────
# Phase 3: Evaluation
# ─────────────────────────────────────────────

def evaluate_classifier(model_path: str | None = None):
    """Evaluate the trained classifier. Reports ROC-AUC, per-domain AUC, and set-level accuracy."""
    try:
        import torch
        from torch.utils.data import DataLoader, Dataset
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        from sklearn.metrics import (
            roc_auc_score, precision_score, recall_score, f1_score,
            accuracy_score, classification_report,
        )
        import numpy as np
    except ImportError:
        print("ERROR: Evaluation requires: pip install torch transformers scikit-learn numpy")
        return None

    if model_path is None:
        model_path = MODEL_DIR / "best_classifier"

    # Load model
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    device = torch.device("mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()

    # Load data
    with open(DATA_DIR / "classifier_training_data.json") as f:
        examples = json.load(f)
    with open(DATA_DIR / "test_indices.json") as f:
        test_indices = json.load(f)

    test_examples = [examples[i] for i in test_indices]
    texts = [e["text"] for e in test_examples]
    labels = [e["label"] for e in test_examples]
    set_ids = [e["set_id"] for e in test_examples]
    domains = [e["domain"] for e in test_examples]

    # Get predictions
    all_probs = []
    all_preds = []

    for i in range(0, len(texts), 32):
        batch_texts = texts[i:i+32]
        enc = tokenizer(batch_texts, truncation=True, max_length=128,
                        padding=True, return_tensors="pt").to(device)
        with torch.no_grad():
            outputs = model(**enc)
            probs = torch.softmax(outputs.logits, dim=-1)[:, 1].cpu().numpy()
            preds = outputs.logits.argmax(dim=-1).cpu().numpy()
        all_probs.extend(probs.tolist())
        all_preds.extend(preds.tolist())

    # Overall metrics
    labels_arr = np.array(labels)
    probs_arr = np.array(all_probs)
    preds_arr = np.array(all_preds)

    roc_auc = roc_auc_score(labels_arr, probs_arr)
    accuracy = accuracy_score(labels_arr, preds_arr)
    precision = precision_score(labels_arr, preds_arr)
    recall = recall_score(labels_arr, preds_arr)
    f1 = f1_score(labels_arr, preds_arr)

    print("\n" + "=" * 60)
    print("CLASSIFIER VALIDATION RESULTS")
    print("=" * 60)
    print(f"\n  ROC-AUC:    {roc_auc:.4f}  (0.50 = random, 1.0 = perfect detection)")
    print(f"  Accuracy:   {accuracy:.1%}")
    print(f"  Precision:  {precision:.1%}")
    print(f"  Recall:     {recall:.1%}")
    print(f"  F1:         {f1:.1%}")
    print(f"\n  Interpretation:")
    if roc_auc < 0.55:
        print(f"    PASS: Classifier cannot distinguish real from cover (AUC ~ random)")
    elif roc_auc < 0.65:
        print(f"    MARGINAL: Slight signal detected, covers may need improvement")
    else:
        print(f"    FAIL: Classifier can distinguish real from cover (AUC={roc_auc:.2f})")

    # Per-domain AUC
    print(f"\n  Per-domain ROC-AUC:")
    unique_domains = sorted(set(domains))
    domain_aucs = {}
    for d in unique_domains:
        d_mask = [i for i, dom in enumerate(domains) if dom == d]
        if len(d_mask) < 10:
            continue
        d_labels = labels_arr[d_mask]
        d_probs = probs_arr[d_mask]
        if len(set(d_labels)) < 2:
            continue
        d_auc = roc_auc_score(d_labels, d_probs)
        domain_aucs[d] = d_auc
        print(f"    {d:>15}: {d_auc:.4f} (n={len(d_mask)})")

    # Set-level accuracy (the metric comparable to Benchmark C)
    # For each set: does the classifier rank the real query highest?
    unique_sets = sorted(set(set_ids))
    set_correct = 0
    set_total = 0
    for sid in unique_sets:
        s_mask = [i for i, s in enumerate(set_ids) if s == sid]
        if not s_mask:
            continue
        s_labels = [labels[i] for i in s_mask]
        s_probs = [all_probs[i] for i in s_mask]

        if 1 not in s_labels:
            continue  # no real query in this set's test split

        # Highest probability = classifier's guess for "real"
        best_idx = max(range(len(s_probs)), key=lambda i: s_probs[i])
        if s_labels[best_idx] == 1:
            set_correct += 1
        set_total += 1

    set_accuracy = set_correct / set_total if set_total > 0 else 0

    print(f"\n  Set-level detection (comparable to Benchmark C):")
    print(f"    Classifier picks real query as top-ranked: {set_accuracy:.1%} ({set_correct}/{set_total})")
    print(f"    Random baseline: 25.0%")
    if set_accuracy <= 0.30:
        print(f"    PASS: Near random baseline")
    elif set_accuracy <= 0.40:
        print(f"    MARGINAL: Slight advantage over random")
    else:
        print(f"    FAIL: Classifier has significant detection ability")

    # Save results
    RESULTS_DIR.mkdir(exist_ok=True)
    result = {
        "roc_auc": roc_auc,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "set_level_accuracy": set_accuracy,
        "set_level_n": set_total,
        "per_domain_auc": domain_aucs,
        "n_test_examples": len(test_examples),
    }
    out_path = RESULTS_DIR / "classifier_results.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nResults saved to {out_path}")

    return result


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="External Classifier Validation")
    parser.add_argument("command", choices=["generate", "train", "evaluate", "run"],
                        help="Phase to run (or 'run' for all)")
    parser.add_argument("--n-sets", type=int, default=1000,
                        help="Number of cover sets to generate")
    parser.add_argument("--model", default="distilbert-base-uncased",
                        help="HuggingFace model name for classifier")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.command in ("generate", "run"):
        generate_training_data(n_sets=args.n_sets, seed=args.seed)

    if args.command in ("train", "run"):
        train_classifier(
            model_name=args.model,
            epochs=args.epochs,
            batch_size=args.batch_size,
            seed=args.seed,
        )

    if args.command in ("evaluate", "run"):
        evaluate_classifier()


if __name__ == "__main__":
    main()
