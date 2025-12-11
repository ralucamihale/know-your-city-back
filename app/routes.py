from flask import Blueprint, jsonify
from app.services.supabase_client import supabase # Import the client we just made

main = Blueprint('main', __name__)

@main.route('/api/cities', methods=['GET'])
def get_cities():
    try:
        # Query the 'cities' table in Supabase
        # .select("*") means "get all columns"
        response = supabase.table('cities').select("*").execute()
        
        # Access the data from the response object
        data = response.data
        
        return jsonify({
            "status": "success", 
            "data": data
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500