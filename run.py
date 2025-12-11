from app import create_app

# Create the application instance using the factory function
app = create_app()

if __name__ == '__main__':
    # Run the app. 
    # debug=True allows the server to auto-reload when you save code changes.
    app.run(debug=True, port=5000)