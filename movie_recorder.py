"""
Movie Recorder with S3 Upload + Audio Extraction + Transcription
Records screen WITH AUDIO, extracts audio separately, and generates transcriptions.

Requirements:
    pip install boto3 google-genai python-dotenv

System requirement:
    ffmpeg must be installed (brew install ffmpeg)
    
Audio setup (macOS):
    1. Install BlackHole: brew install blackhole-2ch
    2. Open Audio MIDI Setup (Spotlight → "Audio MIDI Setup")
    3. Click + → Create Multi-Output Device
    4. Check both your speakers/headphones AND BlackHole 2ch
    5. Right-click Multi-Output Device → Use This Device For Sound Output

Environment:
    Set GEMINI_API_KEY in .env file or environment variable

Usage:
    python movie_recorder.py --segment-duration 60
    python movie_recorder.py --segment-duration 60 --audio-device "BlackHole 2ch"
"""

import subprocess
import threading
import time
import os
import argparse
import signal
import sys
from datetime import datetime
from pathlib import Path
from queue import Queue
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Try to import Google GenAI for transcription
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("[WARNING] google-genai not installed. Transcription will be disabled.")
    print("         Install with: pip install google-genai")


class S3Uploader:
    """Handles async uploads to S3."""
    
    def __init__(self, bucket_name: str, region: str, prefix: str = "recordings"):
        self.bucket_name = bucket_name
        self.prefix = prefix
        session = boto3.Session(profile_name='hackathon')
        self.s3_client = session.client('s3', region_name=region)
        self.upload_queue = Queue()
        self.running = True
        self.upload_thread = threading.Thread(target=self._upload_worker, daemon=True)
        self.upload_thread.start()
    
    def _upload_worker(self):
        """Background worker that processes upload queue."""
        while self.running or not self.upload_queue.empty():
            try:
                file_path = self.upload_queue.get(timeout=1)
                self._upload_file(file_path)
                self.upload_queue.task_done()
            except Exception:
                continue
    
    def _upload_file(self, file_path: str):
        """Upload a single file to S3."""
        if not os.path.exists(file_path):
            print(f"[UPLOAD] File not found, skipping: {file_path}")
            return
            
        file_name = os.path.basename(file_path)
        
        # Determine subfolder based on file type
        if file_path.endswith('.mp4'):
            subfolder = "videos"
        elif file_path.endswith('.mp3'):
            subfolder = "audio"
        elif file_path.endswith('.txt'):
            subfolder = "transcripts"
        else:
            subfolder = "other"
        
        s3_key = f"{self.prefix}/{subfolder}/{file_name}"
        
        try:
            file_size = os.path.getsize(file_path)
            size_str = f"{file_size / 1024 / 1024:.1f} MB" if file_size > 1024*1024 else f"{file_size / 1024:.1f} KB"
            print(f"[UPLOAD] Uploading {file_name} ({size_str}) to s3://{self.bucket_name}/{s3_key}")
            self.s3_client.upload_file(file_path, self.bucket_name, s3_key)
            print(f"[UPLOAD] ✓ Completed: {file_name}")
            
        except ClientError as e:
            print(f"[ERROR] Failed to upload {file_name}: {e}")
        except Exception as e:
            print(f"[ERROR] Unexpected error uploading {file_name}: {e}")
    
    def queue_upload(self, file_path: str):
        """Add file to upload queue."""
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            self.upload_queue.put(file_path)
            print(f"[QUEUE] Added {os.path.basename(file_path)} to upload queue")
    
    def stop(self):
        """Stop the uploader and wait for pending uploads."""
        print(f"[UPLOAD] Waiting for {self.upload_queue.qsize()} pending uploads...")
        self.running = False
        self.upload_thread.join(timeout=180)


