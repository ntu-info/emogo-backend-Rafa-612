from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from bson import ObjectId
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import io

MONGODB_URI = "mongodb+srv://Rafa-612:eQ8IOESaO4lyLnm2@rafa-612.qiobhis.mongodb.net/?appName=Rafa-612"  # your URI
DB_NAME = "emogo_db"  # your DB name

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
    user_id: str = None,
    duration: float = None,
    location: str = None
):
    """
    Upload video file to MongoDB GridFS
    Returns video_id that can be used to retrieve the video
    """
    try:
        # Read video file
        video_content = await file.read()
        
        # Upload to GridFS
        file_id = await app.fs.upload_from_stream(
            file.filename,
            video_content,
            metadata={
                "content_type": file.content_type,
                "user_id": user_id,
                "duration": duration,
                "location": location,
                "upload_time": datetime.utcnow().isoformat()
            }
        )
        
        # Save metadata to vlogs collection
        vlog_data = {
            "user_id": user_id,
            "video_id": str(file_id),
            "filename": file.filename,
            "duration": duration,
            "location": location,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        result = await app.mongodb["vlogs"].insert_one(vlog_data)
        vlog_data["_id"] = str(result.inserted_id)
        
        return {
            "status": "success",
            "video_id": str(file_id),
            "download_url": f"/download-video/{str(file_id)}",
            "data": vlog_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download-video/{video_id}")
async def download_video(video_id: str):
    """
    Download video file from MongoDB GridFS
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
                "Content-Disposition": f'attachment; filename="{filename}"'
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
        vlogs = await app.mongodb["vlogs"].find().to_list(1000)
        vlogs = [convert_objectid(item) for item in vlogs]
        return vlogs
    except Exception as e:
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
                padding: 10px;
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
                    document.getElementById(countId).textContent = data.length;
                    
                    if (endpoint === '/vlogs') {
                        // Special handling for vlogs with video links
                        let html = '';
                        data.forEach((item, index) => {
                            html += `<div class="video-item">
                                <strong>Video ${index + 1}</strong><br>
                                User: ${item.user_id || 'N/A'}<br>
                                Duration: ${item.duration || 'N/A'}s<br>
                                Time: ${item.timestamp || 'N/A'}<br>`;
                            
                            if (item.video_id) {
                                html += `<a href="/download-video/${item.video_id}" class="download-btn" style="margin-top: 10px;">📥 Download Video</a>`;
                            } else if (item.video_url) {
                                html += `<br>Video URL: ${item.video_url}`;
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

@app.get("/")
def read_root():
    return {"status": "ok", "dashboard": "/dashboard"}