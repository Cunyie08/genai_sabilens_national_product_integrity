import json
import faiss
import numpy as np

# Load the embeddings
embeddings = np.load("embeddings.npy")

# Initialize FAISS index
embedding_dim = embeddings.shape[1]  # 512-dimensional embeddings
index = faiss.IndexFlatL2(embedding_dim)  # Using L2 (Euclidean) distance

# Add embeddings to the index
index.add(embeddings)

# Perform a similarity search (e.g., find the 5 most similar products to the first product)
D, I = index.search(embeddings[0:1], 5)  # Search for 5 nearest neighbors to the first product

# Print distances and indices
print("Distances:", D)
print("Indices:", I)

# Load the product index
with open("product_index.json", "r") as f:
    product_index = json.load(f)

# Display the similar products based on indices
for idx in I[0]:
    print("Similar product:", product_index[idx])