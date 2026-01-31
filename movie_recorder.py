"""
Movie Recorder with S3 Upload
Records screen WITH AUDIO continuously and uploads segments to S3.

Requirements:
    pip install boto3

System requirement:
    ffmpeg must be installed (brew install ffmpeg)
    
Audio setup (macOS):
    1. Install BlackHole: brew install blackhole-2ch
    2. Open Audio MIDI Setup (Spotlight → "Audio MIDI Setup")
    3. Click + → Create Multi-Output Device
    4. Check both your speakers/headphones AND BlackHole 2ch
    5. Right-click Multi-Output Device → Use This Device For Sound Output

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
        s3_key = f"{self.prefix}/{file_name}"
        
        try:
            file_size = os.path.getsize(file_path)
            print(f"[UPLOAD] Uploading {file_name} ({file_size / 1024 / 1024:.1f} MB) to s3://{self.bucket_name}/{s3_key}")
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
        self.upload_thread.join(timeout=120)


class MovieRecorder:
    """Records screen WITH AUDIO in segments - each segment is a separate ffmpeg run."""
    
    def __init__(self, output_dir: str, segment_duration: int = 60, 
                 fps: int = 30, quality: str = "medium", 
                 audio_device: str = None, uploader: S3Uploader = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.segment_duration = segment_duration
        self.fps = fps
        self.quality = quality
        self.audio_device = audio_device or "BlackHole 2ch"  # Default for macOS
        self.uploader = uploader
        self.running = False
        self.current_process = None
        self.segment_count = 0
        self.record_thread = None
        
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
            # Record screen (input 1) with audio from BlackHole
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "avfoundation",
                "-framerate", str(self.fps),
                "-capture_cursor", "1",
                "-i", f"1:{self.audio_device}",  # Screen 1 + audio device
                "-t", str(self.segment_duration),  # Time limit for clean exit
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", crf,
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",  # Audio codec
                "-b:a", "128k",  # Audio bitrate
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
                "-i", "default",  # PulseAudio default
                "-t", str(self.segment_duration),
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", crf,
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "128k",
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
                "-i", f"audio={self.audio_device}",  # Windows audio device
                "-t", str(self.segment_duration),
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", crf,
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "128k",
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
        
        # Wait for ffmpeg to finish (time limit reached or stopped)
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
    
    def _recording_loop(self):
        """Main recording loop - records segments until stopped."""
        while self.running:
            output_file = self._get_output_filename()
            
            # Record one segment
            success = self._record_segment(output_file)
            
            if success and os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
                print(f"[RECORDER] ✓ Segment {self.segment_count} complete: {os.path.basename(output_file)}")
                
                # Queue for upload
                if self.uploader:
                    self.uploader.queue_upload(output_file)
                
                self.segment_count += 1
            elif not self.running:
                # We were stopped mid-recording
                if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
                    print(f"[RECORDER] Final segment saved: {os.path.basename(output_file)}")
                    if self.uploader:
                        self.uploader.queue_upload(output_file)
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
        
        # Start recording in background thread
        self.record_thread = threading.Thread(target=self._recording_loop, daemon=True)
        self.record_thread.start()
    
    def stop(self):
        """Stop recording gracefully."""
        print("[RECORDER] Stopping recording...")
        self.running = False
        
        # Stop current ffmpeg process if running
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
        
        # Wait for recording thread to finish
        if self.record_thread:
            self.record_thread.join(timeout=5)
        
        print(f"[RECORDER] Recording stopped. Total segments: {self.segment_count}")


def main():
    default_output = os.path.expanduser("~/Downloads/dhivya/gemini-superbowl/movie_recordings")
    
    parser = argparse.ArgumentParser(description="Movie recorder (screen + audio) with S3 upload")
    parser.add_argument("--bucket", default="sa-hr-docs-qtest", help="S3 bucket name")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--prefix", default="recordings", help="S3 key prefix")
    parser.add_argument("--output-dir", default=default_output, help="Local directory for recordings")
    parser.add_argument("--segment-duration", type=int, default=60, help="Segment duration in seconds")
    parser.add_argument("--fps", type=int, default=30, help="Frames per second")
    parser.add_argument("--quality", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--audio-device", default="BlackHole 2ch",
                        help="Audio device (macOS: 'BlackHole 2ch', Linux: 'default', Windows: 'Stereo Mix')")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("MOVIE RECORDER (SCREEN + AUDIO) WITH S3 UPLOAD")
    print("=" * 60)
    print(f"Bucket: {args.bucket}")
    print(f"Region: {args.region}")
    print(f"Output Directory: {args.output_dir}")
    print(f"Segment Duration: {args.segment_duration}s")
    print(f"FPS: {args.fps}")
    print(f"Quality: {args.quality}")
    print(f"Audio Device: {args.audio_device}")
    print("=" * 60)
    print("Press Ctrl+C to stop recording\n")
    
    # Initialize components
    uploader = S3Uploader(args.bucket, args.region, args.prefix)
    recorder = MovieRecorder(
        args.output_dir, 
        args.segment_duration, 
        args.fps, 
        args.quality,
        args.audio_device,
        uploader
    )
    
    # Handle graceful shutdown
    def signal_handler(sig, frame):
        print("\n[MAIN] Shutting down...")
        recorder.stop()
        time.sleep(2)
        uploader.stop()
        print("[MAIN] Shutdown complete.")
        print(f"[MAIN] Recordings saved in: {args.output_dir}")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start recording
    recorder.start()
    
    # Keep main thread alive
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
