from routes import router
from firebase_admin import credentials
from dotenv import load_dotenv
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, db
import os
from auth_routes import auth_router

app = FastAPI()
app.include_router(auth_router, prefix="/auth")

origins = [
    "http://localhost:3000",    # React app
    "http://localhost:8000",    # FastAPI backend
    "https://restaurant-allergy-manager.onrender.com"  # Render app
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)


load_dotenv()


def initialize_firebase():
    try:
        # Get Firebase credentials from environment variable
        cred_json = os.getenv('FIREBASE_CREDENTIALS')
        if not cred_json:
            raise ValueError("FIREBASE_CREDENTIALS not found in environment")

        # Parse the JSON string into a dictionary
        cred_dict = json.loads(cred_json)

        # Get database URL from environment
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL not found in environment")

        # Initialize Firebase
        firebase_admin.initialize_app(credentials.Certificate(cred_dict), {
            'databaseURL': database_url
        })
        print("Firebase initialized successfully")
    except Exception as e:
        print(f"Firebase initialization error: {e}")
        import traceback
        traceback.print_exc()


initialize_firebase()
# Import and include your router
app.include_router(router)


@app.get("/")
async def root():
    return {"message": "Restaurant Allergy Manager API"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
