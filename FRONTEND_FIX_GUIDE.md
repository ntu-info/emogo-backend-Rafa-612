# 🎥 Frontend Video Upload Fix Guide

## 問題診斷

目前前端存在以下問題：
1. ✅ 後端 API 已經準備好 (`POST /upload-video`)
2. ❌ 前端仍在儲存本地檔案路徑而非上傳真正的影片
3. ❌ Dashboard 無法播放影片
4. ❌ 下載的是 JSON 檔案而非 MP4 檔案

## 問題根源

前端可能正在做這樣的事情：
```javascript
// ❌ 錯誤做法：只儲存本地路徑
await fetch('https://emogo-backend-rafa-612.onrender.com/vlogs', {
  method: 'POST',
  body: JSON.stringify({
    user_id: "...",
    video_url: videoUri,  // ← 這是本地路徑！例如：file:///...
    duration: 1.0
  })
});
```

## 正確的修復方案

前端需要分三步驟上傳：

### 步驟 1: 上傳影片檔案到伺服器

```javascript
// ✅ 正確做法：上傳真正的影片檔案
const uploadVideo = async (videoUri, userId) => {
  try {
    console.log('📤 Starting video upload...');
    console.log('📹 Video URI:', videoUri);
    
    // 建立 FormData
    const formData = new FormData();
    
    // 添加影片檔案
    formData.append('file', {
      uri: videoUri,
      type: 'video/mp4',
      name: `video_${Date.now()}.mp4`
    });
    
    // 添加 user_id
    formData.append('user_id', userId);
    
    // 添加 metadata（可選）
    const metadata = {
      timestamp: new Date().toISOString(),
      emotion_score: emotionScore,
      location: locationData,
      weather: weatherData
    };
    formData.append('metadata', JSON.stringify(metadata));
    
    console.log('📦 FormData prepared, sending request...');
    
    // 上傳到後端
    const response = await fetch('https://emogo-backend-rafa-612.onrender.com/upload-video', {
      method: 'POST',
      body: formData,
      headers: {
        // 不要設定 Content-Type，讓瀏覽器自動設定 multipart/form-data
      }
    });
    
    console.log('📡 Response status:', response.status);
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Upload failed: ${response.status} - ${errorText}`);
    }
    
    const result = await response.json();
    console.log('✅ Video uploaded successfully:', result);
    
    // result.file_url 就是影片的公開 URL
    return result.file_url;
    
  } catch (error) {
    console.error('❌ Video upload error:', error);
    throw error;
  }
};
```

### 步驟 2: 儲存情緒分數

```javascript
const saveSentiment = async (userId, emotionScore, locationData, weatherData) => {
  try {
    const response = await fetch('https://emogo-backend-rafa-612.onrender.com/sentiments', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        user_id: userId,
        emotion_score: emotionScore,
        timestamp: new Date().toISOString(),
        weather: `${weatherData.temperature}°C, ${weatherData.condition}`,
        location: locationData
      })
    });
    
    const result = await response.json();
    console.log('✅ Sentiment saved:', result);
    return result;
  } catch (error) {
    console.error('❌ Sentiment save error:', error);
    throw error;
  }
};
```

### 步驟 3: 儲存 Vlog metadata（使用步驟1的 URL）

```javascript
const saveVlogMetadata = async (userId, videoUrl, duration, locationData) => {
  try {
    const response = await fetch('https://emogo-backend-rafa-612.onrender.com/vlogs', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        user_id: userId,
        video_url: videoUrl,  // ← 使用步驟1返回的 file_url
        duration: duration,
        timestamp: new Date().toISOString(),
        location: locationData
      })
    });
    
    const result = await response.json();
    console.log('✅ Vlog metadata saved:', result);
    return result;
  } catch (error) {
    console.error('❌ Vlog save error:', error);
    throw error;
  }
};
```

### 步驟 4: 儲存 GPS 座標

```javascript
const saveGPS = async (userId, latitude, longitude) => {
  try {
    const response = await fetch('https://emogo-backend-rafa-612.onrender.com/gps', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        user_id: userId,
        latitude: latitude,
        longitude: longitude,
        timestamp: new Date().toISOString()
      })
    });
    
    const result = await response.json();
    console.log('✅ GPS saved:', result);
    return result;
  } catch (error) {
    console.error('❌ GPS save error:', error);
    throw error;
  }
};
```

### 完整流程：整合所有步驟

```javascript
const handleSaveRecord = async () => {
  try {
    console.log('💾 Starting save process...');
    
    // 1. 上傳影片檔案
    const videoUrl = await uploadVideo(recordedVideoUri, userId);
    console.log('✅ Step 1: Video uploaded to:', videoUrl);
    
    // 2. 儲存情緒分數
    await saveSentiment(userId, emotionScore, locationData, weatherData);
    console.log('✅ Step 2: Sentiment saved');
    
    // 3. 儲存 Vlog metadata（使用剛才上傳的 videoUrl）
    await saveVlogMetadata(userId, videoUrl, videoDuration, locationData);
    console.log('✅ Step 3: Vlog metadata saved');
    
    // 4. 儲存 GPS
    await saveGPS(userId, locationData.latitude, locationData.longitude);
    console.log('✅ Step 4: GPS saved');
    
    console.log('🎉 All data saved successfully!');
    alert('Record saved successfully!');
    
  } catch (error) {
    console.error('❌ Save failed:', error);
    alert(`Failed to save record: ${error.message}`);
  }
};
```

## React Native 特定實作

如果你使用 React Native 和 Expo：

```javascript
import * as FileSystem from 'expo-file-system';

