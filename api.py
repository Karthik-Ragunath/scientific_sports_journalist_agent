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
import tweepy

# Import our modules
from movie_recorder import MovieRecorder, AudioProcessor
from video_analyzer import VideoAnalyzer

load_dotenv()

# Initialize X/Twitter clients
def get_twitter_credentials():
    """Get Twitter API credentials from environment."""
    return {
        "api_key": os.getenv("X_API_KEY"),
        "api_secret": os.getenv("X_API_SECRET"),
        "access_token": os.getenv("X_ACCESS_TOKEN"),
        "access_token_secret": os.getenv("X_ACCESS_TOKEN_SECRET"),
    }

def get_twitter_client():
    """Create and return Twitter API v2 client."""
    creds = get_twitter_credentials()
    
    if not all(creds.values()):
        return None
    
    client = tweepy.Client(
        consumer_key=creds["api_key"],
        consumer_secret=creds["api_secret"],
        access_token=creds["access_token"],
        access_token_secret=creds["access_token_secret"]
    )
    return client

def get_twitter_api_v1():
    """Create and return Twitter API v1.1 client (needed for media upload)."""
    creds = get_twitter_credentials()
    
    if not all(creds.values()):
        return None
    
    auth = tweepy.OAuth1UserHandler(
        creds["api_key"],
        creds["api_secret"],
        creds["access_token"],
        creds["access_token_secret"]
    )
    return tweepy.API(auth)

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
    
    # Setup output directory - same as movie_recorder.py
    output_dir = os.path.expanduser("~/Downloads/dhivya/gemini-superbowl/movie_recordings")
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
        
        # Wait longer for file to be finalized (concatenation takes time)
        await asyncio.sleep(4)
        
        # Find the latest recorded video - prefer accumulated
        output_dir = Path(recorder_state["output_dir"])
        
        # First check for accumulated videos (most complete)
        accumulated = sorted(output_dir.glob("accumulated_*.mp4"), key=os.path.getmtime, reverse=True)
        all_videos = sorted(output_dir.glob("*.mp4"), key=os.path.getmtime, reverse=True)
        
        current_video = None
        video_url = None
        
        if accumulated:
            current_video = str(accumulated[0])
            print(f"[STOP] Using accumulated video: {accumulated[0].name}")
        elif all_videos:
            current_video = str(all_videos[0])
            print(f"[STOP] Using latest video: {all_videos[0].name}")
        
        if current_video:
            video_filename = os.path.basename(current_video)
            video_url = f"/api/videos/{video_filename}"
            print(f"[STOP] Set current_video: {current_video}")
        
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
        
        # Build the analysis prompt with Todd Whitehead persona - tweet-worthy style
        base_prompt = """You are Todd Whitehead (@ToddWhitehead), sports data analyst for @SynergySST and @Sportradar.

⚠️ CRITICAL: Your ENTIRE response must be TWEET-READY. 
- NEVER start with "Okay", "Here's", "Based on", "I can see", "Let me", or any preamble
- Start IMMEDIATELY with a bold headline or the key insight
- Keep it punchy, data-driven, shareable

"""
        
        if user_question:
            analysis_prompt = f"""{base_prompt}
User asked: "{user_question}"

FORMAT YOUR RESPONSE EXACTLY LIKE THIS (start with the headline, no intro):

**🏀 [HEADLINE - make it punchy]**

| Stat | Value |
|------|-------|
| ... | ... |

📊 **Key Insight:** [One compelling sentence]

🐦 **Tweet:** [280 chars max, include emojis and hashtags]"""
        else:
            analysis_prompt = f"""{base_prompt}
FORMAT YOUR RESPONSE EXACTLY LIKE THIS (start with the headline, no intro):

**🏀 [HEADLINE - make it punchy]**

| Stat | Value |
|------|-------|
| ... | ... |

📊 **Key Insight:** [One compelling sentence]

🐦 **Tweet:** [280 chars max, include emojis and hashtags]"""
        
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


# ============== X/Twitter Posting ==============

class XPostRequest(BaseModel):
    tweet_text: str
    video_path: Optional[str] = None  # Path to video file to attach
    full_content: Optional[str] = None  # Full AI analysis to post as thread

