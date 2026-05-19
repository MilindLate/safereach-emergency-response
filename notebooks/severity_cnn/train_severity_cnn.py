#!/usr/bin/env python3
"""
SafeReach — EfficientNet-B2 Crash Severity CNN Training
======================================================
Dataset: iRAD crash images (IIT Madras) + COCO + Roboflow crash datasets
Model:   EfficientNet-B2 fine-tuned for 3-class severity classification
Classes: low | medium | critical

Training config (from submission doc §4.1):
  - LR: 1e-4, batch: 32, epochs: 50, early-stopping patience: 7
  - Augmentation: h-flip, brightness, Gaussian blur
  - Target accuracy: ≥ 85% on 200-image held-out test set
"""

import os
import time
import json
import random
from pathlib import Path
from datetime import datetime

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as T
from torchvision.models import efficientnet_b2, EfficientNet_B2_Weights
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
from PIL import Image

# ── Reproducibility ────────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Training on: {DEVICE}")

# ── Config ────────────────────────────────────────────────────────────────────
CONFIG = {
    "num_classes":     3,
    "class_names":     ["low", "medium", "critical"],
    "image_size":      224,
    "batch_size":      32,
    "epochs":          50,
    "lr":              1e-4,
    "weight_decay":    1e-4,
    "patience":        7,           # early stopping
    "dropout":         0.3,
    "train_split":     0.70,
    "val_split":       0.15,
    "test_split":      0.15,
    "model_save_path": "models/severity_cnn.pt",
    "results_path":    "results/cnn_training_results.json",
}


# ── Dataset ───────────────────────────────────────────────────────────────────

class CrashSeverityDataset(Dataset):
    """
    Expects directory structure:
        data/
          train/
            low/      *.jpg
            medium/   *.jpg
            critical/ *.jpg
          val/   ...
          test/  ...
    """

    def __init__(self, root_dir: str, split: str, transform=None):
        self.samples   = []
        self.transform = transform
        self.class_to_idx = {"low": 0, "medium": 1, "critical": 2}

        split_dir = Path(root_dir) / split
        if not split_dir.exists():
            print(f"⚠ Dataset directory {split_dir} not found — generating synthetic stubs.")
            self._generate_stubs(split)
            return

        for class_name, class_idx in self.class_to_idx.items():
            class_dir = split_dir / class_name
            if not class_dir.exists():
                continue
            for img_path in class_dir.glob("*.jpg"):
                self.samples.append((str(img_path), class_idx))
            for img_path in class_dir.glob("*.png"):
                self.samples.append((str(img_path), class_idx))

        print(f"  {split}: {len(self.samples)} samples loaded.")

    def _generate_stubs(self, split):
        """Generate synthetic coloured stubs for demo/CI runs."""
        counts = {"train": 210, "val": 45, "test": 45}
        n = counts.get(split, 30)
        for i in range(n):
            label = i % 3
            self.samples.append((None, label))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        if path is None:
            # Synthetic stub: random noise image
            img = Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
        else:
            img = Image.open(path).convert("RGB")

        if self.transform:
            img = self.transform(img)
        return img, label


# ── Transforms ────────────────────────────────────────────────────────────────

def get_transforms(split: str):
    """
    Training: augmentation for Indian night-time / adverse lighting scenarios.
    Val/Test: deterministic preprocessing only.
    """
    mean = [0.485, 0.456, 0.406]
    std  = [0.229, 0.224, 0.225]

    if split == "train":
        return T.Compose([
            T.Resize((256, 256)),
            T.RandomCrop(CONFIG["image_size"]),
            T.RandomHorizontalFlip(p=0.5),
            T.ColorJitter(brightness=0.3, contrast=0.2, saturation=0.2),
            T.GaussianBlur(kernel_size=3, sigma=(0.1, 1.5)),
            T.RandomRotation(degrees=15),
            T.ToTensor(),
            T.Normalize(mean=mean, std=std),
        ])
    else:
        return T.Compose([
            T.Resize((CONFIG["image_size"], CONFIG["image_size"])),
            T.ToTensor(),
            T.Normalize(mean=mean, std=std),
        ])


# ── Model ─────────────────────────────────────────────────────────────────────

def build_model() -> nn.Module:
    """EfficientNet-B2 with custom classification head for 3 severity classes."""
    model = efficientnet_b2(weights=EfficientNet_B2_Weights.IMAGENET1K_V1)

    # Freeze base layers, fine-tune top 3 blocks
    for name, param in model.named_parameters():
        param.requires_grad = False

    for name, param in model.named_parameters():
        if any(layer in name for layer in ["features.6", "features.7", "features.8", "classifier"]):
            param.requires_grad = True

    in_features = model.classifier[1].in_features
    model.classifier = nn.Sequential(
        nn.Dropout(p=CONFIG["dropout"], inplace=True),
        nn.Linear(in_features, 256),
        nn.ReLU(inplace=True),
        nn.Dropout(p=0.2),
        nn.Linear(256, CONFIG["num_classes"]),
    )

    return model.to(DEVICE)


# ── Training loop ─────────────────────────────────────────────────────────────

def train_epoch(model, loader, optimizer, criterion):
    model.train()
    total_loss, correct, total = 0.0, 0, 0

    for images, labels in loader:
        images, labels = images.to(DEVICE), labels.to(DEVICE)
        optimizer.zero_grad()
        outputs = model(images)
        loss    = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * images.size(0)
        _, predicted = outputs.max(1)
        correct += predicted.eq(labels).sum().item()
        total   += images.size(0)

    return total_loss / total, correct / total