const uploadVideo = async (videoUri, userId) => {
  try {
    // React Native 需要使用 FileSystem.uploadAsync
    const response = await FileSystem.uploadAsync(
      'https://emogo-backend-rafa-612.onrender.com/upload-video',
      videoUri,
      {
        httpMethod: 'POST',
        uploadType: FileSystem.FileSystemUploadType.MULTIPART,
        fieldName: 'file',
        parameters: {
          user_id: userId,
          metadata: JSON.stringify({
            timestamp: new Date().toISOString(),
            // ... other metadata
          })
        }
      }
    );
    
    const result = JSON.parse(response.body);
    console.log('✅ Upload result:', result);
    return result.file_url;
    
  } catch (error) {
    console.error('❌ Upload error:', error);
    throw error;
  }
};
```

## 測試步驟

1. **測試影片上傳**
   ```javascript
   // 在 console 中應該看到：
   // 📤 Starting video upload...
   // 📦 FormData prepared, sending request...
   // 📡 Response status: 200
   // ✅ Video uploaded successfully: { file_url: "https://...", ... }
   ```

2. **檢查後端 logs**
   在 Render dashboard 應該看到：
   ```
   📤 Receiving video upload request
   📦 File: video_1234567890.mp4, Content-Type: video/mp4
   ✅ File saved: /app/uploads/videos/...
   🌐 Public URL: https://emogo-backend-rafa-612.onrender.com/videos/...
   ```

3. **檢查 Dashboard**
   - 訪問：https://emogo-backend-rafa-612.onrender.com/dashboard
   - 應該看到影片播放器並能播放
   - 點擊下載按鈕應該下載 .mp4 檔案

## 常見錯誤排查

### 錯誤 1: 422 Unprocessable Entity
**原因**：FormData 格式錯誤或缺少必要欄位
**解決**：確保 `file` 和 `user_id` 都有包含

### 錯誤 2: CORS Error
**原因**：後端 CORS 設定問題（已修復）
**解決**：確認後端已部署最新版本

### 錯誤 3: 影片無法播放
**原因**：上傳的不是真正的影片檔案
**解決**：確認 FormData 中的 file 是 Blob/File 物件，不是字串路徑

### 錯誤 4: 下載的是 JSON 而非 MP4
**原因**：`video_url` 仍是本地路徑或錯誤的 URL
**解決**：使用 `/upload-video` 返回的 `file_url`

## 驗證成功的標準

✅ Console 顯示：
```
✅ Video uploaded successfully: { file_url: "https://emogo-backend-rafa-612.onrender.com/videos/...", ... }
✅ Sentiment saved
✅ Vlog metadata saved
✅ GPS saved
```

✅ Dashboard 顯示：
- 影片播放器正常顯示
- 點擊播放可以看影片
- 下載按鈕下載 .mp4 檔案

✅ 後端 logs 顯示：
```
📤 Receiving video upload request
✅ File saved: ...
🌐 Public URL: https://...
```

## 需要修改的檔案

請在前端專案中找到以下檔案並修改：

1. **影片錄製頁面** (可能是 `RecordScreen.js` 或類似名稱)
2. **儲存邏輯** (可能在 `handleSave` 或 `submitRecord` 函數)
3. **API 服務** (可能是 `api.js` 或 `services/api.js`)

---

## 🚀 Quick Fix Checklist

- [ ] 移除所有使用本地路徑 (`file://...`) 的程式碼
- [ ] 實作 `uploadVideo()` 函數使用 FormData
- [ ] 確保上傳到 `/upload-video` endpoint
- [ ] 使用返回的 `file_url` 儲存到 `/vlogs`
- [ ] 測試：上傳 → 檢查 Dashboard → 確認可播放
- [ ] 測試：下載按鈕 → 確認下載 .mp4 檔案

---

**請將此指南分享給前端開發者，並按照步驟修改前端程式碼。**
