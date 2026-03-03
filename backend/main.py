from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import re
from typing import Dict

app = FastAPI(title="EDI Parser API")

# Allow frontend to connect (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def detect_transaction_type(content: str) -> str:
    """
    Detect EDI transaction type by looking for ST*837, ST*835, or ST*834
    """
    # Look for ST segment with transaction type
    # Format: ST*837*... or ST*835*... or ST*834*...
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
    ISA*00*          *00*          *ZZ*SENDERID     *ZZ*RECEIVERID    *220101*1200*^*00501*000000001*0*T*:~
    """
    metadata = {
        "sender_id": "Unknown",
        "receiver_id": "Unknown",
        "interchange_date": "Unknown",
        "transaction_count": 0
    }
    
    # Find ISA segment (usually first line)
    lines = content.split('~')
    for line in lines:
        if line.startswith('ISA'):
            segments = line.split('*')
            if len(segments) > 8:
                # Sender ID is at position 6-7 (depending on implementation)
                # Common pattern: ISA*00*...*00*...*ZZ*SENDER*ZZ*RECEIVER*...
                metadata["sender_id"] = segments[6].strip()
                metadata["receiver_id"] = segments[8].strip()
                # Date is at position 9 (YYMMDD format)
                if len(segments) > 9:
                    metadata["interchange_date"] = segments[9].strip()
            break
    
    # Count transactions (ST segments)
    st_count = len(re.findall(r'ST\*', content))
    metadata["transaction_count"] = st_count
    
    return metadata

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload an EDI file, detect its type, and extract metadata
    """
    # Check file extension (basic validation)
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
        # Decode bytes to string (assuming UTF-8 or ASCII)
        content_str = content.decode('utf-8')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {str(e)}")
    
    # Detect transaction type
    tx_type = detect_transaction_type(content_str)
    
    # Extract metadata
    metadata = extract_metadata(content_str)
    
    # Return results
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)