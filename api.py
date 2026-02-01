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
from twitter_service import TwitterService

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

# Initialize Twitter service (optional - may not be configured)
twitter_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global video_analyzer, twitter_service

    # Setup output directory
    output_dir = os.path.expanduser("~/Downloads/sports_journalist_recordings")
    os.makedirs(output_dir, exist_ok=True)
    recorder_state["output_dir"] = output_dir

    # Initialize video analyzer
    video_analyzer = VideoAnalyzer()

    # Initialize Twitter service (optional)
    try:
        twitter_service = TwitterService()
        print("[API] Twitter service initialized")
    except ValueError as e:
        print(f"[API] Twitter service not configured: {e}")
        twitter_service = None

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
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
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


class TweetRequest(BaseModel):
    text: Optional[str] = None
    article: Optional[str] = None
    auto_extract: bool = True


class TweetResponse(BaseModel):
    success: bool
    tweet_id: Optional[str] = None
    tweet_url: Optional[str] = None
    text: Optional[str] = None
    character_count: Optional[int] = None
    error: Optional[str] = None


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
    prompt: Optional[str] = Form(None),
    query: Optional[str] = Form(None)
):
    """
    Analyze video with optional audio transcription or text query.
    
    - audio: Audio file to transcribe (user's question about the play)
    - video_path: Path to video file to analyze (or uses latest recording)
    - prompt: Additional prompt/context for analysis
    - query: Direct text query from user (alternative to audio)
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
        
        # Get user's question - either from text query or transcribed audio
        user_question = query  # Use direct text query if provided
        
        # Transcribe audio if provided and no text query
        if not user_question and audio:
            audio_content = await audio.read()
            user_question = await video_analyzer.transcribe_audio(audio_content)
        
        # Build the analysis prompt with Todd Whitehead persona
        base_prompt = """You are Todd Whitehead, a renowned sports data analyst known for:
- Providing analysis and insight for @SynergySST and @Sportradar
- Sharing basketball/sports data in fun and eye-catching ways
- Creating concise, data-driven content with visual appeal

IMPORTANT FORMATTING RULES:
- Be CONCISE - no fluff or filler text
- Use markdown TABLES to display stats and comparisons
- Include ASCII charts or formatted data visualizations where helpful
- Start directly with the analysis - NO preamble like "Okay, I can analyze..." or "Based on the video..."
- Write in Todd's engaging, data-forward style

"""
        
        if user_question:
            analysis_prompt = f"""{base_prompt}
User's question: "{user_question}"

Provide:
1. **Direct Answer** - Answer the question concisely
2. **Key Stats** - Use a markdown table for any relevant numbers
3. **Quick Analysis** - 2-3 bullet points max
4. **Tweet** - A compelling tweet-worthy summary (280 chars max)

Remember: Be specific about what you observe. Use tables and visual formatting."""
        else:
            analysis_prompt = f"""{base_prompt}
Analyze this play and provide:
1. **Play Breakdown** - What happened (use a table if multiple players involved)
2. **Key Metrics** - Any visible stats in table format
3. **Strategic Insight** - 2-3 bullet points
4. **Tweet** - A compelling summary (280 chars max)

Remember: Be specific about what you observe. Use tables and visual formatting."""
        
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


# ============== Twitter/X Endpoints ==============

@app.post("/api/tweet", response_model=TweetResponse)
async def post_tweet(request: TweetRequest):
    """
    Post a tweet to X (Twitter).

    - text: Direct tweet text (max 280 chars)
    - article: AI-generated article to extract tweet from
    - auto_extract: If true, extract tweet-worthy content from article
    """
    global twitter_service

    if twitter_service is None:
        return TweetResponse(
            success=False,
            error="Twitter service not configured. Please set X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET in .env"
        )

    try:
        # Option 1: Direct tweet text provided
        if request.text:
            result = twitter_service.post_tweet(request.text)

        # Option 2: Extract from article
        elif request.article:
            if request.auto_extract:
                result = twitter_service.post_tweet_from_article(request.article)
            else:
                # Use first 280 chars of article as fallback
                result = twitter_service.post_tweet(request.article)

        else:
            return TweetResponse(
                success=False,
                error="Either 'text' or 'article' must be provided"
            )

        return TweetResponse(**result)

    except Exception as e:
        return TweetResponse(
            success=False,
            error=str(e)
        )


@app.get("/api/twitter/status")
async def get_twitter_status():
    """Check if Twitter service is configured and ready."""
    global twitter_service

    return {
        "configured": twitter_service is not None,
        "message": "Twitter service is ready" if twitter_service else "Twitter service not configured"
    }


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
