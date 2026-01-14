from flask import Flask
from flask_cors import CORS
import os
from dotenv import load_dotenv
# Importăm db din fișierul neutru extensions
from .extensions import db

load_dotenv()

def create_app():
    app = Flask(__name__)
    
    # Configurare Bază de Date
    database_url = os.getenv('DATABASE_URL')
    
    # Fix pentru Supabase
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Inițializăm db-ul importat din extensions
    db.init_app(app)
    
    from .routes import main
    app.register_blueprint(main)
        
    return app