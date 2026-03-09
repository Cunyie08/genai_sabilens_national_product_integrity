import os
import shutil

RAW_FOLDER = "raw_images"
OUTPUT_FOLDER = "reference_dataset"

VIEWS = ["front", "back", "left", "right", "top", "bottom"]

def get_product_name(filename):
    name = filename.replace(".jpg", "")
    parts = name.split("_")
    view = parts[-1]

    if view not in VIEWS:
        return None, None

    product_name = "_".join(parts[:-1])
    return product_name, view


def structure_dataset():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    for file in os.listdir(RAW_FOLDER):
        if not file.endswith(".jpg"):
            continue

        product_name, view = get_product_name(file)
        if product_name is None:
            print(f"Skipping {file}")
            continue

        product_dir = os.path.join(OUTPUT_FOLDER, product_name)
        os.makedirs(product_dir, exist_ok=True)

        src_path = os.path.join(RAW_FOLDER, file)
        dst_path = os.path.join(product_dir, f"{view}.jpg")

        shutil.copy(src_path, dst_path)

    print("Dataset structured successfully.")


if __name__ == "__main__":
    structure_dataset()