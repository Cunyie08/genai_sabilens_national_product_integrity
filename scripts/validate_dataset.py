# import os
# import csv

# DATASET_FOLDER = "reference_dataset"

# REQUIRED = {"front.jpg"}
# OPTIONAL = {"back.jpg", "left.jpg", "right.jpg", "top.jpg", "bottom.jpg"}

# def validate():
#     total_products = 0
#     valid_products = 0
#     report_data = []

#     for product in os.listdir(DATASET_FOLDER):
#         product_path = os.path.join(DATASET_FOLDER, product)

#         if not os.path.isdir(product_path):
#             continue

#         total_products += 1
#         files = set(os.listdir(product_path))

#         # Check for missing required views
#         missing_required = REQUIRED - files
#         missing_optional = OPTIONAL - files

#         product_info = {"product_name": product, "missing_required": missing_required, "missing_optional": missing_optional}

#         if missing_required:
#             report_data.append({**product_info, "status": "ERROR"})
#         else:
#             valid_products += 1
#             report_data.append({**product_info, "status": "OK"})

#     # Save validation results to CSV
#     with open("validation_report.csv", mode='w', newline='') as file:
#         writer = csv.DictWriter(file, fieldnames=["product_name", "missing_required", "missing_optional", "status"])
#         writer.writeheader()
#         writer.writerows(report_data)

#     print("\nCSV report generated: validation_report.csv")
#     print(f"Total products: {total_products}")
#     print(f"Valid products: {valid_products}")
#     print(f"Invalid products (missing front): {total_products - valid_products}")

# if __name__ == "__main__":
#     validate()

import os
import csv

DATASET_FOLDER = "reference_dataset"

REQUIRED = {"front.jpg"}
OPTIONAL = {"back.jpg", "left.jpg", "right.jpg", "top.jpg", "bottom.jpg"}

def validate():
    total_products = 0
    valid_products = 0
    total_optional_views = {view: 0 for view in OPTIONAL}
    report_data = []

    for product in os.listdir(DATASET_FOLDER):
        product_path = os.path.join(DATASET_FOLDER, product)

        if not os.path.isdir(product_path):
            continue

        total_products += 1
        files = set(os.listdir(product_path))

        # Check for missing required views
        missing_required = REQUIRED - files
        missing_optional = OPTIONAL - files

        product_info = {"product_name": product, "missing_required": missing_required, "missing_optional": missing_optional}

        if missing_required:
            report_data.append({**product_info, "status": "ERROR"})
        else:
            valid_products += 1
            report_data.append({**product_info, "status": "OK"})

            # Track missing optional views for percentage coverage
            for view in missing_optional:
                total_optional_views[view] += 1

    # Save validation results to CSV
    with open("validation_report.csv", mode='w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=["product_name", "missing_required", "missing_optional", "status"])
        writer.writeheader()
        writer.writerows(report_data)

    # Calculate and print percentage coverage stats
    print("\nCSV report generated: validation_report.csv")
    print(f"Total products: {total_products}")
    print(f"Valid products: {valid_products}")
    print(f"Invalid products (missing front): {total_products - valid_products}")

    print("\nPercentage Coverage Stats (Optional Views):")
    for view, count in total_optional_views.items():
        percentage = (count / total_products) * 100
        print(f"{view}: {percentage:.2f}%")

if __name__ == "__main__":
    validate()