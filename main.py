from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from bson import ObjectId
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, quote
import io
import os
import json

MONGODB_URI = "mongodb+srv://Rafa-612:eQ8IOESaO4lyLnm2@rafa-612.qiobhis.mongodb.net/?appName=Rafa-612"  # your URI
DB_NAME = "emogo_db"  # your DB name
BASE_URL = os.getenv("BASE_URL", "https://emogo-backend-rafa-612.onrender.com")
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB

# Create upload directory
UPLOAD_DIR = Path("uploads/videos")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI()

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request validation
class Sentiment(BaseModel):
    user_id: str
    emotion_score: int  # 0-10
    timestamp: Optional[str] = None
    weather: Optional[str] = None
    location: Optional[dict] = None

class Vlog(BaseModel):
    user_id: str
    video_url: Optional[str] = None  # For backward compatibility
    video_id: Optional[str] = None  # GridFS file ID
    duration: Optional[float] = None
    timestamp: Optional[str] = None
    location: Optional[dict] = None

class VlogMetadata(BaseModel):
    user_id: str
    duration: Optional[float] = None
    location: Optional[dict] = None

class GPS(BaseModel):
    user_id: str
    latitude: float
    longitude: float
    timestamp: Optional[str] = None

@app.on_event("startup")
async def startup_db_client():
    app.mongodb_client = AsyncIOMotorClient(MONGODB_URI)
    app.mongodb = app.mongodb_client[DB_NAME]
    app.fs = AsyncIOMotorGridFSBucket(app.mongodb)
    print(f"✅ MongoDB connected to {DB_NAME}")
    print(f"✅ Upload directory: {UPLOAD_DIR.absolute()}")
    print(f"✅ Upload directory exists: {UPLOAD_DIR.exists()}")

@app.on_event("shutdown")
async def shutdown_db_client():
    app.mongodb_client.close()

def convert_objectid(item):
    """Recursively convert ObjectId to string in a document"""
    if isinstance(item, dict):
        return {key: convert_objectid(value) for key, value in item.items()}
    elif isinstance(item, list):
        return [convert_objectid(element) for element in item]
    elif isinstance(item, ObjectId):
        return str(item)
    else:
        return item