@torch.no_grad()
def evaluate(model, loader, criterion):
    model.eval()
    total_loss, correct, total = 0.0, 0, 0
    all_preds, all_labels = [], []

    for images, labels in loader:
        images, labels = images.to(DEVICE), labels.to(DEVICE)
        outputs = model(images)
        loss    = criterion(outputs, labels)

        total_loss += loss.item() * images.size(0)
        _, predicted = outputs.max(1)
        correct += predicted.eq(labels).sum().item()
        total   += images.size(0)
        all_preds.extend(predicted.cpu().numpy())
        all_labels.extend(labels.cpu().numpy())

    return total_loss / total, correct / total, all_preds, all_labels


# ── Main training pipeline ────────────────────────────────────────────────────

def main():
    print("\n" + "="*60)
    print("  SafeReach — Crash Severity CNN Training")
    print("  Team CtrlAltElite | CoERS IIT Madras 2026")
    print("="*60 + "\n")

    DATA_ROOT = os.environ.get("CRASH_DATASET_PATH", "data/crash_images")

    # Datasets + loaders
    datasets = {
        split: CrashSeverityDataset(DATA_ROOT, split, get_transforms(split))
        for split in ["train", "val", "test"]
    }
    loaders = {
        split: DataLoader(
            ds,
            batch_size=CONFIG["batch_size"],
            shuffle=(split == "train"),
            num_workers=min(4, os.cpu_count() or 1),
            pin_memory=DEVICE.type == "cuda",
        )
        for split, ds in datasets.items()
    }

    print(f"Dataset: {len(datasets['train'])} train | {len(datasets['val'])} val | {len(datasets['test'])} test")

    # Model + optimiser + loss
    model     = build_model()
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total     = sum(p.numel() for p in model.parameters())
    print(f"Model: EfficientNet-B2 | {trainable:,} / {total:,} params trainable\n")

    # Class-weighted loss to handle imbalanced crash severity distribution
    class_weights = torch.tensor([1.0, 1.5, 2.0]).to(DEVICE)  # critical weighted 2×
    criterion = nn.CrossEntropyLoss(weight=class_weights)

    optimizer = optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=CONFIG["lr"],
        weight_decay=CONFIG["weight_decay"],
    )
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=CONFIG["epochs"])

    # Training loop with early stopping
    best_val_acc = 0.0
    patience_cnt = 0
    history      = {"train_loss": [], "val_loss": [], "train_acc": [], "val_acc": []}

    Path("models").mkdir(exist_ok=True)
    Path("results").mkdir(exist_ok=True)

    for epoch in range(1, CONFIG["epochs"] + 1):
        t0 = time.time()

        train_loss, train_acc = train_epoch(model, loaders["train"], optimizer, criterion)
        val_loss, val_acc, _, _ = evaluate(model, loaders["val"], criterion)
        scheduler.step()

        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["train_acc"].append(train_acc)
        history["val_acc"].append(val_acc)

        print(
            f"Epoch {epoch:3d}/{CONFIG['epochs']} | "
            f"Train loss: {train_loss:.4f} acc: {train_acc:.3f} | "
            f"Val loss: {val_loss:.4f} acc: {val_acc:.3f} | "
            f"{time.time()-t0:.1f}s"
        )

        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), CONFIG["model_save_path"])
            print(f"  ✓ Best model saved (val_acc={best_val_acc:.4f})")
            patience_cnt = 0
        else:
            patience_cnt += 1
            if patience_cnt >= CONFIG["patience"]:
                print(f"\n  Early stopping at epoch {epoch} (patience={CONFIG['patience']})")
                break

    # ── Test evaluation ───────────────────────────────────────────────────────
    print("\n" + "─"*40)
    print("  Test Set Evaluation")
    print("─"*40)

    model.load_state_dict(torch.load(CONFIG["model_save_path"], map_location=DEVICE, weights_only=True))
    test_loss, test_acc, preds, labels = evaluate(model, loaders["test"], criterion)

    print(f"  Test accuracy: {test_acc:.4f} ({test_acc*100:.2f}%)")
    print(f"  Test loss:     {test_loss:.4f}")
    print()
    print(classification_report(labels, preds, target_names=CONFIG["class_names"]))

    cm = confusion_matrix(labels, preds)
    print("  Confusion matrix:")
    print(cm)

    # ── Save results ──────────────────────────────────────────────────────────
    results = {
        "training_date":   datetime.now().isoformat(),
        "final_epoch":     len(history["train_loss"]),
        "best_val_acc":    best_val_acc,
        "test_accuracy":   test_acc,
        "test_loss":       test_loss,
        "config":          CONFIG,
        "history":         history,
    }
    with open(CONFIG["results_path"], "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to {CONFIG['results_path']}")

    # ── Training curves ───────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    epochs_range = range(1, len(history["train_loss"]) + 1)

    axes[0].plot(epochs_range, history["train_loss"], label="Train")
    axes[0].plot(epochs_range, history["val_loss"],   label="Validation")
    axes[0].set_title("Loss")
    axes[0].set_xlabel("Epoch")
    axes[0].legend()

    axes[1].plot(epochs_range, history["train_acc"], label="Train")
    axes[1].plot(epochs_range, history["val_acc"],   label="Validation")
    axes[1].axhline(y=0.85, color="r", linestyle="--", label="Target (85%)")
    axes[1].set_title("Accuracy")
    axes[1].set_xlabel("Epoch")
    axes[1].legend()

    plt.tight_layout()
    plt.savefig("results/cnn_training_curves.png", dpi=150)
    print("  Training curves saved to results/cnn_training_curves.png")

    target_met = test_acc >= 0.85
    print(f"\n  {'✅' if target_met else '⚠'} Target accuracy {'MET' if target_met else 'NOT MET'}: "
          f"{test_acc*100:.1f}% (target: 85%)")


if __name__ == "__main__":
    main()
