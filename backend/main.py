from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
import re
from typing import Dict, List, Any
from bson import ObjectId
import uuid
import io
import json
from chat_agent import get_agent
from jose import JWTError
from auth import create_access_token, decode_token, verify_password, get_password_hash
from models import User, UserRole
from database import users_collection
from validation import validate
from fastapi.responses import StreamingResponse
from chat_agent import get_agent

app = FastAPI(title="EDI Parser API")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# In-memory storage
file_storage = {}
parsed_files = {}
file_types = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


import os
from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set")
# ------------------------- Helper Functions -------------------------

def detect_transaction_type(content: str) -> str:
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

def user_helper(doc) -> User:
    return User(
        id=str(doc["_id"]),
        email=doc["email"],
        hashed_password=doc["hashed_password"],
        role=UserRole(doc["role"]),
        active=doc["active"]
    )

# ------------------------- Authentication Dependencies -------------------------

async def get_current_user(token: str = Depends(oauth2_scheme)):
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
    
    user_doc = await users_collection.find_one({"email": email})
    if not user_doc or not user_doc.get("active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_helper(user_doc)

def require_roles(allowed_roles: list[UserRole]):
    async def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action"
            )
        return current_user
    return role_checker

# ------------------------- Authentication Endpoints -------------------------

@app.post("/register")
async def register(email: str, password: str, role: UserRole = UserRole.BILLING_SPECIALIST):
    existing = await users_collection.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = get_password_hash(password)
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
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role.value}
    )
    return {"access_token": access_token, "token_type": "bearer"}

# ------------------------- Parse Endpoint -------------------------
@app.post("/parse/{file_id}")
async def parse_edi_file(file_id: str, current_user: User = Depends(get_current_user)):
    content_str = file_storage.get(file_id)
    if not content_str:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        segments = content_str.split('~')
        result = []
        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue
            elements = seg.split('*')
            segment_id = elements[0] if elements else ''
            result.append({
                "id": segment_id,
                "elements": elements
            })
        parsed_files[file_id] = result
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parsing failed: {str(e)}")

# ------------------------- Validation Endpoint -------------------------
@app.post("/validate/{file_id}")
async def validate_edi_file(file_id: str, current_user: User = Depends(get_current_user)):
    parsed = parsed_files.get(file_id)
    if not parsed:
        raise HTTPException(status_code=404, detail="Parsed data not found.")
    file_type = file_types.get(file_id)
    if not file_type:
        raise HTTPException(status_code=404, detail="File type not found.")
    try:
        errors = validate(parsed, file_type)
        return errors
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

# ------------------------- Summary Endpoints (Phase 5) -------------------------

def generate_835_summary(parsed_data: List[Dict]) -> List[Dict]:
    """
    Extract payment details from 835 file, including adjustments from CAS segments.
    Returns a list of dicts with:
      - claim_id
      - billed
      - paid
      - patient_responsibility
      - adjustments (list of strings like "CO45:30")
      - status_code
    """
    summary = []
    current_claim = None
    i = 0
    while i < len(parsed_data):
        seg = parsed_data[i]
        seg_id = seg.get('id')
        elements = seg.get('elements', [])

        if seg_id == 'CLP':
            # Save previous claim if any
            if current_claim:
                summary.append(current_claim)
            # Start new claim
            current_claim = {
                "claim_id": elements[1] if len(elements) > 1 else "",
                "billed": elements[2] if len(elements) > 2 else "",
                "paid": elements[3] if len(elements) > 3 else "",
                "patient_responsibility": elements[4] if len(elements) > 4 else "",
                "status_code": elements[1] if len(elements) > 1 else "",
                "adjustments": []
            }

        elif seg_id == 'CAS' and current_claim:
            # CAS: elements[1] = group code (CO, PR, OA, PI)
            # elements[2] = reason code (e.g., 45)
            # elements[3] = amount
            group = elements[1] if len(elements) > 1 else ""
            reason = elements[2] if len(elements) > 2 else ""
            amount = elements[3] if len(elements) > 3 else ""
            if group and reason and amount:
                adj_str = f"{group}{reason}: {amount}"
                current_claim["adjustments"].append(adj_str)

        i += 1

    # Append last claim
    if current_claim:
        summary.append(current_claim)

    return summary

