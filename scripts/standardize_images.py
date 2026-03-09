# scripts/standardize_images.py

import os
import cv2

DATASET_FOLDER = "reference_dataset"
TARGET_SIZE = (512, 512)

def standardize():
    # Loop through all products in the reference dataset folder
    for product in os.listdir(DATASET_FOLDER):
        product_path = os.path.join(DATASET_FOLDER, product)

        # Skip if it's not a folder (in case it's a file or not a valid product directory)
        if not os.path.isdir(product_path):
            continue

        # Process all images in the product folder
        for img_file in os.listdir(product_path):
            img_path = os.path.join(product_path, img_file)

            # Read image using OpenCV
            img = cv2.imread(img_path)
            
            # Resize image to 512x512
            img = cv2.resize(img, TARGET_SIZE)
            
            # Convert to RGB color space if not already
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            # Save the image back after resizing
            cv2.imwrite(img_path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))

    print("All images standardized to 512x512.")

if __name__ == "__main__":
    standardize()