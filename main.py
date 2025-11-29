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
    Upload video file to server filesystem
    Returns video URL that can be used to access the video
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
        
        # Clean user_id: remove spaces and special characters for safe filename
        safe_user_id = user_id.replace(" ", "_").replace("/", "_").replace("\\", "_")
        
        # Generate unique filename with microseconds for uniqueness
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{safe_user_id}_{timestamp}.mp4"
        file_path = UPLOAD_DIR / filename
        
        # Ensure directory exists
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        
        # Save video file
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        # Verify file was saved
        if not file_path.exists():
            raise HTTPException(status_code=500, detail="Failed to save file")
        
        saved_size = file_path.stat().st_size
        print(f"✅ File saved: {file_path}")
        print(f"✅ Saved size: {saved_size} bytes")
        
        # Generate accessible URL
        file_url = f"{BASE_URL}/videos/{filename}"
        
        print(f"🌐 Public URL: {file_url}")
        print(f"✅ Upload complete!")
        
        return {
            "status": "success",
            "file_url": file_url,
            "filename": filename,
            "user_id": user_id,
            "size": saved_size,
            "uploaded_at": datetime.utcnow().isoformat(),
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

@app.get("/download-video/{video_id}")
async def download_video(video_id: str):
    """
    Download video file from MongoDB GridFS (legacy support)
    """
    try:
        # Get file from GridFS
        grid_out = await app.fs.open_download_stream(ObjectId(video_id))
        
        # Read file content
        video_content = await grid_out.read()
        
        # Get metadata
        filename = grid_out.filename or "video.mp4"
        content_type = grid_out.metadata.get("content_type", "video/mp4") if grid_out.metadata else "video/mp4"
        
        return StreamingResponse(
            io.BytesIO(video_content),
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Accept-Ranges": "bytes"
            }
        )
    except Exception as e:
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
        print(f"📊 Found {len(vlogs)} vlogs")
        
        vlogs = [convert_objectid(item) for item in vlogs]
        
        # Ensure each vlog has a proper video_url
        for vlog in vlogs:
            if 'video_url' not in vlog or not vlog.get('video_url', '').startswith('http'):
                # If no video_url or it's a local path, construct it from filename
                if 'filename' in vlog:
                    # URL encode the filename to handle spaces and special characters
                    encoded_filename = quote(vlog['filename'])
                    vlog['video_url'] = f"{BASE_URL}/videos/{encoded_filename}"
                    print(f"📝 Constructed video_url for {vlog.get('_id')}: {vlog['video_url']}")
        
        print(f"✅ Returning {len(vlogs)} vlogs")
        return vlogs
    except Exception as e:
        print(f"❌ Error in get_vlogs: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

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
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            h1 {
                color: #333;
                text-align: center;
            }
            .section {
                background: white;
                border-radius: 8px;
                padding: 20px;
                margin: 20px 0;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .download-btn {
                background-color: #4CAF50;
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 16px;
                margin: 5px;
                text-decoration: none;
                display: inline-block;
            }
            .download-btn:hover {
                background-color: #45a049;
            }
            .refresh-btn {
                background-color: #2196F3;
            }
            .refresh-btn:hover {
                background-color: #0b7dda;
            }
            .data-preview {
                background: #f9f9f9;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 15px;
                margin-top: 10px;
                max-height: 400px;
                overflow-y: auto;
            }
            .video-item {
                background: #fff;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 15px;
                margin: 10px 0;
            }
            .count {
                color: #666;
                font-size: 14px;
            }
            pre {
                white-space: pre-wrap;
                word-wrap: break-word;
            }
            video {
                max-width: 100%;
                border-radius: 4px;
                margin: 10px 0;
            }
            .video-controls {
                margin-top: 10px;
            }
        </style>
    </head>
    <body>
        <h1>🎭 EmoGo Data Dashboard</h1>
        
        <div class="section">
            <h2>📊 Data Export</h2>
            <p>Click the buttons below to download data in JSON format:</p>
            <a href="/sentiments" class="download-btn" download="sentiments.json">📈 Download Sentiments</a>
            <a href="/vlogs" class="download-btn" download="vlogs.json">🎥 Download Vlogs</a>
            <a href="/gps" class="download-btn" download="gps.json">📍 Download GPS</a>
            <button class="download-btn refresh-btn" onclick="loadAllData()">🔄 Refresh Data</button>
        </div>

        <div class="section">
            <h2>😊 Sentiments (Emotion Scores)</h2>
            <p class="count">Total: <span id="sentiment-count">Loading...</span></p>
            <div id="sentiments-data" class="data-preview">Loading...</div>
        </div>

        <div class="section">
            <h2>🎥 Vlogs (Video Records)</h2>
            <p class="count">Total: <span id="vlog-count">Loading...</span></p>
            <div id="vlogs-data" class="data-preview">Loading...</div>
        </div>

        <div class="section">
            <h2>📍 GPS Coordinates</h2>
            <p class="count">Total: <span id="gps-count">Loading...</span></p>
            <div id="gps-data" class="data-preview">Loading...</div>
        </div>

        <script>
            async function loadData(endpoint, elementId, countId) {
                try {
                    const response = await fetch(endpoint);
                    const data = await response.json();
                    
                    // Check if data is an array
                    if (!Array.isArray(data)) {
                        console.error('Expected array but got:', typeof data, data);
                        document.getElementById(elementId).innerHTML = 
                            '<p style="color: red;">Error: Invalid data format (expected array)</p><pre>' + 
                            JSON.stringify(data, null, 2) + '</pre>';
                        document.getElementById(countId).textContent = '0';
                        return;
                    }
                    
                    document.getElementById(countId).textContent = data.length;
                    
                    if (endpoint === '/vlogs') {
                        // Special handling for vlogs with video player
                        let html = '';
                        data.forEach((item, index) => {
                            html += `<div class="video-item">
                                <strong>🎬 Video ${index + 1}</strong><br>
                                👤 User: ${item.user_id || 'N/A'}<br>
                                ⏱️ Duration: ${item.duration || 'N/A'}s<br>
                                📅 Time: ${new Date(item.timestamp).toLocaleString() || 'N/A'}<br>`;
                            
                            // Determine video source
                            let videoUrl = null;
                            let downloadUrl = null;
                            
                            if (item.video_url && item.video_url.includes('/videos/')) {
                                // Server-hosted video (new format)
                                videoUrl = item.video_url;
                                // Extract filename from URL for download endpoint
                                const urlParts = item.video_url.split('/videos/');
                                if (urlParts.length > 1) {
                                    downloadUrl = '/videos/' + urlParts[1] + '/download';
                                }
                            } else if (item.video_id) {
                                // GridFS video (old format)
                                videoUrl = '/download-video/' + item.video_id;
                                downloadUrl = videoUrl;
                            } else if (item.filename) {
                                // Fallback: construct URL from filename
                                videoUrl = '/videos/' + encodeURIComponent(item.filename);
                                downloadUrl = '/videos/' + encodeURIComponent(item.filename) + '/download';
                            } else if (item.video_url && item.video_url.startsWith('http')) {
                                // External URL
                                videoUrl = item.video_url;
                                downloadUrl = item.video_url;
                            }
                            
                            if (videoUrl) {
                                html += `
                                    <div style="margin-top: 15px;">
                                        <video width="400" height="300" controls preload="metadata">
                                            <source src="${videoUrl}" type="video/mp4">
                                            Your browser does not support the video tag.
                                        </video>
                                        <div class="video-controls">
                                            <a href="${downloadUrl}" class="download-btn" download>📥 Download Video</a>
                                            <a href="${videoUrl}" class="download-btn" target="_blank" style="background-color: #2196F3;">▶️ Open in New Tab</a>
                                        </div>
                                        <details style="margin-top: 10px;">
                                            <summary style="cursor: pointer; color: #666;">🔍 Debug Info</summary>
                                            <pre style="font-size: 11px; background: #f5f5f5; padding: 10px; border-radius: 4px; margin-top: 5px;">Video URL: ${videoUrl}
Download URL: ${downloadUrl}
Filename: ${item.filename || 'N/A'}
Video ID: ${item.video_id || 'N/A'}</pre>
                                        </details>
                                    </div>
                                `;
                            } else if (item.video_url) {
                                // Local file path (not accessible)
                                html += `<br><span style="color: #f44336;">⚠️ Video stored locally on device (not uploaded to server)</span><br>
                                         <small style="color: #666;">${item.video_url}</small>`;
                            } else {
                                html += `<br><span style="color: #f44336;">⚠️ No video file uploaded</span>`;
                            }
                            
                            html += `</div>`;
                        });
                        document.getElementById(elementId).innerHTML = html || '<p>No data available</p>';
                    } else {
                        document.getElementById(elementId).innerHTML = 
                            '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
                    }
                } catch (error) {
                    document.getElementById(elementId).innerHTML = 
                        '<p style="color: red;">Error loading data: ' + error.message + '</p>';
                }
            }

            function loadAllData() {
                loadData('/sentiments', 'sentiments-data', 'sentiment-count');
                loadData('/vlogs', 'vlogs-data', 'vlog-count');
                loadData('/gps', 'gps-data', 'gps-count');
            }

            // Load data on page load
            window.onload = loadAllData;
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