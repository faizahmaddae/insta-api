"""
Passenger WSGI entry point for cPanel hosting.
"""
import os
import sys

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Set environment variables (or load from .env file)
# You can also set these in cPanel's Environment Variables section
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("LOG_LEVEL", "INFO")

# Import the FastAPI app
from app.main import create_application

# Create the application instance
# Passenger expects an object named "application"
application = create_application()
