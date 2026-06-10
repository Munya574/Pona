# CV model for food image recognition
# Architecture: YOLOv8 or EfficientNet (PyTorch)
# Training data: Food-101 (101k images) + Allergen30 (6k images)


def predict_ingredients(image_bytes: bytes) -> list[str]:
    """Return a list of identified ingredients from a food photo."""
    raise NotImplementedError
