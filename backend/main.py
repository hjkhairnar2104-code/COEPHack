from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
import re
from typing import Dict
from bson import ObjectId  # for converting string id to ObjectId

from jose import JWTError
from auth import create_access_token, decode_token, verify_password, get_password_hash
from models import User, UserRole
from database import users_collection  # import the MongoDB collection

app = FastAPI(title="EDI Parser API")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Allow frontend to connect (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------- Helper Functions -------------------------

def detect_transaction_type(content: str) -> str:
    """
    Detect EDI transaction type by looking for ST*837, ST*835, or ST*834
    """
    st_match = re.search(r'ST\*(\d{3})', content)
    if st_match:
        tx_type = st_match.group(1)
        if tx_type == '837':
            return '837'
        elif tx_type == '835':
            return '835'
        elif tx_type == '834':
            return '834'
    return 'UNKNOWN'

def extract_metadata(content: str) -> Dict:
    """
    Extract basic envelope metadata from ISA segment
    """
    metadata = {
        "sender_id": "Unknown",
        "receiver_id": "Unknown",
        "interchange_date": "Unknown",
        "transaction_count": 0
    }
    
    lines = content.split('~')
    for line in lines:
        if line.startswith('ISA'):
            segments = line.split('*')
            if len(segments) > 8:
                metadata["sender_id"] = segments[6].strip()
                metadata["receiver_id"] = segments[8].strip()
                if len(segments) > 9:
                    metadata["interchange_date"] = segments[9].strip()
            break
    
    st_count = len(re.findall(r'ST\*', content))
    metadata["transaction_count"] = st_count
    return metadata

# ------------------------- Helper to convert MongoDB document to User model -------------------------
def user_helper(doc) -> User:
    return User(
        id=str(doc["_id"]),
        email=doc["email"],
        hashed_password=doc["hashed_password"],
        role=UserRole(doc["role"]),
        active=doc["active"]
    )

# ------------------------- Authentication Endpoints -------------------------

@app.post("/register")
async def register(email: str, password: str, role: UserRole = UserRole.BILLING_SPECIALIST):
    """
    Register a new user.
    - email: user's email address
    - password: user's password (will be hashed)
    - role: optional role (defaults to billing_specialist)
    """
    # Check if email already exists
    existing = await users_collection.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash the password
    hashed = get_password_hash(password)
    
    # Create new user document
    user_doc = {
        "email": email,
        "hashed_password": hashed,
        "role": role.value,
        "active": True
    }
    result = await users_collection.insert_one(user_doc)
    
    return {"message": "User registered successfully", "user_id": str(result.inserted_id)}

@app.post("/token", response_model=dict)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 compatible token login. Expects form data with username and password.
    Returns JWT access token.
    """
    # Find user by email
    user_doc = await users_collection.find_one({"email": form_data.username})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = user_helper(user_doc)
    
    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify password
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role.value}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Dependency to get the current authenticated user from JWT token.
    """
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Find user by email
    user_doc = await users_collection.find_one({"email": email})
    if not user_doc or not user_doc.get("active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_helper(user_doc)

def require_roles(allowed_roles: list[UserRole]):
    """
    Dependency to check if the current user has one of the allowed roles.
    Usage: Depends(require_roles([UserRole.ADMIN, UserRole.BILLING_SPECIALIST]))
    """
    async def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action"
            )
        return current_user
    return role_checker

# ------------------------- Existing Endpoints (Protected) -------------------------

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Upload an EDI file, detect its type, and extract metadata.
    Requires authentication. Role determines allowed file types.
    """
    # File extension validation
    allowed_extensions = ['.edi', '.txt', '.dat', '.x12']
    file_ext = ''.join(['.' + file.filename.split('.')[-1]]).lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Read file content
    try:
        content = await file.read()
        content_str = content.decode('utf-8')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {str(e)}")
    
    # Detect transaction type
    tx_type = detect_transaction_type(content_str)
    
    # Role-based file type restrictions
    if current_user.role == UserRole.BILLING_SPECIALIST and tx_type != "837":
        raise HTTPException(
            status_code=403,
            detail="Billing Specialists can only upload 837 files"
        )
    if current_user.role == UserRole.BENEFITS_ADMIN and tx_type != "834":
        raise HTTPException(
            status_code=403,
            detail="Benefits Admins can only upload 834 files"
        )
    # Admin can upload any type, including 835
    
    # Extract metadata
    metadata = extract_metadata(content_str)
    
    return {
        "filename": file.filename,
        "file_type": tx_type,
        "metadata": metadata,
        "file_size": len(content),
        "message": f"Successfully uploaded {tx_type} file"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "EDI Parser API is running"}

# ------------------------- Admin Endpoints (Optional) -------------------------
@app.get("/admin/users", dependencies=[Depends(require_roles([UserRole.ADMIN]))])
async def list_users():
    cursor = users_collection.find()
    users = await cursor.to_list(length=100)
    # Exclude hashed_password from response
    return [user_helper(u).dict(exclude={"hashed_password"}) for u in users]

@app.delete("/admin/users/{user_id}", dependencies=[Depends(require_roles([UserRole.ADMIN]))])
async def deactivate_user(user_id: str):
    result = await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"active": False}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deactivated"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)