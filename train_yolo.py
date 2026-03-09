# from ultralytics import YOLO  # Import YOLO class from ultralytics

# # Load pre-trained YOLOv8 model
# model = YOLO("yolov8n.pt")

# # Train the model using your custom dataset YAML file
# model.train(data="custom_data.yaml", epochs=100, batch=16)  # Adjust batch_size and epochs as necessary


from ultralytics import YOLO

model = YOLO("yolov8n.pt")

model.train(
    data="custom_data.yaml",
    epochs=180,
    batch=16,
    imgsz=640,

    # augmentation
    hsv_h=0.015,
    hsv_s=0.7,
    hsv_v=0.4,
    degrees=8.0,
    translate=0.08,
    scale=0.25,
    shear=2.0,
    perspective=0.0005,
    flipud=0.0,
    fliplr=0.5,
    mosaic=0.2,
    mixup=0.0,

    # training behavior
    patience=30,
    close_mosaic=10,
    workers=0
)