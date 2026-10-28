import io
from PIL import Image
import numpy as np

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def validate_image(file_bytes: bytes, filename: str) -> dict:
    if not filename or '.' not in filename:
        return {'valid': False, 'reason': 'Invalid filename'}
        
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        return {'valid': False, 'reason': f'Extension {ext} not allowed'}
        
    if len(file_bytes) > config.MAX_UPLOAD_SIZE_BYTES:
        return {'valid': False, 'reason': 'File too large'}
        
    if len(file_bytes) == 0:
        return {'valid': False, 'reason': 'Empty file'}
        
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()  # verify format
    except Exception as e:
        return {'valid': False, 'reason': 'Corrupt image or not an image format'}
        
    try:
        img = Image.open(io.BytesIO(file_bytes))
        if img.mode != 'RGB':
            img = img.convert('RGB')
    except Exception as e:
        return {'valid': False, 'reason': 'Cannot convert image to RGB'}
        
    width, height = img.size
    if width < 64 or height < 64:
        return {'valid': False, 'reason': 'Image dimensions too small (min 64x64)'}
        
    if width > 8000 or height > 8000:
        return {'valid': False, 'reason': 'Image dimensions too large (max 8000x8000)'}
        
    # Lightweight heuristic for non-leaf detection
    """
    Lightweight heuristic to detect solid colors.
    Not a true plant classifier!
    """
    try:
        small_img = img.resize((64, 64))
        arr = np.array(small_img)
        std_dev = np.std(arr)
        if std_dev < 5:
            return {'valid': False, 'reason': 'Image has extreme uniformity (likely a solid color)'}
    except Exception as e:
        pass
        
    return {'valid': True, 'reason': 'OK'}
