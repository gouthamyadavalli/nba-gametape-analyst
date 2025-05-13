# clip_api.py

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from clip_manager import ClipManager
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('clip_api')

app = FastAPI(title="NBA Clip Acquisition API")

# Models
class ClipResponse(BaseModel):
    clip_id: str
    title: str
    source: str
    acquired_at: str
    processed: bool
    local_path: str

class YouTubeRequest(BaseModel):
    url: str
    title: Optional[str] = None

class HighlightsRequest(BaseModel):
    count: Optional[int] = 5

# Routes
@app.post("/clips/youtube", response_model=ClipResponse)
async def download_youtube_clip(request: YouTubeRequest):
    """Download a clip from YouTube"""
    try:
        clip = ClipManager.download_youtube_clip(request.url, request.title)
        if not clip:
            raise HTTPException(status_code=500, detail=f"Failed to download YouTube clip {request.url}")
        return clip
    except Exception as e:
        logger.error(f"Error downloading YouTube clip: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/clips/highlights", response_model=List[ClipResponse])
async def fetch_highlights(request: HighlightsRequest):
    """Fetch NBA highlight clips"""
    try:
        clips = ClipManager.fetch_nba_highlights(request.count)
        if not clips:
            raise HTTPException(status_code=404, detail="No highlight clips found")
        return clips
    except Exception as e:
        logger.error(f"Error fetching highlights: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/clips/upload", response_model=ClipResponse)
async def upload_clip(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None)
):
    """Upload a clip file"""
    try:
        clip = ClipManager.upload_clip(file.file, file.filename, title)
        if not clip:
            raise HTTPException(status_code=500, detail="Failed to save uploaded clip")
        return clip
    except Exception as e:
        logger.error(f"Error uploading clip: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/clips", response_model=List[ClipResponse])
async def get_all_clips():
    """Get all clips"""
    try:
        return ClipManager.get_all_clips()
    except Exception as e:
        logger.error(f"Error getting all clips: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/clips/{clip_id}", response_model=ClipResponse)
async def get_clip(clip_id: str):
    """Get a specific clip by ID"""
    try:
        clip = ClipManager.get_clip(clip_id)
        if not clip:
            raise HTTPException(status_code=404, detail=f"Clip {clip_id} not found")
        return clip
    except Exception as e:
        logger.error(f"Error getting clip: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/clips/unprocessed", response_model=List[ClipResponse])
async def get_unprocessed_clips():
    """Get all unprocessed clips"""
    try:
        return ClipManager.get_unprocessed_clips()
    except Exception as e:
        logger.error(f"Error getting unprocessed clips: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/clips/{clip_id}/mark-processed")
async def mark_clip_processed(clip_id: str):
    """Mark a clip as processed"""
    try:
        ClipManager.mark_processed(clip_id)
        return {"status": "success", "message": f"Clip {clip_id} marked as processed"}
    except Exception as e:
        logger.error(f"Error marking clip as processed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Run the API
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("clip_api:app", host="0.0.0.0", port=8000, reload=True)