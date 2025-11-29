[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/e7FBMwSa)
[![Open in Visual Studio Code](https://classroom.github.com/assets/open-in-vscode-2e0aaae1b6195c2367325f4f02e2d04e9abb55f0b24a779b69b11b9e10269abc.svg)](https://classroom.github.com/online_ide?assignment_repo_id=21872056&assignment_repo_type=AssignmentRepo)

# EmoGo Backend API

## 🆕 Data Collection Status

**Data collection restart date**: December 29, 2024  
**Status**: ✅ All previous data cleared, fresh start  
**Note**: All data shown in the dashboard is collected after this date.

## ✅ Video Storage Solution

**MongoDB GridFS**: Video files are permanently stored in the database!

### How it works:
- ✅ Videos are uploaded to MongoDB GridFS (permanent storage)
- ✅ Video metadata is stored in MongoDB collections
- ✅ Videos persist across server restarts
- ✅ No need for external storage services

### Technical details:
```
POST /upload-video → Stores video in MongoDB GridFS → Returns video_id
GET /stream-video/{video_id} → Retrieves and streams video from MongoDB
GET /download-video/{video_id} → Downloads video from MongoDB
```

### Why MongoDB GridFS?
- **Permanent**: Videos stored in database, not ephemeral filesystem
- **Simple**: No need for Cloudinary or external services
- **Free**: Included in MongoDB Atlas free tier (512MB storage)
- **Reliable**: Built-in replication and backup

## 📊 Data Dashboard (For TAs & Instructors)

**Main Dashboard**: https://emogo-backend-rafa-612.onrender.com/dashboard

This dashboard provides:
- ✅ View all collected data (sentiments, vlogs, GPS)
- ✅ Download data in JSON format
- ✅ Download video files directly
- ✅ Real-time data statistics

## Data Export URLs

You can also directly access raw JSON data via these URLs:

- **Sentiments (Emotion Scores)**: https://emogo-backend-rafa-612.onrender.com/sentiments
- **Vlogs (Video Records)**: https://emogo-backend-rafa-612.onrender.com/vlogs
- **GPS Coordinates**: https://emogo-backend-rafa-612.onrender.com/gps

### API Documentation

Interactive API documentation is available at:
- **Swagger UI**: https://emogo-backend-rafa-612.onrender.com/docs
- **ReDoc**: https://emogo-backend-rafa-612.onrender.com/redoc

---

# Deploy FastAPI on Render

Use this repo as a template to deploy a Python [FastAPI](https://fastapi.tiangolo.com) service on Render.

See https://render.com/docs/deploy-fastapi or follow the steps below:

## Manual Steps

1. You may use this repository directly or [create your own repository from this template](https://github.com/render-examples/fastapi/generate) if you'd like to customize the code.
2. Create a new Web Service on Render.
3. Specify the URL to your new repository or this repository.
4. Render will automatically detect that you are deploying a Python service and use `pip` to download the dependencies.
5. Specify the following as the Start Command.

    ```shell
    uvicorn main:app --host 0.0.0.0 --port $PORT
    ```

6. Click Create Web Service.

Or simply click:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/render-examples/fastapi)

## Thanks

Thanks to [Harish](https://harishgarg.com) for the [inspiration to create a FastAPI quickstart for Render](https://twitter.com/harishkgarg/status/1435084018677010434) and for some sample code!