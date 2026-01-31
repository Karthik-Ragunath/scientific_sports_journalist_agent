"""
FastAPI Backend for Scientific Sports Journalist Agent

Provides API endpoints for:
1. Screen recording control (start/stop)
2. Video analysis with Gemini AI
3. Audio transcription

Usage:
    uvicorn api:app --reload --port 8000
"""

import os
import asyncio
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

# Import our modules
from movie_recorder import MovieRecorder, AudioProcessor
from video_analyzer import VideoAnalyzer

load_dotenv()

# Global state for recorder
recorder_state = {
    "recorder": None,
    "is_recording": False,
    "current_video": None,
    "output_dir": None,
    "session_id": None
}

# Initialize video analyzer
video_analyzer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global video_analyzer
    
    # Setup output directory
    output_dir = os.path.expanduser("~/Downloads/sports_journalist_recordings")
    os.makedirs(output_dir, exist_ok=True)
    recorder_state["output_dir"] = output_dir
    
    # Initialize video analyzer
    video_analyzer = VideoAnalyzer()
    
    print(f"[API] Output directory: {output_dir}")
    print("[API] Server started successfully")
    
    yield
    
    # Cleanup on shutdown
    if recorder_state["recorder"] and recorder_state["is_recording"]:
        recorder_state["recorder"].stop()
    print("[API] Server shutdown complete")

app = FastAPI(
    title="Scientific Sports Journalist API",
    description="AI-powered sports video analysis and journalism",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve recorded videos statically
# Will be mounted after output_dir is set


# ============== Pydantic Models ==============

class RecordingConfig(BaseModel):
    segment_duration: int = 30
    quality: str = "medium"
    audio_device: str = "BlackHole 2ch"
    screen_index: int = 1

class RecordingStatus(BaseModel):
    is_recording: bool
    session_id: Optional[str]
    current_video: Optional[str]
    video_url: Optional[str]

class AnalysisRequest(BaseModel):
    video_path: Optional[str] = None
    prompt: str = "Analyze this sports play and provide detailed insights."
    transcribed_text: Optional[str] = None

class AnalysisResponse(BaseModel):
    success: bool
    analysis: Optional[str]
    thinking: Optional[str]
    error: Optional[str]


# ============== Recording Endpoints ==============

@app.post("/api/recording/start", response_model=RecordingStatus)
async def start_recording(config: RecordingConfig = RecordingConfig()):
    """Start screen recording."""
    global recorder_state
    
    if recorder_state["is_recording"]:
        raise HTTPException(status_code=400, detail="Recording already in progress")
    
    try:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        recorder_state["session_id"] = session_id
        
        # Create audio processor for transcription
        audio_processor = AudioProcessor()
        
        # Create recorder instance
        recorder = MovieRecorder(
            output_dir=recorder_state["output_dir"],
            segment_duration=config.segment_duration,
            quality=config.quality,
            audio_device=config.audio_device,
            screen_index=config.screen_index,
            audio_processor=audio_processor,
            uploader=None,  # No S3 upload for API mode
            accumulate=True  # Accumulate segments for continuous video
        )
        
        recorder_state["recorder"] = recorder
        recorder_state["is_recording"] = True
        
        # Start recording in background
        recorder.start()
        
        return RecordingStatus(
            is_recording=True,
            session_id=session_id,
            current_video=None,
            video_url=None
        )
        
    except Exception as e:
        recorder_state["is_recording"] = False
        raise HTTPException(status_code=500, detail=f"Failed to start recording: {str(e)}")


@app.post("/api/recording/stop", response_model=RecordingStatus)
async def stop_recording():
    """Stop screen recording and return the video path."""
    global recorder_state
    
    if not recorder_state["is_recording"]:
        raise HTTPException(status_code=400, detail="No recording in progress")
    
    try:
        recorder = recorder_state["recorder"]
        recorder.stop()
        
        # Wait a moment for file to be finalized
        await asyncio.sleep(2)
        
        # Find the latest recorded video
        output_dir = Path(recorder_state["output_dir"])
        video_files = sorted(output_dir.glob("*.mp4"), key=os.path.getmtime, reverse=True)
        
        current_video = None
        video_url = None
        
        if video_files:
            current_video = str(video_files[0])
            video_filename = os.path.basename(current_video)
            video_url = f"/api/videos/{video_filename}"
        
        recorder_state["current_video"] = current_video
        recorder_state["is_recording"] = False
        recorder_state["recorder"] = None
        
        return RecordingStatus(
            is_recording=False,
            session_id=recorder_state["session_id"],
            current_video=current_video,
            video_url=video_url
        )
        
    except Exception as e:
        recorder_state["is_recording"] = False
        raise HTTPException(status_code=500, detail=f"Failed to stop recording: {str(e)}")


@app.get("/api/recording/status", response_model=RecordingStatus)
async def get_recording_status():
    """Get current recording status."""
    video_url = None
    if recorder_state["current_video"]:
        video_filename = os.path.basename(recorder_state["current_video"])
        video_url = f"/api/videos/{video_filename}"
    
    return RecordingStatus(
        is_recording=recorder_state["is_recording"],
        session_id=recorder_state["session_id"],
        current_video=recorder_state["current_video"],
        video_url=video_url
    )


@app.get("/api/videos/{filename}")
async def get_video(filename: str):
    """Serve a recorded video file."""
    video_path = Path(recorder_state["output_dir"]) / filename
    
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")
    
    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=filename
    )