def generate_834_summary(parsed_data: List[Dict]) -> List[Dict]:
    """
    Extract member information from 834 file.
    Returns list of dicts with:
      - member_name (str)
      - action (str) – from INS03 (maintenance type code)
      - effective_date (str) – from DTP with qualifier 356/348
      - relationship (str) – from INS02
    """
    summary = []
    i = 0
    while i < len(parsed_data):
        seg = parsed_data[i]
        if seg.get('id') == 'INS':
            elements = seg.get('elements', [])
            # INS segment indices (0‑based):
            # 0: "INS"
            # 1: INS01 – transaction handling code (not used here)
            # 2: INS02 – relationship code (18=Self, 19=Spouse, etc.)
            # 3: INS03 – maintenance type code (021=Add, 024=Terminate, 030=Change)
            rel_code = elements[2] if len(elements) > 2 else ""
            maint_code = elements[3] if len(elements) > 3 else ""

            # Relationship mapping (INS02)
            rel_map = {
                "18": "Self",
                "19": "Spouse",
                "20": "Child",
                "21": "Other",
                "01": "Spouse",
                "02": "Child",
            }
            relationship = rel_map.get(rel_code, rel_code)

            # Maintenance type mapping (INS03)
            action_map = {
            "001": "Add",
            "021": "Add",
            "024": "Terminate",
            "025": "Change",
            "026": "Change",
            "030": "Change",
        }
            action = action_map.get(maint_code, maint_code)

            # Find associated NM1 segment (member name)
            member_name = ""
            j = i + 1
            while j < len(parsed_data) and parsed_data[j].get('id') != 'INS':
                if parsed_data[j].get('id') == 'NM1':
                    nm1 = parsed_data[j].get('elements', [])
                    # NM1 indices: 3=last, 4=first
                    last = nm1[3] if len(nm1) > 3 else ""
                    first = nm1[4] if len(nm1) > 4 else ""
                    member_name = f"{first} {last}".strip()
                    break
                j += 1

            # Find effective date (DTP with qualifier 356 or 348)
            effective_date = ""
            j = i + 1
            while j < len(parsed_data) and parsed_data[j].get('id') != 'INS':
                if parsed_data[j].get('id') == 'DTP':
                    dtp = parsed_data[j].get('elements', [])
                    # DTP indices: 1=date qualifier, 3=date value
                    if len(dtp) > 3 and dtp[1] in ('356', '348'):
                        effective_date = dtp[3]
                        break
                j += 1

            summary.append({
                "member_name": member_name,
                "action": action,
                "effective_date": effective_date,
                "relationship": relationship,
            })
        i += 1
    return summary

@app.post("/summary/{file_id}")
async def get_summary(file_id: str, current_user: User = Depends(get_current_user)):
    """
    Return a summary for 835 or 834 files.
    """
    parsed = parsed_files.get(file_id)
    if not parsed:
        raise HTTPException(status_code=404, detail="Parsed data not found")
    file_type = file_types.get(file_id)
    if not file_type:
        raise HTTPException(status_code=404, detail="File type not found")

    if file_type == "835":
        summary = generate_835_summary(parsed)
    elif file_type == "834":
        summary = generate_834_summary(parsed)
    else:
        raise HTTPException(status_code=400, detail="Summary not available for this file type")

    return summary

# ------------------------- Upload Endpoint -------------------------
@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    allowed_extensions = ['.edi', '.txt', '.dat', '.x12']
    file_ext = ''.join(['.' + file.filename.split('.')[-1]]).lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )
    try:
        content = await file.read()
        content_str = content.decode('utf-8')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {str(e)}")
    
    tx_type = detect_transaction_type(content_str)
    
    if current_user.role == UserRole.BILLING_SPECIALIST and tx_type != "837":
        raise HTTPException(status_code=403, detail="Billing Specialists can only upload 837 files")
    if current_user.role == UserRole.BENEFITS_ADMIN and tx_type != "834":
        raise HTTPException(status_code=403, detail="Benefits Admins can only upload 834 files")
    
    metadata = extract_metadata(content_str)
    file_id = str(uuid.uuid4())
    file_storage[file_id] = content_str
    file_types[file_id] = tx_type
    
    return {
        "file_id": file_id,
        "filename": file.filename,
        "file_type": tx_type,
        "metadata": metadata,
        "file_size": len(content),
        "message": f"Successfully uploaded {tx_type} file"
    }

# ------------------------- Health Check -------------------------
@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "EDI Parser API is running"}

# ------------------------- Admin Endpoints -------------------------
@app.get("/admin/users", dependencies=[Depends(require_roles([UserRole.ADMIN]))])
async def list_users():
    cursor = users_collection.find()
    users = await cursor.to_list(length=100)
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





@app.post("/chat/{file_id}")
async def chat_with_file(
    file_id: str,
    query: str,
    current_user: User = Depends(get_current_user)
):
    """
    Ask a question about the uploaded EDI file.
    Returns a streaming response with AI-generated answer.
    """
    parsed = parsed_files.get(file_id)
    if not parsed:
        raise HTTPException(status_code=404, detail="Parsed data not found")
    
    file_type = file_types.get(file_id)
    if not file_type:
        raise HTTPException(status_code=404, detail="File type not found")
    
    agent = get_agent()
    
    async def event_generator():
        # Send a marker to indicate start (optional)
        yield "data: start\n\n"
        
        async for token in agent.stream_response(query, parsed, file_type):
            # Format as SSE (Server-Sent Event)
            yield f"data: {token}\n\n"
        
        # Send end marker
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    ) 
@app.get("/file-info/{file_id}")
async def get_file_info(file_id: str, current_user: User = Depends(get_current_user)):
    """Return basic info about an uploaded file."""
    file_type = file_types.get(file_id)
    if not file_type:
        raise HTTPException(status_code=404, detail="File not found")
    return {"file_id": file_id, "file_type": file_type}    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)