class XPostResponse(BaseModel):
    success: bool
    tweet_id: Optional[str] = None
    tweet_url: Optional[str] = None
    thread_ids: Optional[list] = None  # IDs of all tweets in thread
    error: Optional[str] = None

def format_table_for_twitter(text: str) -> str:
    """Convert markdown tables to Twitter-friendly format."""
    import re
    
    lines = text.split('\n')
    result_lines = []
    table_headers = []
    in_table = False
    
    for line in lines:
        line = line.strip()
        
        # Detect table separator row (|---|---|)
        if re.match(r'^\|[-:\s|]+\|$', line):
            in_table = True
            continue
        
        # Detect table row
        if line.startswith('|') and line.endswith('|'):
            cells = [c.strip() for c in line.split('|')[1:-1]]
            
            if not in_table:
                # This is the header row
                table_headers = cells
                in_table = True
            else:
                # Data row - format as "Header: Value" pairs
                if table_headers and len(cells) == len(table_headers):
                    # Compact format: "Header1: Val1 | Header2: Val2"
                    pairs = [f"{h}: {v}" for h, v in zip(table_headers, cells) if v]
                    formatted = " • ".join(pairs)
                    result_lines.append(f"📊 {formatted}")
                else:
                    # Fallback: just join values
                    result_lines.append(f"📊 {' | '.join(cells)}")
        else:
            # Reset table state if we hit a non-table line
            if in_table and line:
                in_table = False
                table_headers = []
            result_lines.append(line)
    
    return '\n'.join(result_lines)

def split_into_tweets(text: str, max_length: int = 275) -> list:
    """Split long text into tweet-sized chunks, preserving word boundaries."""
    # First, convert tables to Twitter-friendly format
    text = format_table_for_twitter(text)
    
    # Remove markdown formatting for Twitter
    text = text.replace('**', '').replace('*', '').replace('`', '')
    text = text.replace('###', '').replace('##', '').replace('#', '')
    
    if len(text) <= max_length:
        return [text]
    
    tweets = []
    lines = text.split('\n')
    current_tweet = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # If adding this line exceeds limit, save current and start new
        test_length = len(current_tweet) + len(line) + 2  # +2 for newline
        
        if test_length > max_length:
            if current_tweet:
                tweets.append(current_tweet.strip())
            
            # If single line is too long, split by words
            if len(line) > max_length:
                words = line.split()
                current_tweet = ""
                for word in words:
                    if len(current_tweet) + len(word) + 1 > max_length:
                        if current_tweet:
                            tweets.append(current_tweet.strip())
                        current_tweet = word
                    else:
                        current_tweet = f"{current_tweet} {word}".strip()
            else:
                current_tweet = line
        else:
            current_tweet = f"{current_tweet}\n{line}".strip() if current_tweet else line
    
    if current_tweet:
        tweets.append(current_tweet.strip())
    
    # Add thread numbering if multiple tweets
    if len(tweets) > 1:
        tweets = [f"{i+1}/{len(tweets)} {t}" for i, t in enumerate(tweets)]
    
    return tweets

def get_latest_video_path() -> Optional[str]:
    """Get the path to the latest recorded video."""
    movie_dir = Path(os.path.expanduser("~/Downloads/dhivya/gemini-superbowl/movie_recordings"))
    
    print(f"[VIDEO] Looking for videos in: {movie_dir}")
    
    # First priority: use recorder_state if it was just set (freshest)
    if recorder_state.get("current_video") and os.path.exists(recorder_state["current_video"]):
        video_path = recorder_state["current_video"]
        mtime = datetime.fromtimestamp(os.path.getmtime(video_path))
        print(f"[VIDEO] Using recorder state video: {os.path.basename(video_path)} (modified: {mtime})")
        return video_path
    
    if movie_dir.exists():
        # Get all video files
        all_videos = list(movie_dir.glob("*.mp4"))
        
        if all_videos:
            # Sort ALL videos by modification time (newest first)
            all_videos.sort(key=os.path.getmtime, reverse=True)
            
            # Get the absolute newest video
            newest = all_videos[0]
            newest_mtime = datetime.fromtimestamp(os.path.getmtime(newest))
            
            # Also check for newest accumulated video specifically
            accumulated = [v for v in all_videos if "accumulated_" in v.name]
            
            if accumulated:
                newest_acc = accumulated[0]
                acc_mtime = datetime.fromtimestamp(os.path.getmtime(newest_acc))
                
                # Use accumulated if it's very recent (within 60 seconds of newest)
                time_diff = (newest_mtime - acc_mtime).total_seconds()
                if time_diff < 60:
                    print(f"[VIDEO] Using accumulated video: {newest_acc.name} (modified: {acc_mtime})")
                    return str(newest_acc)
            
            # Otherwise use absolute newest
            print(f"[VIDEO] Using newest video: {newest.name} (modified: {newest_mtime})")
            return str(newest)
    
    print("[VIDEO] No video found")
    return None

