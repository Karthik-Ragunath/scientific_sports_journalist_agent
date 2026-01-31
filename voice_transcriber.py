"""
Real-time Voice Transcriber using Google Gemini API (or Pipecat)

Default: Uses chunked audio transcription with Gemini API (works reliably)
Optional: Use --use-pipecat for real-time streaming via Pipecat (requires Gemini Live API access)

Requirements:
    pip install google-genai python-dotenv pyaudio
    pip install "pipecat-ai[google]"  # Optional, for Pipecat mode

Environment:
    Set GOOGLE_API_KEY or GEMINI_API_KEY in .env file or environment variable

Usage:
    # Default (Google Gemini chunked transcription)
    python voice_transcriber.py
    python voice_transcriber.py --output transcription.txt
    python voice_transcriber.py --output transcription.txt --duration 60
    python voice_transcriber.py --chunk-seconds 3  # Transcribe every 3 seconds
    
    # Pipecat mode (requires Gemini Live API access)
    python voice_transcriber.py --use-pipecat
    python voice_transcriber.py --use-pipecat --output transcription.txt
"""

import argparse
import asyncio
import os
import sys
import time
import wave
import tempfile
import threading
import signal
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    import pyaudio
except ImportError:
    print("[ERROR] pyaudio not installed. Install with: pip install pyaudio")
    print("On macOS, you may need: brew install portaudio && pip install pyaudio")
    sys.exit(1)

try:
    from google import genai
    from google.genai import types
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    GOOGLE_GENAI_AVAILABLE = False

# Try to import Pipecat (optional)
PIPECAT_AVAILABLE = False
try:
    from pipecat.frames.frames import (
        Frame,
        TranscriptionFrame,
        TextFrame,
        AudioRawFrame,
        EndFrame,
    )
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
    from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService
    from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
    PIPECAT_AVAILABLE = True
except ImportError:
    pass


# =============================================================================
# Google Gemini Chunked Transcriber (Default)
# =============================================================================

