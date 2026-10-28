import os

CONFIDENCE_THRESHOLD = 0.45
MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp'}
MODEL_PATH = 'plant_disease_model_v5.h5'
CLASS_INDICES_PATH = 'class_indices_v5.json'
SUPPORTED_LANGUAGES = {'en': 'English', 'hi': 'हिन्दी', 'te': 'తెలుగు'}
DEFAULT_LANGUAGE = 'en'
DB_PATH = 'users.db'
UPLOAD_FOLDER = os.path.join('static', 'uploads')
SECRET_KEY = os.environ.get('SECRET_KEY', 'agritech-secret-2025')
NUM_CLASSES = 15
INPUT_SHAPE = (224, 224, 3)

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-flash-latest"

# Environmental input validation ranges
ENV_RANGES = {
    "temperature":   (0.0, 60.0),
    "humidity":      (0.0, 100.0),
    "soil_moisture": (0.0, 100.0),
    "leaf_wetness":  (0.0, 100.0),
}