class AudioProcessor:
    """Handles audio extraction and transcription."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = None
        
        if GENAI_AVAILABLE and self.api_key:
            try:
                # Use v1alpha API version for latest features
                self.client = genai.Client(
                    api_key=self.api_key,
                    http_options={
                        'api_version': 'v1alpha',
                        'timeout': 300_000,  # 5 minutes for transcription
                    }
                )
                print("[TRANSCRIBE] Gemini transcription enabled")
            except Exception as e:
                print(f"[TRANSCRIBE] Failed to initialize Gemini: {e}")
                self.client = None
        elif not self.api_key:
            print("[TRANSCRIBE] No GEMINI_API_KEY found. Transcription disabled.")
    
    def extract_audio(self, video_path: str) -> str:
        """Extract audio from video file to MP3."""
        audio_path = video_path.replace('.mp4', '.mp3')
        
        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-vn",  # No video
            "-acodec", "libmp3lame",
            "-ab", "192k",  # Audio bitrate
            "-ar", "44100",  # Sample rate
            "-ac", "2",  # Stereo
            audio_path
        ]
        
        try:
            print(f"[AUDIO] Extracting audio from {os.path.basename(video_path)}...")
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=60
            )
            
            if result.returncode == 0 and os.path.exists(audio_path):
                print(f"[AUDIO] ✓ Extracted: {os.path.basename(audio_path)}")
                return audio_path
            else:
                print(f"[AUDIO] ✗ Failed to extract audio")
                return None
        except subprocess.TimeoutExpired:
            print(f"[AUDIO] ✗ Timeout extracting audio")
            return None
        except Exception as e:
            print(f"[AUDIO] ✗ Error: {e}")
            return None
    
    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file using Gemini."""
        if not self.client:
            print("[TRANSCRIBE] Transcription not available (no API key or client)")
            return None
        
        transcript_path = audio_path.replace('.mp3', '_transcript.txt')
        
        try:
            print(f"[TRANSCRIBE] Transcribing {os.path.basename(audio_path)}...")
            
            # Upload audio file to Gemini
            with open(audio_path, 'rb') as f:
                audio_data = f.read()
            
            # Create the transcription request using working pattern
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    types.Content(
                        parts=[
                            types.Part.from_bytes(
                                data=audio_data,
                                mime_type="audio/mp3"
                            ),
                            types.Part(text="Please transcribe this audio accurately. "
                                "Include all spoken words. "
                                "Format the output as plain text with proper punctuation. "
                                "If there are multiple speakers, try to indicate speaker changes.")
                        ]
                    )
                ]
            )
            
            transcript = response.text
            
            # Save transcript to file
            with open(transcript_path, 'w', encoding='utf-8') as f:
                f.write(f"Transcription of: {os.path.basename(audio_path)}\n")
                f.write(f"Generated at: {datetime.now().isoformat()}\n")
                f.write("=" * 60 + "\n\n")
                f.write(transcript)
            
            print(f"[TRANSCRIBE] ✓ Saved: {os.path.basename(transcript_path)}")
            return transcript_path
            
        except Exception as e:
            print(f"[TRANSCRIBE] ✗ Error: {e}")
            return None


