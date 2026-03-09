from ultralytics import YOLO

# Load your trained model
model = YOLO('runs/detect/train/weights/best.pt')  # Replace with your model path

# Run inference on the test dataset
results = model('images (1).jpeg')  # Replace with the path to your test images

# View results
results.show()  # Show images with predictions and bounding boxes