@app.get("/items")
async def get_items():
    try:
        items = await app.mongodb["items"].find().to_list(100)
        # Convert all ObjectIds to strings recursively
        items = [convert_objectid(item) for item in items]
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# POST endpoints for storing data
@app.post("/sentiments")
async def create_sentiment(sentiment: Sentiment):
    try:
        sentiment_data = sentiment.dict()
        if not sentiment_data.get("timestamp"):
            sentiment_data["timestamp"] = datetime.utcnow().isoformat()
        
        result = await app.mongodb["sentiments"].insert_one(sentiment_data)
        sentiment_data["_id"] = str(result.inserted_id)
        return {"status": "success", "data": sentiment_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/vlogs")
async def create_vlog(vlog: Vlog):
    try:
        vlog_data = vlog.dict()
        if not vlog_data.get("timestamp"):
            vlog_data["timestamp"] = datetime.utcnow().isoformat()
        
        result = await app.mongodb["vlogs"].insert_one(vlog_data)
        vlog_data["_id"] = str(result.inserted_id)
        return {"status": "success", "data": vlog_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-video")
async def upload_video(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    metadata: Optional[str] = Form(None)
):
    """
    Upload video file to MongoDB GridFS (permanent storage)
    Returns video_id and URL for accessing the video
    """
    try:
        print(f"📤 Receiving video upload request")
        print(f"📦 File: {file.filename}, Content-Type: {file.content_type}")
        print(f"👤 User ID: {user_id}")
        
        # Read file content
        content = await file.read()
        file_size = len(content)
        print(f"📊 File size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")
        
        # Check file size
        if file_size > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail=f"File too large. Max size is {MAX_UPLOAD_SIZE / 1024 / 1024}MB")
        
        # Validate file type (relaxed for mobile uploads)
        if file.content_type and not (file.content_type.startswith('video/') or file.content_type == 'application/octet-stream'):
            print(f"⚠️ Warning: Unexpected content type {file.content_type}, but proceeding...")
        
        # Parse metadata
        metadata_dict = {}
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
                print(f"📋 Metadata: {metadata_dict}")
            except Exception as e:
                print(f"⚠️ Failed to parse metadata: {e}")
        
        # Clean user_id for filename
        safe_user_id = user_id.replace(" ", "_").replace("/", "_").replace("\\", "_")
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{safe_user_id}_{timestamp}.mp4"
        
        # Upload to MongoDB GridFS (永久儲存！)
        print(f"💾 Uploading to MongoDB GridFS...")
        file_id = await app.fs.upload_from_stream(
            filename,
            content,
            metadata={
                "content_type": file.content_type or "video/mp4",
                "user_id": user_id,
                "upload_time": datetime.utcnow().isoformat(),
                "size": file_size,
                **metadata_dict
            }
        )
        
        print(f"✅ Video uploaded to MongoDB GridFS")
        print(f"🆔 File ID: {file_id}")
        print(f"💾 Permanently stored in database!")
        
        # Generate accessible URL
        video_url = f"{BASE_URL}/stream-video/{str(file_id)}"
        
        return {
            "status": "success",
            "file_url": video_url,  # 為了向後兼容
            "video_id": str(file_id),
            "filename": filename,
            "user_id": user_id,
            "size": file_size,
            "uploaded_at": datetime.utcnow().isoformat(),
            "storage": "mongodb_gridfs",
            "permanent": True,
            "metadata": metadata_dict
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/videos/{filename:path}")
async def get_video(filename: str):
    """
    Stream video file for playback in browser
    Supports URL-encoded filenames (e.g., spaces become %20)
    """
    try:
        # Decode URL-encoded filename
        decoded_filename = unquote(filename)
        print(f"📺 Streaming video request")
        print(f"📝 Original: {filename}")
        print(f"📝 Decoded: {decoded_filename}")
        
        # Security: prevent directory traversal
        if ".." in decoded_filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        file_path = UPLOAD_DIR / decoded_filename
        print(f"📁 File path: {file_path}")
        print(f"✅ File exists: {file_path.exists()}")
        
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            # List available files for debugging
            available_files = list(UPLOAD_DIR.glob("*.mp4"))
            print(f"📂 Available files ({len(available_files)}):")
            for f in available_files:
                print(f"   - {f.name}")
            raise HTTPException(status_code=404, detail=f"Video not found: {decoded_filename}")
        
        file_size = file_path.stat().st_size
        print(f"📊 File size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")
        print(f"✅ Serving video file")
        
        return FileResponse(
            path=str(file_path),
            media_type="video/mp4",
            filename=decoded_filename,
            headers={
                "Content-Disposition": f'inline; filename="{decoded_filename}"',
                "Accept-Ranges": "bytes",
                "Cache-Control": "public, max-age=3600"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error streaming video: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/videos/{filename:path}/download")
async def download_video_file(filename: str):
    """
    Force download video file
    Supports URL-encoded filenames
    """
    try:
        # Decode URL-encoded filename
        decoded_filename = unquote(filename)
        print(f"📥 Download request: {decoded_filename}")
        
        # Security: prevent directory traversal
        if ".." in decoded_filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        file_path = UPLOAD_DIR / decoded_filename
        print(f"� File path: {file_path}")
        
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            raise HTTPException(status_code=404, detail="Video not found")
        
        print(f"✅ Serving download")
        
        return FileResponse(
            path=str(file_path),
            media_type="video/mp4",
            filename=decoded_filename,
            headers={
                "Content-Disposition": f'attachment; filename="{decoded_filename}"'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error downloading video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download-video-file/{filename}")
async def download_video_file_endpoint(filename: str):
    """
    Force download video file
    """
    try:
        # Decode URL-encoded filename
        decoded_filename = unquote(filename)
        print(f"📥 Download request: {decoded_filename}")
        
        # Security: prevent directory traversal
        if ".." in decoded_filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        file_path = UPLOAD_DIR / decoded_filename
        print(f"📁 File path: {file_path}")
        
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            # List available files for debugging
            available_files = list(UPLOAD_DIR.glob("*.mp4"))
            print(f"📂 Available files: {[f.name for f in available_files]}")
            raise HTTPException(status_code=404, detail=f"Video not found: {decoded_filename}")
        
        print(f"✅ Serving download: {decoded_filename}")
        
        return FileResponse(
            path=str(file_path),
            media_type="video/mp4",
            filename=decoded_filename,
            headers={
                "Content-Disposition": f'attachment; filename="{decoded_filename}"'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error downloading video: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stream-video/{video_id}")
async def stream_video(video_id: str):
    """
    Stream video from MongoDB GridFS for playback
    """
    try:
        print(f"📺 Streaming video from MongoDB: {video_id}")
        
        # Get file from GridFS
        grid_out = await app.fs.open_download_stream(ObjectId(video_id))
        
        # Read file content
        video_content = await grid_out.read()
        
        # Get metadata
        filename = grid_out.filename or "video.mp4"
        content_type = grid_out.metadata.get("content_type", "video/mp4") if grid_out.metadata else "video/mp4"
        
        print(f"✅ Serving video from MongoDB: {filename} ({len(video_content)} bytes)")
        
        return StreamingResponse(
            io.BytesIO(video_content),
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Accept-Ranges": "bytes",
                "Cache-Control": "public, max-age=3600"
            }
        )
    except Exception as e:
        print(f"❌ Error streaming from MongoDB: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Video not found: {str(e)}")

@app.get("/download-video/{video_id}")
async def download_video(video_id: str):
    """
    Download video file from MongoDB GridFS
    """
    try:
        print(f"📥 Download video from MongoDB: {video_id}")
        
        # Get file from GridFS
        grid_out = await app.fs.open_download_stream(ObjectId(video_id))
        
        # Read file content
        video_content = await grid_out.read()
        
        # Get metadata
        filename = grid_out.filename or "video.mp4"
        content_type = grid_out.metadata.get("content_type", "video/mp4") if grid_out.metadata else "video/mp4"
        
        print(f"✅ Serving download from MongoDB: {filename}")
        
        return StreamingResponse(
            io.BytesIO(video_content),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        print(f"❌ Error downloading from MongoDB: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Video not found: {str(e)}")

@app.post("/gps")
async def create_gps(gps: GPS):
    try:
        gps_data = gps.dict()
        if not gps_data.get("timestamp"):
            gps_data["timestamp"] = datetime.utcnow().isoformat()
        
        result = await app.mongodb["gps"].insert_one(gps_data)
        gps_data["_id"] = str(result.inserted_id)
        return {"status": "success", "data": gps_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# GET endpoints for retrieving all data
@app.get("/sentiments")
async def get_sentiments():
    try:
        sentiments = await app.mongodb["sentiments"].find().to_list(1000)
        sentiments = [convert_objectid(item) for item in sentiments]
        return sentiments
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/vlogs")
async def get_vlogs():
    try:
        print("📋 Fetching vlogs from database...")
        vlogs = await app.mongodb["vlogs"].find().to_list(1000)
        print(f"📊 Found {len(vlogs)} vlogs in database")
        
        vlogs = [convert_objectid(item) for item in vlogs]
        
        # Get list of actually available video files
        available_files = {f.name for f in UPLOAD_DIR.glob("*.mp4")}
        print(f"📂 Found {len(available_files)} actual video files on server")
        
        # Filter and ensure each vlog has a proper video_url AND the file exists
        valid_vlogs = []
        for vlog in vlogs:
            video_url = vlog.get('video_url', '')
            
            # Check if it's a local file path (should be skipped)
            if video_url and isinstance(video_url, str) and video_url.startswith('file://'):
                print(f"⚠️ Skipping local file: {vlog.get('_id')}")
                continue
            
            # Check if video_url is None or empty or not a valid HTTP URL
            if not video_url or not isinstance(video_url, str) or not video_url.startswith('http'):
                # If no video_url or it's a local path, try to construct it from filename
                if 'filename' in vlog and vlog['filename']:
                    filename = vlog['filename']
                    
                    # Check if file actually exists on server
                    if filename not in available_files:
                        print(f"⚠️ Skipping vlog {vlog.get('_id')} - file not found on server: {filename}")
                        continue
                    
                    # URL encode the filename to handle spaces and special characters
                    encoded_filename = quote(filename)
                    vlog['video_url'] = f"{BASE_URL}/videos/{encoded_filename}"
                    print(f"📝 Constructed video_url for {vlog.get('_id')}: {vlog['video_url']}")
                    valid_vlogs.append(vlog)
                else:
                    print(f"⚠️ Skipping vlog {vlog.get('_id')} - no valid video source")
                    continue
            else:
                # Has valid HTTP URL - check if file exists
                if 'filename' in vlog:
                    if vlog['filename'] not in available_files:
                        print(f"⚠️ Skipping vlog {vlog.get('_id')} - file not found on server: {vlog['filename']}")
                        continue
                valid_vlogs.append(vlog)
        
        print(f"✅ Returning {len(valid_vlogs)} valid vlogs (filtered from {len(vlogs)} total)")
        return valid_vlogs
    except Exception as e:
        print(f"❌ Error in get_vlogs: {str(e)}")
        import traceback
        traceback.print_exc()
        # Return empty array instead of raising error to prevent dashboard crash
        return []

@app.get("/gps")
async def get_gps():
    try:
        gps_data = await app.mongodb["gps"].find().to_list(1000)
        gps_data = [convert_objectid(item) for item in gps_data]
        return gps_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """
    Dashboard for TAs and instructors to view and download all data
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>EmoGo Data Dashboard</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
        <style>
            :root{
                --bg:#0f1724; --card:#0b1220; --muted:#9aa4b2; --accent:#7c3aed; --glass: rgba(255,255,255,0.04);
            }
            *{box-sizing:border-box}
            body{
                font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial;
                margin:0; min-height:100vh; background:linear-gradient(180deg,#071023 0%, #071729 100%);
                color:#e6eef8; -webkit-font-smoothing:antialiased; padding:28px;
            }
            header{display:flex;align-items:center;justify-content:space-between;margin-bottom:24px}
            h1{font-size:20px;margin:0}
            .subtitle{color:var(--muted);font-size:13px}
            .controls{display:flex;gap:10px}
            .btn{
                background:linear-gradient(90deg,var(--accent),#4f46e5);padding:10px 14px;border-radius:8px;color:#fff;text-decoration:none;font-weight:600;border:none;cursor:pointer;
            }
            .panel{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-bottom:20px}
            .card{background:var(--card);border-radius:12px;padding:18px;box-shadow:0 6px 18px rgba(0,0,0,0.6);border:1px solid rgba(255,255,255,0.03)}
            .card h2{margin:0 0 8px 0;font-size:14px}
            .count{color:var(--muted);font-size:12px}
            .data-preview{background:var(--glass);border-radius:8px;padding:14px;max-height:420px;overflow:auto;border:1px solid rgba(255,255,255,0.02)}
            /* vlog list */
            .vlog-list{display:flex;flex-direction:column;gap:12px}
            .vlog-item{display:flex;gap:12px;align-items:center;background:linear-gradient(180deg, rgba(255,255,255,0.02), transparent);padding:12px;border-radius:10px;border:1px solid rgba(255,255,255,0.02)}
            .vlog-thumb{width:120px;height:70px;background:linear-gradient(90deg,#0b1220,#071029);border-radius:8px;display:flex;align-items:center;justify-content:center;color:var(--muted);font-size:12px}
            .vlog-meta{flex:1}
            .vlog-actions{display:flex;flex-direction:column;gap:8px}
            .link-btn{background:transparent;border:1px solid rgba(255,255,255,0.06);color:#e6eef8;padding:8px 12px;border-radius:8px;text-decoration:none;font-weight:600}
            .small{color:var(--muted);font-size:12px}
            pre{background:#071229;padding:10px;border-radius:8px;color:#c8d4e6;overflow:auto;font-size:12px}
            @media (max-width:900px){.panel{grid-template-columns:repeat(1,1fr)} .vlog-thumb{width:92px;height:60px}}
        </style>
    </head>
    <body>
        <header>
            <div>
                <h1>EmoGo Dashboard</h1>
                <div class="subtitle">View and manage collected data — videos stored permanently in MongoDB GridFS</div>
            </div>
            <div class="controls">
                <button class="btn refresh-btn" onclick="loadAllData()">🔄 Refresh</button>
            </div>
        </header>

        <section class="panel">
            <div class="card">
                <h2>Sentiments</h2>
                <div class="count">Total: <strong id="sentiment-count">Loading...</strong></div>
                <div class="data-preview" id="sentiments-data">Loading...</div>
            </div>
            <div class="card">
                <h2>Vlogs</h2>
                <div class="count">Total: <strong id="vlog-count">Loading...</strong></div>
                <div class="data-preview" id="vlogs-data">Loading...</div>
            </div>
            <div class="card">
                <h2>GPS</h2>
                <div class="count">Total: <strong id="gps-count">Loading...</strong></div>
                <div class="data-preview" id="gps-data">Loading...</div>
            </div>
        </section>

        <script>
            function makeSafeText(s){ 
                try { 
                    return String(s || 'N/A'); 
                } catch(e){ 
                    return 'N/A'; 
                } 
            }

            async function loadData(endpoint, elementId, countId){
                try{
                    console.log('Loading:', endpoint);
                    const res = await fetch(endpoint);
                    
                    if(!res.ok){
                        throw new Error('HTTP ' + res.status);
                    }
                    
                    const data = await res.json();
                    console.log('Loaded', endpoint, ':', data.length, 'items');
                    
                    if(!Array.isArray(data)){
                        document.getElementById(elementId).innerHTML = '<pre>Error: expected array\\n'+JSON.stringify(data,null,2)+'</pre>';
                        document.getElementById(countId).textContent = '0';
                        return;
                    }
                    
                    document.getElementById(countId).textContent = data.length;

                    if(endpoint === '/vlogs'){
                        if(data.length === 0){
                            document.getElementById(elementId).innerHTML = '<div class="small">No videos yet</div>';
                            return;
                        }
                        
                        // Build modern vlog list with single Open button
                        const list = document.createElement('div'); 
                        list.className='vlog-list';
                        
                        data.forEach((item, idx)=>{
                            const div = document.createElement('div'); 
                            div.className='vlog-item';

                            const thumb = document.createElement('div'); 
                            thumb.className='vlog-thumb';
                            thumb.textContent = 'VIDEO';

                            const meta = document.createElement('div'); 
                            meta.className='vlog-meta';
                            
                            const title = document.createElement('div'); 
                            title.innerHTML = '<strong>Video ' + (idx+1) + '</strong> <span class="small"> · ' + makeSafeText(item.user_id) + '</span>';
                            
                            const info = document.createElement('div'); 
                            info.className='small';
                            const timestamp = item.timestamp ? new Date(item.timestamp).toLocaleString() : 'N/A';
                            info.textContent = 'Duration: ' + makeSafeText(item.duration) + 's · Time: ' + timestamp;

                            // Resolve open URL: prefer video_id -> stream endpoint, else use video_url
                            let openUrl = null;
                            if(item.video_id){ 
                                openUrl = '/stream-video/' + item.video_id; 
                            }
                            else if(item.video_url && (item.video_url.startsWith('http') || item.video_url.includes('/stream-video/'))){ 
                                openUrl = item.video_url; 
                            }
                            else if(item.filename){ 
                                openUrl = '/videos/' + encodeURIComponent(item.filename); 
                            }

                            const actions = document.createElement('div'); 
                            actions.className='vlog-actions';

                            if(openUrl){
                                const a = document.createElement('a');
                                a.className='link-btn';
                                a.href = openUrl;
                                a.target = '_blank';
                                a.rel = 'noopener noreferrer';
                                a.textContent = 'Open Video';
                                actions.appendChild(a);
                            } else {
                                const note = document.createElement('div'); 
                                note.className='small'; 
                                note.textContent = 'No accessible video file'; 
                                actions.appendChild(note);
                            }

                            const dbg = document.createElement('details'); 
                            dbg.style.marginTop='8px';
                            const summ = document.createElement('summary'); 
                            summ.style.cursor='pointer'; 
                            summ.className='small'; 
                            summ.textContent='Debug Info';
                            const pre = document.createElement('pre'); 
                            pre.textContent = 'Video URL: ' + makeSafeText(item.video_url) + '\\nVideo ID: ' + makeSafeText(item.video_id) + '\\nFilename: ' + makeSafeText(item.filename);
                            dbg.appendChild(summ); 
                            dbg.appendChild(pre);

                            meta.appendChild(title); 
                            meta.appendChild(info); 
                            meta.appendChild(dbg);

                            div.appendChild(thumb); 
                            div.appendChild(meta); 
                            div.appendChild(actions);
                            list.appendChild(div);
                        });
                        
                        const container = document.getElementById(elementId);
                        container.innerHTML = '';
                        container.appendChild(list);
                    } else {
                        // For sentiments and GPS
                        if(data.length === 0){
                            document.getElementById(elementId).innerHTML = '<div class="small">No data yet</div>';
                        } else {
                            document.getElementById(elementId).innerHTML = '<pre>'+JSON.stringify(data,null,2)+'</pre>';
                        }
                    }
                }catch(err){
                    console.error('Load error:', endpoint, err);
                    document.getElementById(elementId).innerHTML = '<pre>Error loading: '+(err.message||err)+'</pre>';
                    document.getElementById(countId).textContent = '0';
                }
            }

            function loadAllData(){
                console.log('Loading all data...');
                loadData('/sentiments','sentiments-data','sentiment-count');
                loadData('/vlogs','vlogs-data','vlog-count');
                loadData('/gps','gps-data','gps-count');
            }

            window.onload = function(){
                console.log('Page loaded, fetching data...');
                loadAllData();
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/debug/videos")
async def debug_videos():
    """
    Debug endpoint to check uploaded videos
    """
    try:
        video_files = list(UPLOAD_DIR.glob("*.mp4"))
        return {
            "upload_dir": str(UPLOAD_DIR.absolute()),
            "exists": UPLOAD_DIR.exists(),
            "total_videos": len(video_files),
            "videos": [
                {
                    "filename": f.name,
                    "size": f.stat().st_size,
                    "url": f"{BASE_URL}/videos/{f.name}"
                }
                for f in video_files
            ]
        }
    except Exception as e:
        return {"error": str(e)}

@app.delete("/admin/clean-local-vlogs")
async def clean_local_vlogs():
    """
    Admin endpoint to remove vlog records with local file paths
    """
    try:
        print("🧹 Starting cleanup of local file path vlogs...")
        
        # Find all vlogs with local file paths
        vlogs = await app.mongodb["vlogs"].find().to_list(1000)
        local_file_count = 0
        deleted_ids = []
        
        for vlog in vlogs:
            video_url = vlog.get('video_url', '')
            if video_url and isinstance(video_url, str) and video_url.startswith('file://'):
                # Delete this vlog
                result = await app.mongodb["vlogs"].delete_one({"_id": vlog["_id"]})
                if result.deleted_count > 0:
                    local_file_count += 1
                    deleted_ids.append(str(vlog["_id"]))
                    print(f"🗑️  Deleted vlog {vlog['_id']} with local path: {video_url[:100]}...")
        
        print(f"✅ Cleanup complete! Removed {local_file_count} local file vlogs")
        
        return {
            "status": "success",
            "deleted_count": local_file_count,
            "deleted_ids": deleted_ids,
            "message": f"Removed {local_file_count} vlog records with local file paths"
        }
    except Exception as e:
        print(f"❌ Error during cleanup: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    return {
        "status": "ok",
        "dashboard": "/dashboard",
        "endpoints": {
            "upload": "/upload-video",
            "videos": "/videos/{filename}",
            "debug": "/debug/videos"
        }
    }