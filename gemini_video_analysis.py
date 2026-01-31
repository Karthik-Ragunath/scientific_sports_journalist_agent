from google import genai
from google.genai import types
from dotenv import load_dotenv
import argparse

parser = argparse.ArgumentParser(description='Analyze a video with Gemini 3')
parser.add_argument('--video-url', type=str, required=False, help='The URL of the video to analyze', default='https://www.youtube.com/watch?v=hKdl0zuqXvw')
parser.add_argument('--prompt', type=str, required=False, help='The prompt to analyze the video', default='Analyze this video with maximum detail.')
args = parser.parse_args()

load_dotenv()

# Use v1alpha for the latest Gemini 3 features
# Set a longer timeout (5 minutes) for video analysis
client = genai.Client(http_options={
    'api_version': 'v1alpha',
    'timeout': 600_000,  # 10 minutes in milliseconds
})

print("Analyzing video... this may take a few minutes.")

response = client.models.generate_content(
    model='gemini-3-pro-preview',
    contents=[
        types.Content(
            parts=[
                # Video part
                types.Part.from_uri(
                    file_uri=args.video_url,
                    mime_type='video/mp4',
                ),
                types.Part(text=args.prompt)
            ]
        )
    ],
    config=types.GenerateContentConfig(
        # Global resolution fallback
        media_resolution='media_resolution_high', 
        # Enable thinking/reasoning mode
        thinking_config=types.ThinkingConfig(
            includeThoughts=True
        ),
        # Deterministic performance
        temperature=0.0 
    )
)

# Print the response
print("\n" + "="*50)
print("RESPONSE:")
print("="*50)

# Check if response has thinking/thoughts
if hasattr(response, 'candidates') and response.candidates:
    for candidate in response.candidates:
        if hasattr(candidate, 'content') and candidate.content:
            for part in candidate.content.parts:
                if hasattr(part, 'thought') and part.thought:
                    print("\n[THINKING]")
                    print(part.text)
                elif hasattr(part, 'text') and part.text:
                    print("\n[RESPONSE]")
                    print(part.text)
else:
    # Fallback to simple text output
    print(response.text)
    
# pip install google-genai python-dotenv