@app.post("/api/post-to-x", response_model=XPostResponse)
async def post_to_x(request: XPostRequest):
    """
    Post to X/Twitter with optional video attachment.
    
    - tweet_text: Main tweet text (will be first tweet if thread)
    - video_path: Optional path to video file (uses latest if not provided)
    - full_content: Optional full AI analysis to post as a thread
    """
    try:
        client = get_twitter_client()
        api_v1 = get_twitter_api_v1()
        
        if not client:
            raise HTTPException(
                status_code=500, 
                detail="X/Twitter credentials not configured. Set X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET in .env"
            )
        
        # Get video path
        video_path = request.video_path
        if not video_path:
            video_path = get_latest_video_path()
        
        # Upload video if available
        media_id = None
        if video_path and os.path.exists(video_path) and api_v1:
            try:
                file_size = os.path.getsize(video_path)
                print(f"[X POST] Uploading video: {video_path} ({file_size / 1024 / 1024:.1f} MB)")
                
                # Twitter video upload (chunked for large files)
                media = api_v1.media_upload(
                    filename=video_path,
                    media_category='tweet_video',
                    chunked=True
                )
                media_id = media.media_id_string
                print(f"[X POST] Video uploaded, media_id: {media_id}")
            except Exception as e:
                print(f"[X POST] Video upload failed: {e}")
                # Continue without video
        
        # Determine content to post
        content_to_post = request.full_content or request.tweet_text
        
        # Split into tweets if content is long
        tweets_content = split_into_tweets(content_to_post)
        
        thread_ids = []
        first_tweet_id = None
        previous_tweet_id = None
        
        for i, tweet_text in enumerate(tweets_content):
            # First tweet gets the video
            tweet_media_ids = [media_id] if (i == 0 and media_id) else None
            
            # Reply to previous tweet if this is part of a thread
            reply_to = previous_tweet_id if previous_tweet_id else None
            
            response = client.create_tweet(
                text=tweet_text,
                media_ids=tweet_media_ids,
                in_reply_to_tweet_id=reply_to
            )
            
            tweet_id = response.data['id']
            thread_ids.append(tweet_id)
            
            if i == 0:
                first_tweet_id = tweet_id
            
            previous_tweet_id = tweet_id
            print(f"[X POST] Posted tweet {i+1}/{len(tweets_content)}: {tweet_id}")
        
        tweet_url = f"https://x.com/i/web/status/{first_tweet_id}"
        
        return XPostResponse(
            success=True,
            tweet_id=first_tweet_id,
            tweet_url=tweet_url,
            thread_ids=thread_ids,
            error=None
        )
        
    except tweepy.TweepyException as e:
        print(f"[X POST] Twitter API error: {e}")
        return XPostResponse(
            success=False,
            tweet_id=None,
            tweet_url=None,
            thread_ids=None,
            error=f"Twitter API error: {str(e)}"
        )
    except Exception as e:
        print(f"[X POST] Error: {e}")
        return XPostResponse(
            success=False,
            tweet_id=None,
            tweet_url=None,
            thread_ids=None,
            error=str(e)
        )

@app.get("/api/latest-video")
async def get_latest_video():
    """Get info about the latest recorded video."""
    video_path = get_latest_video_path()
    
    if not video_path or not os.path.exists(video_path):
        return {"video_path": None, "exists": False}
    
    stat = os.stat(video_path)
    return {
        "video_path": video_path,
        "filename": os.path.basename(video_path),
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "exists": True
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
