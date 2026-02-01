"""
Video Analyzer Module

Provides video analysis and audio transcription using Gemini AI.
Refactored from gemini_video_analysis.py for API usage.
"""

import os
import asyncio
from typing import Optional, Dict, Any
from pathlib import Path

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()


class VideoAnalyzer:
    """Handles video analysis and audio transcription using Gemini AI."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment")
        
        # Initialize Gemini client with v1alpha for latest features
        self.client = genai.Client(
            api_key=self.api_key,
            http_options={
                'api_version': 'v1alpha',
                'timeout': 600_000,  # 10 minutes for video analysis
            }
        )
        
        print("[VideoAnalyzer] Initialized with Gemini API")
    
    async def transcribe_audio(self, audio_data: bytes, mime_type: str = "audio/webm") -> str:
        """
        Transcribe audio data to text.
        
        Args:
            audio_data: Raw audio bytes
            mime_type: MIME type of the audio (default: audio/webm for browser recording)
        
        Returns:
            Transcribed text
        """
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._transcribe_sync,
                audio_data,
                mime_type
            )
            return result
        except Exception as e:
            print(f"[VideoAnalyzer] Transcription error: {e}")
            raise
    
    def _transcribe_sync(self, audio_data: bytes, mime_type: str) -> str:
        """Synchronous transcription helper."""
        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_bytes(
                            data=audio_data,
                            mime_type=mime_type
                        ),
                        types.Part(text="""Transcribe this audio accurately. 
                        Return ONLY the transcribed text, nothing else.
                        If the audio is unclear, do your best to transcribe what you hear.""")
                    ]
                )
            ]
        )
        
        return response.text.strip()
    
    async def analyze_video(
        self, 
        video_path: str, 
        prompt: str,
        include_thinking: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze a video file with Gemini AI.
        
        Args:
            video_path: Path to the video file
            prompt: Analysis prompt/question
            include_thinking: Whether to include thinking/reasoning in response
        
        Returns:
            Dict with 'response' and optionally 'thinking' keys
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")
        
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._analyze_sync,
                video_path,
                prompt,
                include_thinking
            )
            return result
        except Exception as e:
            print(f"[VideoAnalyzer] Analysis error: {e}")
            raise
    
    def _analyze_sync(
        self, 
        video_path: str, 
        prompt: str, 
        include_thinking: bool
    ) -> Dict[str, Any]:
        """Synchronous video analysis helper."""
        
        # Read video file
        with open(video_path, 'rb') as f:
            video_data = f.read()
        
        # Determine mime type
        ext = Path(video_path).suffix.lower()
        mime_types = {
            '.mp4': 'video/mp4',
            '.webm': 'video/webm',
            '.mov': 'video/quicktime',
            '.avi': 'video/x-msvideo'
        }
        mime_type = mime_types.get(ext, 'video/mp4')
        
        # Configure generation
        config = types.GenerateContentConfig(
            media_resolution='media_resolution_medium',  # HIGH only works for single images, not videos
            temperature=0.3  # Slightly creative but factual
        )
        
        if include_thinking:
            config.thinking_config = types.ThinkingConfig(
                includeThoughts=True
            )
        
        # Make the API call
        response = self.client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_bytes(
                            data=video_data,
                            mime_type=mime_type
                        ),
                        types.Part(text=prompt)
                    ]
                )
            ],
            config=config
        )
        
        # Extract response and thinking
        result = {
            "response": None,
            "thinking": None
        }
        
        if hasattr(response, 'candidates') and response.candidates:
            for candidate in response.candidates:
                if hasattr(candidate, 'content') and candidate.content:
                    for part in candidate.content.parts:
                        if hasattr(part, 'thought') and part.thought:
                            result["thinking"] = part.text
                        elif hasattr(part, 'text') and part.text:
                            if result["response"]:
                                result["response"] += "\n" + part.text
                            else:
                                result["response"] = part.text
        
        # Fallback to simple text
        if not result["response"]:
            result["response"] = response.text
        
        return result
    
    async def analyze_video_with_context(
        self,
        video_path: str,
        user_question: str,
        additional_context: str = None
    ) -> Dict[str, Any]:
        """
        Analyze video with user's spoken question as context.
        
        Args:
            video_path: Path to video file
            user_question: Transcribed user question
            additional_context: Any additional context
        
        Returns:
            Analysis result
        """
        prompt = f"""The viewer asked: "{user_question}"

Please analyze this sports video and directly answer their question.

Additional context: {additional_context or 'None provided'}

Provide your analysis as a sports journalist would, with:
1. Direct answer to the question
2. Supporting observations from the video
3. Expert analysis and insights
4. A memorable quote or tweet about this moment"""
        
        return await self.analyze_video(video_path, prompt)


# For backwards compatibility with CLI usage
def main():
    """CLI entry point for video analysis."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze a video with Gemini AI')
    parser.add_argument('--video-path', type=str, required=True, help='Path to video file')
    parser.add_argument('--prompt', type=str, default='Analyze this video with maximum detail.')
    parser.add_argument('--question', type=str, help='User question about the video')
    args = parser.parse_args()
    
    analyzer = VideoAnalyzer()
    
    async def run():
        if args.question:
            result = await analyzer.analyze_video_with_context(
                args.video_path,
                args.question
            )
        else:
            result = await analyzer.analyze_video(args.video_path, args.prompt)
        
        print("\n" + "=" * 50)
        print("ANALYSIS:")
        print("=" * 50)
        
        if result.get("thinking"):
            print("\n[THINKING]")
            print(result["thinking"])
        
        print("\n[RESPONSE]")
        print(result["response"])
    
    asyncio.run(run())


if __name__ == "__main__":
    main()
