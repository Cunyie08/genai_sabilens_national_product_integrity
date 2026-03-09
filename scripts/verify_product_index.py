import json

# Load the product index
with open("product_index.json", "r") as f:
    product_index = json.load(f)

# Check the product index
print("Product index:", product_index)
print("Number of products:", len(product_index))