from flask import Flask
from flask_cors import CORS

def create_app():
    app = Flask(__name__)

    # Allow React (running on port 3000) to talk to this API
    # In production, change the origin to your actual domain.
    CORS(app, origins=["http://localhost:3000"])

    # Import the blueprint from routes.py and register it
    from .routes import main
    app.register_blueprint(main)

    return app