import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        conn = get_connection()
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                disease TEXT NOT NULL,
                crop TEXT DEFAULT NULL,
                confidence REAL DEFAULT NULL,
                file_path TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                temperature REAL DEFAULT NULL,
                humidity REAL DEFAULT NULL,
                soil_moisture REAL DEFAULT NULL,
                leaf_wetness REAL DEFAULT NULL,
                risk_level TEXT DEFAULT NULL,
                mode TEXT DEFAULT 'offline',
                language TEXT DEFAULT 'en'
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                name TEXT NOT NULL,
                message TEXT NOT NULL,
                rating INTEGER,
                timestamp TEXT
            )
        ''')
        
        conn.commit()
    except Exception as e:
        print(f"Error initializing db: {e}")
    finally:
        if 'conn' in locals():
            conn.close()
            
def migrate_history_table():
    try:
        conn = get_connection()
        c = conn.cursor()
        
        c.execute("PRAGMA table_info(history)")
        columns = [row['name'] for row in c.fetchall()]
        
        missing_columns = {
            'confidence': 'REAL DEFAULT NULL',
            'crop': 'TEXT DEFAULT NULL',
            'risk_level': 'TEXT DEFAULT NULL',
            'temperature': 'REAL DEFAULT NULL',
            'humidity': 'REAL DEFAULT NULL',
            'soil_moisture': 'REAL DEFAULT NULL',
            'leaf_wetness': 'REAL DEFAULT NULL',
            'mode': "TEXT DEFAULT 'offline'",
            'language': "TEXT DEFAULT 'en'"
        }
        
        for col, col_type in missing_columns.items():
            if col not in columns:
                c.execute(f"ALTER TABLE history ADD COLUMN {col} {col_type}")
                
        conn.commit()
    except Exception as e:
        print(f"Error migrating history table: {e}")
    finally:
        if 'conn' in locals():
            conn.close()
            
def migrate_feedback_table():
    try:
        conn = get_connection()
        c = conn.cursor()
        
        c.execute("PRAGMA table_info(feedback)")
        columns = [row['name'] for row in c.fetchall()]
        
        if 'rating' not in columns:
            c.execute("ALTER TABLE feedback ADD COLUMN rating INTEGER")
        if 'timestamp' not in columns:
            c.execute("ALTER TABLE feedback ADD COLUMN timestamp TEXT")
            
        conn.commit()
    except Exception as e:
        print(f"Error migrating feedback table: {e}")
    finally:
        if 'conn' in locals():
            conn.close()
            
def hash_password(plain: str) -> str:
    return generate_password_hash(plain)
    
def check_password(plain: str, hashed: str) -> bool:
    try:
        return check_password_hash(hashed, plain)
    except ValueError:
        # Handle legacy plaintext passwords
        if plain == hashed:
            # Need a way to re-hash, but returning True here is the request
            # Ideally the caller will re-hash and update DB
            return True
        return False
        
def save_history(user_email, disease, crop, confidence, file_path, timestamp, temperature=None, humidity=None, soil_moisture=None, leaf_wetness=None, risk_level=None, mode='offline', language='en'):
    try:
        conn = get_connection()
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO history (
                user_email, disease, crop, confidence, file_path, timestamp,
                temperature, humidity, soil_moisture, leaf_wetness, risk_level, mode, language
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_email, disease, crop, confidence, file_path, timestamp,
            temperature, humidity, soil_moisture, leaf_wetness, risk_level, mode, language
        ))
        conn.commit()
    except Exception as e:
        print(f"Error saving history: {e}")
    finally:
        if 'conn' in locals():
            conn.close()