class VoiceTranscriber:
    """Records microphone audio and transcribes in near real-time using Gemini."""
    
    def __init__(
        self,
        output_file: str = None,
        duration: int = None,
        chunk_seconds: int = 5,
        sample_rate: int = 16000,
        channels: int = 1,
    ):
        self.output_file = output_file
        self.duration = duration
        self.chunk_seconds = chunk_seconds
        self.sample_rate = sample_rate
        self.channels = channels
        
        self.running = False
        self.start_time = None
        self.transcriptions = []
        
        # PyAudio setup
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.audio_buffer = []
        
        # Gemini client setup
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("No API key found. Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable.")
        
        self.client = genai.Client(api_key=api_key)
        
        # Initialize output file
        if output_file:
            with open(output_file, 'w') as f:
                f.write(f"Voice Transcription - {datetime.now().isoformat()}\n")
                f.write("=" * 60 + "\n\n")
    
    def _record_audio(self):
        """Background thread that records audio."""
        chunk_size = 1024
        
        self.stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=chunk_size
        )
        
        frames_per_chunk = int(self.sample_rate * self.chunk_seconds / chunk_size)
        current_chunk = []
        frame_count = 0
        
        while self.running:
            try:
                data = self.stream.read(chunk_size, exception_on_overflow=False)
                current_chunk.append(data)
                frame_count += 1
                
                # Check if we have enough frames for a chunk
                if frame_count >= frames_per_chunk:
                    # Send chunk for transcription
                    self.audio_buffer.append(b''.join(current_chunk))
                    current_chunk = []
                    frame_count = 0
                
                # Check duration limit
                if self.duration and (time.time() - self.start_time) >= self.duration:
                    # Send any remaining audio
                    if current_chunk:
                        self.audio_buffer.append(b''.join(current_chunk))
                    self.running = False
                    break
                    
            except Exception as e:
                print(f"[ERROR] Recording error: {e}")
                self.running = False
                break
        
        # Clean up
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
    
    def _save_wav(self, audio_data: bytes, filepath: str):
        """Save audio data to WAV file."""
        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit audio = 2 bytes
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data)
    
    def _transcribe_chunk(self, audio_data: bytes) -> str:
        """Transcribe an audio chunk using Gemini."""
        try:
            # Save to temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp_path = tmp.name
                self._save_wav(audio_data, tmp_path)
            
            # Upload and transcribe
            audio_file = self.client.files.upload(file=tmp_path)
            
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=types.Content(
                    parts=[
                        types.Part.from_uri(
                            file_uri=audio_file.uri,
                            mime_type='audio/x-wav'
                        ),
                        types.Part(text="Transcribe this audio accurately. Only provide the transcription, no commentary.")
                    ]
                )
            )
            
            # Clean up
            self.client.files.delete(name=audio_file.name)
            os.remove(tmp_path)
            
            return response.text.strip() if response.text else ""
            
        except Exception as e:
            print(f"[ERROR] Transcription failed: {e}")
            return ""
    
    def _transcription_worker(self):
        """Background thread that processes audio chunks for transcription."""
        while self.running or self.audio_buffer:
            if self.audio_buffer:
                audio_data = self.audio_buffer.pop(0)
                
                # Transcribe
                text = self._transcribe_chunk(audio_data)
                
                if text:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"[{timestamp}] 🎤 {text}")
                    
                    self.transcriptions.append({
                        "timestamp": timestamp,
                        "text": text
                    })
                    
                    if self.output_file:
                        with open(self.output_file, 'a') as f:
                            f.write(f"[{timestamp}] {text}\n")
            else:
                time.sleep(0.1)
    
    def start(self):
        """Start recording and transcribing."""
        print("=" * 60)
        print("REAL-TIME VOICE TRANSCRIBER (Google Gemini)")
        print("=" * 60)
        print(f"Output file: {self.output_file or 'Console only'}")
        print(f"Duration: {self.duration or 'Until Ctrl+C'} seconds")
        print(f"Chunk size: {self.chunk_seconds} seconds")
        print("=" * 60)
        print("\n🎤 Speak into your microphone. Press Ctrl+C to stop.\n")
        
        self.running = True
        self.start_time = time.time()
        
        # Start recording thread
        record_thread = threading.Thread(target=self._record_audio, daemon=True)
        record_thread.start()
        
        # Start transcription thread
        transcribe_thread = threading.Thread(target=self._transcription_worker, daemon=True)
        transcribe_thread.start()
        
        # Wait for recording to finish
        try:
            while self.running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n[INFO] Stopping...")
            self.stop()
        
        # Wait for transcription to finish processing remaining chunks
        while self.audio_buffer:
            time.sleep(0.5)
        
        record_thread.join(timeout=2)
        transcribe_thread.join(timeout=5)
        
        self._print_summary()
    
    def stop(self):
        """Stop recording."""
        self.running = False
    
    def _print_summary(self):
        """Print transcription summary."""
        print("\n" + "=" * 60)
        print("TRANSCRIPTION COMPLETE")
        print("=" * 60)
        
        if self.transcriptions:
            print(f"\nTotal chunks transcribed: {len(self.transcriptions)}")
            print(f"Duration: {time.time() - self.start_time:.1f} seconds")
            
            full_text = " ".join([t["text"] for t in self.transcriptions])
            print(f"\nFull transcription:\n{full_text}")
        else:
            print("\nNo transcriptions captured.")
        
        if self.output_file:
            print(f"\nTranscription saved to: {self.output_file}")
    
    def __del__(self):
        """Cleanup."""
        if hasattr(self, 'audio'):
            self.audio.terminate()


# =============================================================================
# Pipecat Transcriber (Optional - requires Gemini Live API access)
# =============================================================================

class PipecatTranscriptionLogger(FrameProcessor):
    """Processor that logs transcription frames to console and optionally to file."""
    
    def __init__(self, output_file: str = None):
        super().__init__()
        self.output_file = output_file
        self.transcriptions = []
        
        if output_file:
            # Initialize output file with header
            with open(output_file, 'w') as f:
                f.write(f"Voice Transcription (Pipecat) - {datetime.now().isoformat()}\n")
                f.write("=" * 60 + "\n\n")
    
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        
        if isinstance(frame, TranscriptionFrame):
            # Handle transcription frames from Gemini Live
            text = frame.text
            if text and text.strip():
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] 🎤 {text}")
                
                self.transcriptions.append({
                    "timestamp": timestamp,
                    "text": text
                })
                
                if self.output_file:
                    with open(self.output_file, 'a') as f:
                        f.write(f"[{timestamp}] {text}\n")
        
        elif isinstance(frame, TextFrame):
            # Handle text responses from Gemini
            text = frame.text
            if text and text.strip():
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] 💬 AI: {text}")
                
                if self.output_file:
                    with open(self.output_file, 'a') as f:
                        f.write(f"[{timestamp}] AI: {text}\n")
        
        await self.push_frame(frame, direction)
    
    def get_full_transcription(self) -> str:
        """Get all transcriptions as a single string."""
        return "\n".join([t["text"] for t in self.transcriptions])


