import pyrebase
from firebase_admin import credentials, initialize_app

# Pyrebase Configuration
firebaseConfig = {
    "apiKey": "AIzaSyCw6LRis1ynw32B9SwpsMi6C2mArsp88bU",
    "authDomain": "mp3bank-25551.firebaseapp.com",
    "databaseURL": "https://mp3bank-25551-default-rtdb.firebaseio.com",
    "projectId": "mp3bank-25551",
    "storageBucket": "mp3bank-25551.firebasestorage.app",
    "messagingSenderId": "361940396433",
    "appId": "1:361940396433:web:d2c9b1ff6a759190bd5230", 
}

# Initialize Pyrebase
firebase = pyrebase.initialize_app(firebaseConfig)
db = firebase.database()
auth_instance = firebase.auth()
storage = firebase.storage()  # Initialize Firebase Storage

# Path to the Firebase Admin SDK service account key file
#service_account_path = 'C:/Users/PjBonbon/Desktop/ctu-ac-accreditedboardinghouse-datalink-main/ctuacaccreditedboardinghouse-firebase-adminsdk-f2r9o-1727478a48.json'

# Initialize Firebase Admin SDK
# cred = credentials.Certificate(service_account_path)
# initialize_app(cred, {
#     'databaseURL': 'https://ctuacaccreditedboardinghouse-default-rtdb.firebaseio.com'  # Admin SDK should have access to your Realtime Database
# })