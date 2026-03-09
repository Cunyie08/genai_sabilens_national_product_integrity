import os
import json

DATASET_FOLDER = "reference_dataset"
REQUIRED = {"front.jpg"}
OPTIONAL = {"back.jpg", "left.jpg", "right.jpg", "top.jpg", "bottom.jpg"}

def compute_stats():
    total_products = 0
    optional_counts = {view: 0 for view in OPTIONAL}

    for product in os.listdir(DATASET_FOLDER):
        product_path = os.path.join(DATASET_FOLDER, product)
        if not os.path.isdir(product_path):
            continue

        total_products += 1
        files = set(os.listdir(product_path))

        for view in OPTIONAL:
            if view in files:
                optional_counts[view] += 1

    print("\nDataset Statistics\n")

    for view, count in optional_counts.items():
        percentage = (count / total_products) * 100
        print(f"{view}: {count}/{total_products} ({percentage:.1f}%)")

    print(f"\nTotal products: {total_products}")

if __name__ == "__main__":
    compute_stats()