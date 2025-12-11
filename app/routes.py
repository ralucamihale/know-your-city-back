from flask import Blueprint, jsonify

# Define a Blueprint named 'main'.
# This helps organize routes if you add more files later (e.g., 'auth', 'users').
main = Blueprint('main', __name__)

@main.route('/api/data', methods=['GET'])
def get_data():
    """
    Route: GET /api/data
    Description: Returns a simple JSON handshake.
    """
    return jsonify({
        "message": "OK",
        "status": "success",
        "payload": "Hello from the separate Backend Repo!"
    })

@main.route('/api/health', methods=['GET'])
def health_check():
    """
    Route: GET /api/health
    Description: A standard route for uptime monitors to check if server is alive.
    """
    return jsonify({"status": "healthy"})