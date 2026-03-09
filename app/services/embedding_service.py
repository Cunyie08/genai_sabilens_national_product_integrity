import torch
import numpy as np
from PIL import Image
from transformers import CLIPProcessor, CLIPModel


class EmbeddingService:
    def __init__(self):
        if torch.backends.mps.is_available():
            self.device = "mps"
        elif torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"

        self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(self.device)
        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

    def generate_embedding(self, image_input):
        if isinstance(image_input, str):
            image = Image.open(image_input).convert("RGB")
        else:
            image = image_input.convert("RGB")

        inputs = self.processor(images=image, return_tensors="pt").to(self.device)

        with torch.no_grad():
            features = self.model.get_image_features(**inputs)

        vec = features[0].detach().cpu().numpy()
        vec = vec / np.linalg.norm(vec)
        return vec.tolist()