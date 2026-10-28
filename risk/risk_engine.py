DISEASE_RULES = {
    'Pepper__bell___Bacterial_spot': {'type': 'bacterial', 'humidity_sensitive': True, 'leaf_wetness_sensitive': True, 'temp_range': [20, 35], 'base_risk': 'MEDIUM'},
    'Pepper__bell___healthy': {'type': 'healthy', 'humidity_sensitive': False, 'leaf_wetness_sensitive': False, 'temp_range': [15, 30], 'base_risk': 'LOW'},
    'Potato___Early_blight': {'type': 'fungal', 'humidity_sensitive': True, 'leaf_wetness_sensitive': True, 'temp_range': [15, 30], 'base_risk': 'MEDIUM'},
    'Potato___Late_blight': {'type': 'oomycete', 'humidity_sensitive': True, 'leaf_wetness_sensitive': True, 'temp_range': [10, 25], 'base_risk': 'HIGH'},
    'Potato___healthy': {'type': 'healthy', 'humidity_sensitive': False, 'leaf_wetness_sensitive': False, 'temp_range': [15, 25], 'base_risk': 'LOW'},
    'Tomato_Bacterial_spot': {'type': 'bacterial', 'humidity_sensitive': True, 'leaf_wetness_sensitive': True, 'temp_range': [20, 35], 'base_risk': 'MEDIUM'},
    'Tomato_Early_blight': {'type': 'fungal', 'humidity_sensitive': True, 'leaf_wetness_sensitive': True, 'temp_range': [15, 30], 'base_risk': 'MEDIUM'},
    'Tomato_Late_blight': {'type': 'oomycete', 'humidity_sensitive': True, 'leaf_wetness_sensitive': True, 'temp_range': [10, 25], 'base_risk': 'HIGH'},
    'Tomato_Leaf_Mold': {'type': 'fungal', 'humidity_sensitive': True, 'leaf_wetness_sensitive': False, 'temp_range': [15, 25], 'base_risk': 'MEDIUM'},
    'Tomato_Septoria_leaf_spot': {'type': 'fungal', 'humidity_sensitive': True, 'leaf_wetness_sensitive': True, 'temp_range': [15, 30], 'base_risk': 'MEDIUM'},
    'Tomato_Spider_mites_Two_spotted_spider_mite': {'type': 'insect', 'humidity_sensitive': False, 'leaf_wetness_sensitive': False, 'temp_range': [20, 40], 'base_risk': 'MEDIUM'},
    'Tomato__Target_Spot': {'type': 'fungal', 'humidity_sensitive': True, 'leaf_wetness_sensitive': True, 'temp_range': [20, 35], 'base_risk': 'MEDIUM'},
    'Tomato__Tomato_YellowLeaf__Curl_Virus': {'type': 'viral', 'humidity_sensitive': False, 'leaf_wetness_sensitive': False, 'temp_range': [20, 40], 'base_risk': 'MEDIUM'},
    'Tomato__Tomato_mosaic_virus': {'type': 'viral', 'humidity_sensitive': False, 'leaf_wetness_sensitive': False, 'temp_range': [15, 35], 'base_risk': 'MEDIUM'},
    'Tomato_healthy': {'type': 'healthy', 'humidity_sensitive': False, 'leaf_wetness_sensitive': False, 'temp_range': [15, 35], 'base_risk': 'LOW'}
}

def calculate_risk(disease_name: str, env: dict) -> dict:
    if not env or all(v is None for v in env.values()):
        return {'level': 'GENERAL', 'score': 0, 'reasons': ['No environment data provided'], 'env_provided': False}
        
    # Validate ranges
    t = env.get('temperature')
    h = env.get('humidity')
    s = env.get('soil_moisture')
    l = env.get('leaf_wetness')
    
    reasons = []
    
    if t is not None and not (0 <= t <= 60):
        t = None
    if h is not None and not (0 <= h <= 100):
        h = None
    if s is not None and not (0 <= s <= 100):
        s = None
    if l is not None and not (0 <= l <= 100):
        l = None
        
    rule = DISEASE_RULES.get(disease_name, None)
    if not rule or rule['type'] == 'healthy':
        return {'level': 'LOW', 'score': 0, 'reasons': ['Crop is healthy or disease unknown'], 'env_provided': True}
        
    score = 0
    if rule['base_risk'] == 'LOW':
        score += 20
    elif rule['base_risk'] == 'MEDIUM':
        score += 50
    elif rule['base_risk'] == 'HIGH':
        score += 70
        
    reasons.append(f"Base risk for {rule['type']} is {rule['base_risk']}")
    
    if rule['type'] == 'fungal':
        if h is not None and h > 80:
            score += 20
            reasons.append("High humidity favors fungal growth")
        if l is not None and l > 70:
            score += 20
            reasons.append("High leaf wetness favors fungal growth")
        if t is not None and 15 <= t <= 25:
            score += 10
            reasons.append("Optimal temperature for fungal growth")
            
    elif rule['type'] == 'oomycete':
        if h is not None and h > 85:
            score += 30
            reasons.append("Very high humidity favors oomycetes (Late Blight)")
        if t is not None and 10 <= t <= 20:
            score += 20
            reasons.append("Cool temperatures favor oomycetes")
        if l is not None and l > 80:
            score += 20
            reasons.append("High leaf wetness favors oomycetes")
            
    elif rule['type'] == 'bacterial':
        if h is not None and h > 75:
            score += 15
            reasons.append("High humidity favors bacterial growth")
        if t is not None and t > 30:
            score += 15
            reasons.append("Warm temperatures favor bacterial growth")
        if l is not None and l > 60:
            score += 10
            reasons.append("Leaf wetness favors bacterial spread")
            
    elif rule['type'] in ['viral', 'insect']:
        if t is not None and t > 30:
            score += 15
            reasons.append("Warm temperatures increase vector activity")
            
    score = min(score, 100)
    
    if score < 40:
        level = 'LOW'
    elif score < 70:
        level = 'MEDIUM'
    else:
        level = 'HIGH'
        
    return {
        'level': level,
        'score': score,
        'reasons': reasons,
        'env_provided': True
    }
