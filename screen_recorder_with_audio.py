"""
Screen Recorder with S3 Upload
Records screen WITH AUDIO continuously and uploads 1-minute chunks to S3.

Requirements:
    pip install boto3 mss opencv-python numpy

System requirement:
    ffmpeg must be installed (sudo apt install ffmpeg / brew install ffmpeg)
    
Audio setup:
    macOS: Install BlackHole (brew install blackhole-2ch), create Multi-Output Device
    Linux: PulseAudio (usually pre-installed)
    Windows: Enable Stereo Mix in Sound settings

Usage:
    python screen_recorder_s3.py --bucket your-bucket-name --region us-east-1
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
        self.s3_client = boto3.client('s3', region_name=region)
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
        file_name = os.path.basename(file_path)
        s3_key = f"{self.prefix}/{file_name}"
        
        try:
            print(f"[UPLOAD] Uploading {file_name} to s3://{self.bucket_name}/{s3_key}")
            self.s3_client.upload_file(file_path, self.bucket_name, s3_key)
            print(f"[UPLOAD] ✓ Completed: {file_name}")
            
            # Delete local file after successful upload
            os.remove(file_path)
            print(f"[CLEANUP] Deleted local file: {file_name}")
            
        except ClientError as e:
            print(f"[ERROR] Failed to upload {file_name}: {e}")
        except Exception as e:
            print(f"[ERROR] Unexpected error uploading {file_name}: {e}")
    
    def queue_upload(self, file_path: str):
        """Add file to upload queue."""
        self.upload_queue.put(file_path)
        print(f"[QUEUE] Added {os.path.basename(file_path)} to upload queue")
    
    def stop(self):
        """Stop the uploader and wait for pending uploads."""
        self.running = False
        self.upload_thread.join(timeout=30)


class ScreenRecorder:
    """Records screen with audio in 1-minute segments using ffmpeg."""
    
    def __init__(self, output_dir: str, segment_duration: int = 60, 
                 fps: int = 30, quality: str = "medium", audio_device: str = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.segment_duration = segment_duration
        self.fps = fps
        self.quality = quality
        self.audio_device = audio_device
        self.process = None
        self.running = False
        
        # Quality presets (crf values - lower is better quality, larger file)
        self.quality_presets = {
            "low": "28",
            "medium": "23", 
            "high": "18"
        }
    
    def _get_ffmpeg_command(self) -> list:
        """Build ffmpeg command based on OS."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_pattern = str(self.output_dir / f"recording_{timestamp}_%03d.mp4")
        
        crf = self.quality_presets.get(self.quality, "23")
        
        # Detect OS and build appropriate command
        if sys.platform == "darwin":  # macOS
            # Requires BlackHole for system audio: brew install blackhole-2ch
            # Then create Multi-Output Device in Audio MIDI Setup
            audio_dev = self.audio_device or "BlackHole 2ch"
            return [
                "ffmpeg",
                "-f", "avfoundation",
                "-framerate", str(self.fps),
                "-i", f"1:{audio_dev}",  # Screen 1 + audio device
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", crf,
                "-c:a", "aac",
                "-b:a", "128k",
                "-f", "segment",
                "-segment_time", str(self.segment_duration),
                "-reset_timestamps", "1",
                "-segment_format", "mp4",
                output_pattern
            ]
        elif sys.platform == "linux":
            # Get screen resolution
            resolution = self._get_linux_resolution()
            return [
                "ffmpeg",
                "-f", "x11grab",
                "-framerate", str(self.fps),
                "-video_size", resolution,
                "-i", ":0.0",  # Display :0, screen 0
                "-f", "pulse",
                "-i", "default",  # PulseAudio default source
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", crf,
                "-c:a", "aac",
                "-b:a", "128k",
                "-f", "segment",
                "-segment_time", str(self.segment_duration),
                "-reset_timestamps", "1",
                "-segment_format", "mp4",
                output_pattern
            ]
        elif sys.platform == "win32":  # Windows
            # Requires Stereo Mix enabled in Sound settings
            return [
                "ffmpeg",
                "-f", "gdigrab",
                "-framerate", str(self.fps),
                "-i", "desktop",
                "-f", "dshow",
                "-i", "audio=Stereo Mix (Realtek High Definition Audio)",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", crf,
                "-c:a", "aac",
                "-b:a", "128k",
                "-f", "segment",
                "-segment_time", str(self.segment_duration),
                "-reset_timestamps", "1",
                "-segment_format", "mp4",
                output_pattern
            ]
        else:
            raise RuntimeError(f"Unsupported platform: {sys.platform}")
    
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
        return "1920x1080"  # Default fallback
    
    def start(self):
        """Start recording."""
        cmd = self._get_ffmpeg_command()
        print(f"[RECORDER] Starting ffmpeg with command:")
        print(f"  {' '.join(cmd)}")
        
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE
        )
        self.running = True
        print(f"[RECORDER] Recording started. Segments saved to: {self.output_dir}")
    
    def stop(self):
        """Stop recording gracefully."""
        if self.process:
            self.running = False
            print("[RECORDER] Stopping recording...")
            self.process.stdin.write(b'q')
            self.process.stdin.flush()
            self.process.wait(timeout=10)
            print("[RECORDER] Recording stopped.")


