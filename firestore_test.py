import firebase_admin
from firebase_admin import credentials, firestore

# Load and initialize the Firebase Admin SDK
cred = credentials.Certificate("serviceAccount.json")
firebase_admin.initialize_app(cred)

# ✅ Print the project ID
print(f"🔍 Firebase project ID being used: {firebase_admin.get_app().project_id}", flush=True)

# Attempt to write a test document
db = firestore.client()
db.collection("test_connection").document("hello").set({
    "status": "success",
    "message": "If you see this, Firestore is connected!"
})

print("✅ Test document written to Firestore.", flush=True)
# If this script runs without errors, Firestore is connected successfully.