async def run_pipecat_transcriber(output_file: str = None, duration: int = None):
    """Run the voice transcription pipeline using Pipecat."""
    
    if not PIPECAT_AVAILABLE:
        print("[ERROR] Pipecat not installed. Install with: pip install 'pipecat-ai[google]'")
        return
    
    # Get API key
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] No API key found. Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable.")
        return
    
    print("=" * 60)
    print("REAL-TIME VOICE TRANSCRIBER (Pipecat + Gemini Live)")
    print("=" * 60)
    print(f"Output file: {output_file or 'Console only'}")
    print(f"Duration: {duration or 'Until Ctrl+C'} seconds")
    print("=" * 60)
    print("\n🎤 Speak into your microphone. Press Ctrl+C to stop.\n")
    print("[NOTE] Pipecat mode requires Gemini Live API access.")
    print("[NOTE] If you get model errors, use default mode (without --use-pipecat)\n")
    
    # Create the Gemini Live service
    # Note: Gemini Live requires specific models that support bidiGenerateContent
    gemini_live = GeminiLiveLLMService(
        api_key=api_key,
        model="gemini-2.0-flash-live",  # Requires Gemini Live API access
        system_instruction="You are a transcription assistant. Listen to the audio and provide accurate transcriptions. Only transcribe what you hear, don't add commentary.",
    )
    
    # Create transcription logger
    transcription_logger = PipecatTranscriptionLogger(output_file=output_file)
    
    # Create local audio transport for microphone input
    transport_params = LocalAudioTransportParams(
        audio_in_enabled=True,
        audio_out_enabled=False,  # We don't need audio output
    )
    transport = LocalAudioTransport(transport_params)
    
    # Build the pipeline
    pipeline = Pipeline([
        transport.input(),      # Microphone input
        gemini_live,            # Gemini Live for transcription
        transcription_logger,   # Log transcriptions
    ])
    
    # Create and run the task
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=False,
        )
    )
    
    runner = PipelineRunner()
    
    try:
        if duration:
            # Run for specified duration
            await asyncio.wait_for(runner.run(task), timeout=duration)
        else:
            # Run until interrupted
            await runner.run(task)
    except asyncio.TimeoutError:
        print(f"\n[INFO] Duration of {duration}s reached.")
    except KeyboardInterrupt:
        print("\n[INFO] Stopping transcription...")
    finally:
        await task.cancel()
        
        # Print summary
        print("\n" + "=" * 60)
        print("TRANSCRIPTION COMPLETE")
        print("=" * 60)
        
        full_text = transcription_logger.get_full_transcription()
        if full_text:
            print(f"\nFull transcription:\n{full_text}")
        
        if output_file:
            print(f"\nTranscription saved to: {output_file}")


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Real-time voice transcription using Google Gemini",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default mode (chunked transcription with Gemini API)
  python voice_transcriber.py
  python voice_transcriber.py --output transcript.txt --duration 60
  python voice_transcriber.py --chunk-seconds 3  # Faster feedback
  
  # Pipecat mode (requires Gemini Live API access)
  python voice_transcriber.py --use-pipecat
  python voice_transcriber.py --use-pipecat --output transcript.txt
        """
    )
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Output file for transcription (optional)")
    parser.add_argument("--duration", "-d", type=int, default=None,
                        help="Recording duration in seconds (optional, default: until Ctrl+C)")
    parser.add_argument("--chunk-seconds", "-c", type=int, default=5,
                        help="Seconds of audio per transcription chunk (default: 5, only for default mode)")
    parser.add_argument("--use-pipecat", action="store_true",
                        help="Use Pipecat + Gemini Live for real-time streaming (requires special API access)")
    
    args = parser.parse_args()
    
    # Handle signals
    def signal_handler(sig, frame):
        print("\n[INFO] Signal received, stopping...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        if args.use_pipecat:
            # Pipecat mode
            if not PIPECAT_AVAILABLE:
                print("[ERROR] Pipecat not installed. Install with: pip install 'pipecat-ai[google]'")
                sys.exit(1)
            asyncio.run(run_pipecat_transcriber(
                output_file=args.output,
                duration=args.duration
            ))
        else:
            # Default: Google Gemini chunked mode
            if not GOOGLE_GENAI_AVAILABLE:
                print("[ERROR] google-genai not installed. Install with: pip install google-genai")
                sys.exit(1)
            transcriber = VoiceTranscriber(
                output_file=args.output,
                duration=args.duration,
                chunk_seconds=args.chunk_seconds,
            )
            transcriber.start()
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
