import json, os

ADVISORY_PATH = os.path.join(os.path.dirname(__file__), 'advisory.json')

_advisory_data = None

def _load():
    global _advisory_data
    if _advisory_data is None:
        with open(ADVISORY_PATH, 'r', encoding='utf-8') as f:
            _advisory_data = json.load(f)
    return _advisory_data

def get_advisory(disease_name: str, language: str = 'en') -> dict:
    """
    Returns advisory for a disease in the requested language.
    Falls back to English if translation not available.
    Returns dict with: crop, symptoms, cause, treatment, prevention, risk_factors, safety, language_used, fallback
    """
    data = _load()
    
    # Try exact match first
    entry = data.get(disease_name)
    
    if entry is None:
        # Try case-insensitive match
        for key in data:
            if key.lower() == disease_name.lower():
                entry = data[key]
                break
    
    if entry is None:
        return {
            'crop': 'Unknown',
            'symptoms': 'Advisory not available for this disease.',
            'cause': 'Information not available.',
            'treatment': 'Please consult your local agricultural extension officer.',
            'prevention': 'Practice general good agricultural practices.',
            'risk_factors': [],
            'safety': 'Always follow local agricultural guidance.',
            'language_used': 'en',
            'fallback': True,
            'not_found': True
        }
    
    lang_data = entry.get(language)
    fallback = False
    
    if lang_data is None:
        lang_data = entry.get('en', {})
        fallback = True
    
    return {
        **lang_data,
        'language_used': 'en' if fallback else language,
        'fallback': fallback
    }

def list_diseases() -> list:
    data = _load()
    return list(data.keys())

def get_supported_languages() -> list:
    return ['en', 'hi', 'te']
