from dotenv import load_dotenv
import os

# Define the path to the secrets file
dotenv_path = ".devcontainer/secrets.env"

# Load environment variables from the secrets file
if load_dotenv(dotenv_path):
    print("Secrets loaded successfully from secrets.env.")
else:
    print(f"Failed to load secrets.env file from {dotenv_path}")

# Optionally print loaded variables for debugging (remove in production)
print("RAPIDAPI_KEY:", os.getenv("RAPIDAPI_KEY"))
print("RAPIDAPI_HOST:", os.getenv("RAPIDAPI_HOST"))
print("DB_CONNECTION_STRING:", os.getenv("DB_CONNECTION_STRING"))