class FileWatcher:
    """Watches for new completed video segments."""
    
    def __init__(self, watch_dir: str, uploader: S3Uploader):
        self.watch_dir = Path(watch_dir)
        self.uploader = uploader
        self.known_files = set()
        self.running = True
        self.watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
    
    def start(self):
        """Start watching for new files."""
        # Initialize with existing files
        self.known_files = set(self.watch_dir.glob("*.mp4"))
        self.watch_thread.start()
        print(f"[WATCHER] Watching {self.watch_dir} for new segments")
    
    def _watch_loop(self):
        """Main watch loop - checks for new completed files."""
        while self.running:
            time.sleep(5)  # Check every 5 seconds
            
            current_files = set(self.watch_dir.glob("*.mp4"))
            new_files = current_files - self.known_files
            
            for file_path in new_files:
                # Wait a moment to ensure file is fully written
                time.sleep(1)
                
                # Check if file size is stable (not being written)
                size1 = file_path.stat().st_size
                time.sleep(0.5)
                size2 = file_path.stat().st_size
                
                if size1 == size2 and size1 > 0:
                    # File is complete, but skip the most recent one (still being written)
                    all_files = sorted(self.watch_dir.glob("*.mp4"), key=os.path.getmtime)
                    if len(all_files) > 1 and file_path != all_files[-1]:
                        self.uploader.queue_upload(str(file_path))
                        self.known_files.add(file_path)
            
            # Update known files
            self.known_files = current_files
    
    def stop(self):
        """Stop watching."""
        self.running = False
        
        # Upload any remaining files
        remaining_files = sorted(self.watch_dir.glob("*.mp4"), key=os.path.getmtime)
        for f in remaining_files:
            self.uploader.queue_upload(str(f))


def main():
    parser = argparse.ArgumentParser(description="Screen recorder with S3 upload")
    parser.add_argument("--bucket", required=True, help="S3 bucket name")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--prefix", default="recordings", help="S3 key prefix")
    parser.add_argument("--output-dir", default="./recordings", help="Local temp directory")
    parser.add_argument("--segment-duration", type=int, default=60, help="Segment duration in seconds")
    parser.add_argument("--fps", type=int, default=30, help="Frames per second")
    parser.add_argument("--quality", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--audio-device", default=None, 
                        help="Audio device name (macOS: 'BlackHole 2ch', Windows: 'Stereo Mix')")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("SCREEN RECORDER WITH AUDIO + S3 UPLOAD")
    print("=" * 60)
    print(f"Bucket: {args.bucket}")
    print(f"Region: {args.region}")
    print(f"Segment Duration: {args.segment_duration}s")
    print(f"FPS: {args.fps}")
    print(f"Quality: {args.quality}")
    print(f"Audio Device: {args.audio_device or 'default'}")
    print("=" * 60)
    print("Press Ctrl+C to stop recording\n")
    
    # Initialize components
    uploader = S3Uploader(args.bucket, args.region, args.prefix)
    recorder = ScreenRecorder(
        args.output_dir, 
        args.segment_duration, 
        args.fps, 
        args.quality,
        args.audio_device
    )
    watcher = FileWatcher(args.output_dir, uploader)
    
    # Handle graceful shutdown
    def signal_handler(sig, frame):
        print("\n[MAIN] Shutting down...")
        recorder.stop()
        watcher.stop()
        uploader.stop()
        print("[MAIN] Shutdown complete.")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start recording
    recorder.start()
    watcher.start()
    
    # Keep main thread alive
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()