class MovieRecorder:
    """Records screen WITH AUDIO in segments with audio extraction and transcription."""
    
    def __init__(self, output_dir: str, segment_duration: int = 60, 
                 fps: int = 30, quality: str = "medium", 
                 audio_device: str = None, uploader: S3Uploader = None,
                 audio_processor: AudioProcessor = None, screen_index: int = 1,
                 accumulate: bool = False):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.segment_duration = segment_duration
        self.fps = fps
        self.quality = quality
        self.audio_device = audio_device or "BlackHole 2ch"
        self.screen_index = screen_index  # Which screen to capture (1=main, 2=second monitor, etc.)
        self.uploader = uploader
        self.audio_processor = audio_processor
        self.accumulate = accumulate  # Accumulate mode: each output contains all previous segments
        self.running = False
        self.current_process = None
        self.segment_count = 0
        self.record_thread = None
        self.recorded_segments = []  # Track all recorded segment paths for accumulation
        self.session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Quality presets (CRF - lower = better quality)
        self.quality_presets = {
            "low": "28",
            "medium": "23", 
            "high": "18"
        }
    
    def _get_output_filename(self) -> str:
        """Generate output filename for current segment."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return str(self.output_dir / f"movie_{timestamp}_{self.segment_count:03d}.mp4")
    
    def _record_segment(self, output_file: str) -> bool:
        """Record a single segment with time limit. Returns True if completed normally."""
        crf = self.quality_presets.get(self.quality, "23")
        
        if sys.platform == "darwin":  # macOS
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "avfoundation",
                "-capture_cursor", "1",
                "-framerate", "30",
                "-i", f"{self.screen_index}:{self.audio_device}",  # screen_index:audio_device
                "-t", str(self.segment_duration),
                "-vf", f"fps={self.fps}",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", crf,
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "256k",
                "-ar", "48000",
                "-ac", "2",
                "-af", "aresample=async=1",
                "-movflags", "+faststart",
                output_file
            ]
        elif sys.platform == "linux":
            resolution = self._get_linux_resolution()
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "x11grab",
                "-framerate", str(self.fps),
                "-video_size", resolution,
                "-i", ":0.0",
                "-f", "pulse",
                "-i", "default",
                "-t", str(self.segment_duration),
                "-vf", f"fps={self.fps}",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", crf,
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "256k",
                "-ar", "48000",
                "-ac", "2",
                "-af", "aresample=async=1",
                "-movflags", "+faststart",
                output_file
            ]
        elif sys.platform == "win32":
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "gdigrab",
                "-framerate", str(self.fps),
                "-i", "desktop",
                "-f", "dshow",
                "-i", f"audio={self.audio_device}",
                "-t", str(self.segment_duration),
                "-vf", f"fps={self.fps}",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", crf,
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "256k",
                "-ar", "48000",
                "-ac", "2",
                "-af", "aresample=async=1",
                "-movflags", "+faststart",
                output_file
            ]
        else:
            raise RuntimeError(f"Unsupported platform: {sys.platform}")
        
        print(f"[RECORDER] Recording segment {self.segment_count}: {os.path.basename(output_file)}")
        
        self.current_process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        try:
            self.current_process.wait()
            return self.current_process.returncode == 0
        except Exception:
            return False
    
    def _get_linux_resolution(self) -> str:
        """Get screen resolution on Linux."""
        try:
            result = subprocess.run(
                ["xdpyinfo"], capture_output=True, text=True
            )
            for line in result.stdout.split('\n'):
                if 'dimensions:' in line:
                    return line.split()[1]
        except Exception:
            pass
        return "1920x1080"
    
    def _concatenate_segments(self) -> str:
        """Concatenate all recorded segments into one accumulated file."""
        if len(self.recorded_segments) == 0:
            return None
        
        if len(self.recorded_segments) == 1:
            # Just one segment, copy it as accumulated
            src = self.recorded_segments[0]
            accumulated_path = str(self.output_dir / f"accumulated_{self.session_timestamp}_{self.segment_count:03d}.mp4")
            import shutil
            shutil.copy2(src, accumulated_path)
            return accumulated_path
        
        # Create a concat file list
        concat_list_path = str(self.output_dir / f"_concat_list_{self.segment_count}.txt")
        with open(concat_list_path, 'w') as f:
            for seg_path in self.recorded_segments:
                # Use absolute paths and escape single quotes
                f.write(f"file '{seg_path}'\n")
        
        accumulated_path = str(self.output_dir / f"accumulated_{self.session_timestamp}_{self.segment_count:03d}.mp4")
        
        # Concatenate using ffmpeg
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy",  # Copy streams without re-encoding (fast)
            accumulated_path
        ]
        
        try:
            print(f"[ACCUMULATE] Creating accumulated video ({len(self.recorded_segments)} segments)...")
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=120
            )
            
            # Clean up concat list file
            os.remove(concat_list_path)
            
            if result.returncode == 0 and os.path.exists(accumulated_path):
                duration = len(self.recorded_segments) * self.segment_duration
                print(f"[ACCUMULATE] ✓ Created: {os.path.basename(accumulated_path)} (~{duration}s)")
                return accumulated_path
            else:
                print(f"[ACCUMULATE] ✗ Failed to create accumulated video")
                return None
        except Exception as e:
            print(f"[ACCUMULATE] ✗ Error: {e}")
            if os.path.exists(concat_list_path):
                os.remove(concat_list_path)
            return None
    
    def _process_segment(self, video_path: str):
        """Process a completed segment: extract audio, transcribe, upload all."""
        # Upload video
        if self.uploader:
            self.uploader.queue_upload(video_path)
        
        # Extract audio
        if self.audio_processor:
            audio_path = self.audio_processor.extract_audio(video_path)
            
            if audio_path:
                # Upload audio
                if self.uploader:
                    self.uploader.queue_upload(audio_path)
                
                # Transcribe
                transcript_path = self.audio_processor.transcribe(audio_path)
                
                if transcript_path and self.uploader:
                    self.uploader.queue_upload(transcript_path)
    
    def _recording_loop(self):
        """Main recording loop - records segments until stopped."""
        while self.running:
            output_file = self._get_output_filename()
            
            success = self._record_segment(output_file)
            
            if success and os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
                print(f"[RECORDER] ✓ Segment {self.segment_count} complete: {os.path.basename(output_file)}")
                
                if self.accumulate:
                    # Accumulate mode: concatenate all segments and process accumulated video
                    self.recorded_segments.append(output_file)
                    accumulated_path = self._concatenate_segments()
                    
                    if accumulated_path:
                        self._process_segment(accumulated_path)
                else:
                    # Normal mode: process each segment individually
                    self._process_segment(output_file)
                
                self.segment_count += 1
            elif not self.running:
                if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
                    print(f"[RECORDER] Final segment saved: {os.path.basename(output_file)}")
                    
                    if self.accumulate:
                        self.recorded_segments.append(output_file)
                        accumulated_path = self._concatenate_segments()
                        if accumulated_path:
                            self._process_segment(accumulated_path)
                    else:
                        self._process_segment(output_file)
                break
            else:
                print(f"[RECORDER] Warning: Segment {self.segment_count} may have issues")
                self.segment_count += 1
    
    def start(self):
        """Start recording."""
        self.running = True
        self.segment_count = 0
        
        print(f"[RECORDER] Starting screen + audio recording")
        print(f"[RECORDER] Audio device: {self.audio_device}")
        print(f"[RECORDER] Segment duration: {self.segment_duration} seconds")
        print(f"[RECORDER] Output directory: {self.output_dir}")
        print(f"[RECORDER] Quality: {self.quality} (CRF {self.quality_presets.get(self.quality, '23')})")
        print(f"[RECORDER] Audio extraction: Enabled")
        print(f"[RECORDER] Transcription: {'Enabled' if self.audio_processor and self.audio_processor.client else 'Disabled'}")
        print(f"[RECORDER] Accumulate mode: {'Enabled' if self.accumulate else 'Disabled'}")
        
        self.record_thread = threading.Thread(target=self._recording_loop, daemon=True)
        self.record_thread.start()
    
    def stop(self):
        """Stop recording gracefully."""
        print("[RECORDER] Stopping recording...")
        self.running = False
        
        if self.current_process and self.current_process.poll() is None:
            print("[RECORDER] Stopping current segment...")
            try:
                self.current_process.send_signal(signal.SIGINT)
                self.current_process.wait(timeout=5)
                print("[RECORDER] ✓ Current segment finalized.")
            except subprocess.TimeoutExpired:
                print("[RECORDER] Timeout, terminating...")
                self.current_process.terminate()
                try:
                    self.current_process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.current_process.kill()
                    self.current_process.wait()
            except Exception as e:
                print(f"[RECORDER] Error stopping: {e}")
                try:
                    self.current_process.kill()
                except Exception:
                    pass
        
        if self.record_thread:
            self.record_thread.join(timeout=5)
        
        print(f"[RECORDER] Recording stopped. Total segments: {self.segment_count}")


def main():
    default_output = os.path.expanduser("~/Downloads/dhivya/gemini-superbowl/movie_recordings")
    
    parser = argparse.ArgumentParser(description="Movie recorder with audio extraction and transcription")
    parser.add_argument("--bucket", default="sa-hr-docs-qtest", help="S3 bucket name")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--prefix", default="recordings", help="S3 key prefix")
    parser.add_argument("--output-dir", default=default_output, help="Local directory for recordings")
    parser.add_argument("--segment-duration", type=int, default=60, help="Segment duration in seconds")
    parser.add_argument("--fps", type=int, default=30, help="Frames per second")
    parser.add_argument("--quality", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--audio-device", default="BlackHole 2ch",
                        help="Audio device (macOS: 'BlackHole 2ch')")
    parser.add_argument("--screen", type=int, default=1,
                        help="Screen index to capture (1=main display, 2=second monitor, etc.)")
    parser.add_argument("--gemini-api-key", default=None,
                        help="Gemini API key (or set GEMINI_API_KEY env var)")
    parser.add_argument("--no-transcribe", action="store_true",
                        help="Disable transcription")
    parser.add_argument("--accumulate", action="store_true",
                        help="Accumulate mode: each output contains all previous segments (15s, 30s, 45s, etc.)")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("MOVIE RECORDER + AUDIO + TRANSCRIPTION")
    print("=" * 60)
    print(f"Bucket: {args.bucket}")
    print(f"Region: {args.region}")
    print(f"Output Directory: {args.output_dir}")
    print(f"Segment Duration: {args.segment_duration}s")
    print(f"FPS: {args.fps}")
    print(f"Quality: {args.quality}")
    print(f"Audio Device: {args.audio_device}")
    print(f"Screen Index: {args.screen}")
    print(f"Transcription: {'Disabled' if args.no_transcribe else 'Enabled'}")
    print(f"Accumulate Mode: {'Enabled' if args.accumulate else 'Disabled'}")
    print("=" * 60)
    print("Press Ctrl+C to stop recording\n")
    
    # Initialize components
    uploader = S3Uploader(args.bucket, args.region, args.prefix)
    
    audio_processor = None
    if not args.no_transcribe:
        audio_processor = AudioProcessor(api_key=args.gemini_api_key)
    else:
        # Still create processor for audio extraction, just without transcription
        audio_processor = AudioProcessor(api_key=None)
    
    recorder = MovieRecorder(
        args.output_dir, 
        args.segment_duration, 
        args.fps, 
        args.quality,
        args.audio_device,
        uploader,
        audio_processor,
        args.screen,
        args.accumulate
    )
    
    def signal_handler(sig, frame):
        print("\n[MAIN] Shutting down...")
        recorder.stop()
        time.sleep(3)
        uploader.stop()
        print("[MAIN] Shutdown complete.")
        print(f"[MAIN] Recordings saved in: {args.output_dir}")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    recorder.start()
    
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
