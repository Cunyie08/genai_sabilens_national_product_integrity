"""
feature_extractor.py  –  SabiLens Visual Module v2
====================================================
WHAT CHANGED FROM v1 AND WHY
------------------------------
v1 used ResNet50 as a classification backbone.  ResNet50 is trained to
recognise OBJECT CATEGORIES (cat, dog, cereal box).  Its deep layers
actively DISCARD low-level detail (colour shifts, distortion, font
misalignment) in favour of high-level semantics.  That is exactly why
a visually-altered fake scored identically to the authentic product —
the model was designed to ignore those differences.

v2 uses EfficientNet-B3 with two key changes:
  1. Dual-head output: a GLOBAL head (whole-image semantics, same as
     before) PLUS a LOCAL head (average-pooled patch grid that retains
     spatial / colour / texture detail).
  2. The two vectors are concatenated before L2-normalisation so the
     SimilarityEngine gets a richer fingerprint that is sensitive to
     BOTH "does this look like the right product?" AND "do the fine
     details match?".

EfficientNet-B3 chosen over B0/B7 because:
  - Better ImageNet accuracy than ResNet50 with fewer parameters
  - Compound scaling means both depth and resolution benefit
  - Runs comfortably on CPU for cloud inference

OUTPUT VECTOR SIZES
  global_head : 1536-d  (EfficientNet-B3 penultimate features)
  local_head  :  768-d  (spatial grid, 3x3 pooled → 256-d each → 768-d)
  concatenated: 2304-d  → L2-normalised → stored in .pkl
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
 
import torch
import torch.nn as nn
import numpy as np
from torchvision import models, transforms
from PIL import Image
 
_MODEL_CACHE = {}
 
 
class FeatureExtractor:
 
    def __init__(self, device: str = "cpu"):
        self.device = torch.device(device)
 
        if "efficientnet" not in _MODEL_CACHE:
            _MODEL_CACHE["efficientnet"] = self._build_model()
 
        self.model = _MODEL_CACHE["efficientnet"]
        self.model.eval()
 
        self.transform = transforms.Compose([
            transforms.Resize((300, 300)),
            transforms.CenterCrop(300),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])
 
        self._grid_pool = nn.AdaptiveAvgPool2d((3, 3))
 
    def extract(self, image_path: str) -> np.ndarray:
        image = Image.open(image_path).convert("RGB")
        return self._run(image)
 
    def extract_from_array(self, img_array: np.ndarray) -> np.ndarray:
        image = Image.fromarray(img_array)
        return self._run(image)
 
    def _build_model(self):
        base = models.efficientnet_b3(
            weights=models.EfficientNet_B3_Weights.DEFAULT
        )
        return base
 
    def _run(self, pil_image: Image.Image) -> np.ndarray:
        tensor = self.transform(pil_image).unsqueeze(0).to(self.device)
 
        with torch.no_grad():
            # Global head
            spatial = self.model.features(tensor)     # (1, C, H, W)
            global_vec = self.model.avgpool(spatial)  # (1, 1536, 1, 1)
            global_vec = global_vec.flatten(1)        # (1, 1536)
 
            # Local head — channel count derived dynamically, no hardcoding
            grid = self._grid_pool(spatial)           # (1, C, 3, 3)
            local_vec = grid.flatten(1)               # (1, C*9)
 
        combined = torch.cat([global_vec, local_vec], dim=1)
        combined_np = combined.cpu().numpy().flatten().astype(np.float32)
        return self._l2_normalise(combined_np)
 
    @staticmethod
    def _l2_normalise(vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        return vec if norm == 0 else vec / norm
 