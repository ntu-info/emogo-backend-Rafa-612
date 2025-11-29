# EmoGo Backend API

## 📊 Data Dashboard (Required by TAs)

**🔗 Data Export/Download Page:**  
**https://emogo-backend-rafa-612.onrender.com/dashboard**

This dashboard provides:
- ✅ View all **Sentiments** (emotion scores, weather, location)
- ✅ View all **Vlogs** (video recordings with metadata)
- ✅ View all **GPS coordinates**
- ✅ Download individual videos
- ✅ Export all data as JSON file

---

## 🚀 What This Backend Does

FastAPI backend service for the EmoGo emotion tracking mobile app.

**Features:**
- 📝 Collects emotion data (sentiment scores 0-10)
- 🎥 Stores video logs permanently in MongoDB GridFS
- 📍 Records GPS coordinates with timestamps
- 🌤️ Includes weather and location data
- � All data persists across server restarts

**Tech Stack:**
- FastAPI (Python web framework)
- MongoDB Atlas (database + video storage)
- MongoDB GridFS (permanent video storage)
- Deployed on Render

**API Endpoints:**
```
POST /sentiments      → Store emotion data
POST /upload-video    → Upload video to MongoDB GridFS
POST /vlogs           → Store video metadata
POST /gps             → Store GPS coordinates
GET  /dashboard       → View/download all data
```

---

## 📅 Data Collection Status

**Collection restart date:** November 29, 2024  
All data in the dashboard was collected after this date.