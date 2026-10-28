import os
import json
import io
import numpy as np
from PIL import Image

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

try:
    from tensorflow.keras.applications import MobileNetV2
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import GlobalAveragePooling2D, Dense, Dropout
except ImportError:
    pass

MODEL_LOADED = False
keras_model = None
CLASS_NAMES = []

def load_class_names():
    global CLASS_NAMES
    try:
        if os.path.exists(config.CLASS_INDICES_PATH):
            with open(config.CLASS_INDICES_PATH, 'r') as f:
                class_indices = json.load(f)
            inv = {int(v): k for k, v in class_indices.items()}
            CLASS_NAMES = [inv[i] for i in range(len(inv))]
        else:
            CLASS_NAMES = [f"Class_{i}" for i in range(config.NUM_CLASSES)]
    except Exception as e:
        CLASS_NAMES = [f"Class_{i}" for i in range(config.NUM_CLASSES)]

def load_model():
    global keras_model, MODEL_LOADED
    try:
        base_model = MobileNetV2(input_shape=config.INPUT_SHAPE, include_top=False, weights='imagenet')
        base_model.trainable = False
        keras_model = Sequential([
            base_model,
            GlobalAveragePooling2D(),
            Dense(512, activation='relu'),
            Dropout(0.2),
            Dense(config.NUM_CLASSES, activation='softmax')
        ])
        
        if os.path.exists(config.MODEL_PATH):
            keras_model.load_weights(config.MODEL_PATH)
            keras_model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
            MODEL_LOADED = True
        else:
            MODEL_LOADED = False
            
        load_class_names()
    except Exception as e:
        MODEL_LOADED = False

load_model()

def format_disease_name(name: str) -> str:
    # converts 'Tomato__Early_blight' -> 'Tomato Early Blight'
    name = name.replace('___', ' ')
    name = name.replace('__', ' ')
    name = name.replace('_', ' ')
    return name.strip()

def predict(image_bytes: bytes) -> dict:
    if not MODEL_LOADED or keras_model is None:
        return {'error': 'Model not loaded'}
        
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img = img.resize((config.INPUT_SHAPE[0], config.INPUT_SHAPE[1]))
        
        arr = np.array(img, dtype=np.float32)
        arr = (arr / 127.5) - 1.0
        arr = np.expand_dims(arr, axis=0)
        
        preds = keras_model.predict(arr)
        class_idx = int(np.argmax(preds[0]))
        confidence = float(preds[0][class_idx])
        
        disease_raw = CLASS_NAMES[class_idx] if class_idx < len(CLASS_NAMES) else f"Unknown_Class_{class_idx}"
        disease = format_disease_name(disease_raw)
        
        return {
            'disease_raw': disease_raw,
            'disease': disease,
            'confidence': confidence,
            'class_idx': class_idx,
            'low_confidence': confidence < config.CONFIDENCE_THRESHOLD
        }
    except Exception as e:
        return {'error': str(e)}
