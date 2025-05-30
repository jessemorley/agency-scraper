import firebase_admin
from firebase_admin import credentials, firestore

# Confirm connection to database
print(f"🔍 Firebase project ID being used: {firebase_admin.get_app().project_id}", flush=True)

# Load service account
cred = credentials.Certificate("serviceAccount.json")
firebase_admin.initialize_app(cred)

# Connect to Firestore
db = firestore.client()

# Test write
doc_ref = db.collection("test_connection").document("hello")
doc_ref.set({
    "status": "success",
    "message": "If you see this, Firestore is connected!"
})

print("✅ Test document written to Firestore.")