@app.get("/api/videos")
async def list_videos():
    """List all recorded videos."""
    output_dir = Path(recorder_state["output_dir"])
    
    if not output_dir.exists():
        return {"videos": []}
    
    videos = []
    for video_file in sorted(output_dir.glob("*.mp4"), key=os.path.getmtime, reverse=True):
        stat = video_file.stat()
        videos.append({
            "filename": video_file.name,
            "url": f"/api/videos/{video_file.name}",
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })
    
    return {"videos": videos[:10]}  # Return latest 10


# ============== Analysis Endpoints ==============

@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_video(
    audio: Optional[UploadFile] = File(None),
    video_path: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None)
):
    """
    Analyze video with optional audio transcription.
    
    - audio: Audio file to transcribe (user's question about the play)
    - video_path: Path to video file to analyze (or uses latest recording)
    - prompt: Additional prompt/context for analysis
    """
    global video_analyzer
    
    try:
        # Get video path - use provided or latest recording
        if not video_path:
            video_path = recorder_state.get("current_video")
        
        if not video_path or not os.path.exists(video_path):
            # Try to find latest video
            output_dir = Path(recorder_state["output_dir"])
            video_files = sorted(output_dir.glob("*.mp4"), key=os.path.getmtime, reverse=True)
            if video_files:
                video_path = str(video_files[0])
            else:
                raise HTTPException(status_code=400, detail="No video available for analysis")
        
        # Transcribe audio if provided
        transcribed_text = None
        if audio:
            audio_content = await audio.read()
            transcribed_text = await video_analyzer.transcribe_audio(audio_content)
        
        # Build the analysis prompt
        analysis_prompt = prompt or "Analyze this sports play with detailed insights."
        
        if transcribed_text:
            analysis_prompt = f"""User's question about the play: "{transcribed_text}"

Based on the video, please provide:
1. A detailed answer to the user's question
2. Key observations about the play
3. Strategic analysis
4. Generate a compelling tweet about this moment

Format your response as a sports journalism article with markdown formatting."""
        
        # Analyze the video
        result = await video_analyzer.analyze_video(video_path, analysis_prompt)
        
        return AnalysisResponse(
            success=True,
            analysis=result.get("response"),
            thinking=result.get("thinking"),
            error=None
        )
        
    except Exception as e:
        return AnalysisResponse(
            success=False,
            analysis=None,
            thinking=None,
            error=str(e)
        )


@app.post("/api/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Transcribe audio file to text."""
    global video_analyzer
    
    try:
        audio_content = await audio.read()
        transcribed_text = await video_analyzer.transcribe_audio(audio_content)
        
        return {
            "success": True,
            "transcription": transcribed_text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


# ============== Health Check ==============

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "recording_available": recorder_state["output_dir"] is not None,
        "analyzer_available": video_analyzer is not None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
