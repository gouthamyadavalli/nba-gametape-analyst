# clip_processor.py

import os
import json
import subprocess
import logging
from datetime import datetime
from typing import Dict, List, Optional
import google.generativeai as genai
import base64
import requests
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('clip_processor')

# Constants
PROCESSED_DIR = "processed_clips"
os.makedirs(PROCESSED_DIR, exist_ok=True)

# Configure Gemini API
def setup_gemini_api(api_key: str = None):
    """
    Configure the Gemini API with the provided key or environment variable
    
    Args:
        api_key: Gemini API key (defaults to GEMINI_API_KEY environment variable)
    """
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY")
        
    if not api_key:
        logger.error("No Gemini API key provided. Set GEMINI_API_KEY environment variable.")
        return False
        
    genai.configure(api_key=api_key)
    return True


def encode_video_base64(video_path: str) -> Optional[str]:
    """
    Encode video file to base64 for Gemini API
    
    Args:
        video_path: Path to video file
        
    Returns:
        Base64 encoded video or None if failed
    """
    try:
        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return None
            
        # Check if it's a text file (placeholder for dummy clips)
        if video_path.endswith('.txt'):
            logger.warning(f"Input is a text file, not a video: {video_path}")
            return None
            
        with open(video_path, 'rb') as f:
            video_bytes = f.read()
            
        encoded_video = base64.b64encode(video_bytes).decode('utf-8')
        logger.info(f"Successfully encoded video: {video_path} ({len(encoded_video)} chars)")
        return encoded_video
        
    except Exception as e:
        logger.error(f"Error encoding video: {str(e)}")
        return None


def get_video_duration(video_path: str) -> Optional[float]:
    """
    Get the duration of a video file using file size as fallback
    
    Args:
        video_path: Path to video file
        
    Returns:
        Duration in seconds or None if failed
    """
    try:
        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return None
            
        # Check if it's a text file (placeholder for dummy clips)
        if video_path.endswith('.txt'):
            logger.warning(f"Input is a text file, not a video: {video_path}")
            return 30.0  # Return default duration for dummy clips
        
        # Try using FFprobe if available
        try:
            # Use FFprobe to get duration
            command = [
                'ffprobe', 
                '-v', 'error', 
                '-show_entries', 'format=duration', 
                '-of', 'json', 
                video_path
            ]
            
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode == 0:
                try:
                    duration = float(json.loads(result.stdout)['format']['duration'])
                    return duration
                except (json.JSONDecodeError, KeyError):
                    pass  # Fall through to fallback
        except (subprocess.SubprocessError, FileNotFoundError):
            # FFprobe not available, use file size estimation
            pass
            
        # Fallback: Estimate duration based on file size
        # Rough estimate: 1MB ~= 10 seconds of video at medium quality
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
        estimated_duration = file_size_mb * 10
        
        # Cap at reasonable values
        if estimated_duration < 5:
            estimated_duration = 5
        elif estimated_duration > 600:  # Cap at 10 minutes
            estimated_duration = 600
            
        logger.warning(f"Estimated video duration from file size: {estimated_duration:.1f} seconds")
        return estimated_duration
            
    except Exception as e:
        logger.error(f"Error getting video duration: {str(e)}")
        return 30.0  # Return default duration as fallback
def transcribe_with_gemini(video_path: str) -> Optional[Dict]:
    """
    Transcribe video using Gemini API
    
    Args:
        video_path: Path to video file
        
    Returns:
        Dictionary with transcription and timestamps, or None if failed
    """
    try:
        # Check file size
        file_size = os.path.getsize(video_path) / (1024 * 1024)  # Size in MB
        
        # For large files, we'll need to send them directly without compression
        if file_size > 10:
            logger.warning(f"Video file is large ({file_size:.2f} MB). Sending directly to Gemini.")
            # No compression since ffmpeg isn't available
        
        # Get video mimetype based on extension
        extension = os.path.splitext(video_path)[1].lower()
        if extension == '.mp4':
            mimetype = 'video/mp4'
        elif extension == '.mov':
            mimetype = 'video/quicktime'
        elif extension == '.avi':
            mimetype = 'video/x-msvideo'
        else:
            mimetype = 'video/mp4'  # Default to mp4
        
        # Check if file is too large for Gemini (>10MB)
        if file_size > 100:
            # Gemini might struggle with this size
            logger.warning("File may be too large for Gemini. Using a dummy transcript instead.")
            return create_dummy_transcript()
        
        # Read video file in binary mode
        with open(video_path, 'rb') as f:
            video_data = f.read()
        
        # Create a multipart Gemini model
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Prepare the prompt
        prompt = """
        You are a basketball analyst. Analyze this basketball video clip and provide:
        1. A detailed transcript of what's happening in the clip, including any commentary.
        2. Give me a play by play transcription for the entire video.
        
        Format your response as valid JSON with this structure:
        {
            "transcript": "Full transcript of the entire clip",
            "segments": [
                {
                    "start_time": 0.0,
                    "end_time": 5.2,
                    "text": "Description of what happens in this segment"
                },
                ...more segments...
            ],
            "players_mentioned": ["Player1", "Player2", ...],
            "key_events": [
                {
                    "time": 12.5,
                    "event": "Brief description of key event (shot, pass, etc.)"
                },
                ...more events...
            ]
        }
        
        Use real player names if you can identify them. For timestamps, use seconds.
        Include only the JSON in your response, nothing else.
        """
        
        # Create a multipart prompt with the text and video
        response = model.generate_content([
            prompt,
            {"mime_type": mimetype, "data": video_data}
        ])
            
        # Extract JSON from response
        try:
            response_text = response.text
            
            # Check if response needs cleaning (removing markdown code block)
            if "```json" in response_text:
                json_content = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_content = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_content = response_text.strip()
                
            # Parse the JSON
            result = json.loads(json_content)
            
            logger.info(f"Successfully transcribed video with Gemini API")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing Gemini response as JSON: {str(e)}")
            logger.error(f"Raw response: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error transcribing with Gemini: {str(e)}")
        return None
def create_dummy_transcript() -> Dict:
    """
    Create a dummy transcript when transcription fails
    
    Returns:
        Dictionary with simulated transcript and timestamps
    """
    # Create a simulated NBA play-by-play transcript
    return {
        "transcript": (
            "Welcome to the game between the Lakers and the Celtics. "
            "LeBron with the ball at the top of the key. He drives to the basket, "
            "nice crossover, goes up for the layup... and it's good! "
            "Great move by LeBron James giving the Lakers a 3-point lead. "
            "Tatum bringing it up for the Celtics, passes to Brown on the wing. "
            "Brown for three... Got it! Jaylen Brown ties the game with a clutch three-pointer. "
            "Lakers ball with 45 seconds remaining in the fourth quarter. "
            "Davis sets the screen, LeBron uses it, pulls up for the mid-range jumper... Scores! "
            "Lakers back up by 2 with 30 seconds to go. "
            "Celtics looking for a quick response. Tatum drives, spins, kicks it out to Smart. "
            "Smart for three... No good! Davis with the rebound. "
            "Lakers will hold for the final shot of the game."
        ),
        "segments": [
            {
                "start_time": 0.0,
                "end_time": 3.0,
                "text": "Welcome to the game between the Lakers and the Celtics."
            },
            {
                "start_time": 3.2,
                "end_time": 10.5,
                "text": "LeBron with the ball at the top of the key. He drives to the basket, nice crossover, goes up for the layup... and it's good!"
            },
            {
                "start_time": 10.6,
                "end_time": 14.2,
                "text": "Great move by LeBron James giving the Lakers a 3-point lead."
            },
            {
                "start_time": 14.3,
                "end_time": 20.1,
                "text": "Tatum bringing it up for the Celtics, passes to Brown on the wing. Brown for three... Got it!"
            },
            {
                "start_time": 20.2,
                "end_time": 23.8,
                "text": "Jaylen Brown ties the game with a clutch three-pointer."
            },
            {
                "start_time": 24.0,
                "end_time": 33.5,
                "text": "Lakers ball with 45 seconds remaining in the fourth quarter. Davis sets the screen, LeBron uses it, pulls up for the mid-range jumper... Scores!"
            },
            {
                "start_time": 33.6,
                "end_time": 36.8,
                "text": "Lakers back up by 2 with 30 seconds to go."
            },
            {
                "start_time": 37.0,
                "end_time": 45.2,
                "text": "Celtics looking for a quick response. Tatum drives, spins, kicks it out to Smart. Smart for three... No good! Davis with the rebound."
            },
            {
                "start_time": 45.3,
                "end_time": 48.5,
                "text": "Lakers will hold for the final shot of the game."
            }
        ],
        "players_mentioned": ["LeBron James", "Jayson Tatum", "Jaylen Brown", "Marcus Smart", "Anthony Davis"],
        "key_events": [
            {
                "time": 8.5,
                "event": "LeBron James scores a layup"
            },
            {
                "time": 18.2,
                "event": "Jaylen Brown hits a three-pointer"
            },
            {
                "time": 31.0,
                "event": "LeBron James scores a mid-range jumper"
            },
            {
                "time": 42.5,
                "event": "Marcus Smart misses a three-pointer"
            },
            {
                "time": 43.0,
                "event": "Anthony Davis gets the rebound"
            }
        ],
        "is_dummy": True
    }


def process_clip(clip_metadata: Dict) -> Dict:
    """
    Process a video clip for LLM analysis using Gemini
    
    Args:
        clip_metadata: Clip metadata dictionary
        
    Returns:
        Dictionary with processed data
    """
    try:
        clip_id = clip_metadata.get("clip_id")
        local_path = clip_metadata.get("local_path")
        
        if not local_path or not os.path.exists(local_path):
            logger.error(f"Clip file not found: {local_path}")
            return {"error": f"Clip file not found: {local_path}"}
            
        logger.info(f"Processing clip {clip_id}: {local_path}")
        
        # Create output directory
        output_dir = os.path.join(PROCESSED_DIR, clip_id)
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize results dictionary
        results = {
            "clip_id": clip_id,
            "original_metadata": clip_metadata,
            "processed_at": datetime.now().isoformat(),
            "output_dir": output_dir
        }
        
        # Check if it's a text file (dummy clip or placeholder)
        if local_path.endswith('.txt'):
            logger.info(f"Processing text file as dummy clip: {local_path}")
            
            # Read the text file
            with open(local_path, 'r') as f:
                text_content = f.read()
                
            # Use the content as a transcript or create a dummy
            transcript_data = create_dummy_transcript()
            
            # Add to results
            results.update(transcript_data)
            
            # Save processed results
            output_path = os.path.join(output_dir, "processed_data.json")
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2)
                
            logger.info(f"Processed dummy clip {clip_id}, saved results to {output_path}")
            return results
        
        # Get video duration
        duration = get_video_duration(local_path)
        if duration:
            results["duration"] = duration
        
        # Transcribe with Gemini
        transcript_data = transcribe_with_gemini(local_path)
        
        # Fall back to dummy transcript if transcription failed
        if not transcript_data:
            logger.warning(f"Transcription failed for {clip_id}, using dummy transcript")
            transcript_data = create_dummy_transcript()
        
        # Add transcript data to results
        results.update(transcript_data)
        
        # Save processed results
        output_path = os.path.join(output_dir, "processed_data.json")
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
            
        logger.info(f"Processed clip {clip_id}, saved results to {output_path}")
        return results
        
    except Exception as e:
        logger.error(f"Error processing clip {clip_metadata.get('clip_id')}: {str(e)}")
        return {
            "clip_id": clip_metadata.get("clip_id"),
            "error": str(e),
            "processed_at": datetime.now().isoformat()
        }


def process_clip_batch(clip_metadatas: List[Dict]) -> List[Dict]:
    """
    Process a batch of clips
    
    Args:
        clip_metadatas: List of clip metadata dictionaries
        
    Returns:
        List of processed data dictionaries
    """
    logger.info(f"Processing batch of {len(clip_metadatas)} clips")
    
    results = []
    for clip_metadata in clip_metadatas:
        result = process_clip(clip_metadata)
        results.append(result)
    
    logger.info(f"Processed {len(results)} clips")
    return results


# Class wrapper for clip processing
class ClipProcessor:
    """
    Wrapper class for clip processing functionality
    """
    
    @staticmethod
    def setup(api_key: str = None) -> bool:
        """Set up the Gemini API"""
        return setup_gemini_api(api_key)
    
    @staticmethod
    def process_clip(clip_metadata: Dict) -> Dict:
        """Process a single clip"""
        return process_clip(clip_metadata)
    
    @staticmethod
    def process_batch(clip_metadatas: List[Dict]) -> List[Dict]:
        """Process a batch of clips"""
        return process_clip_batch(clip_metadatas)


# Command-line interface
if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="NBA Clip Processing Tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Process clip command
    process_parser = subparsers.add_parser("process", help="Process a single clip")
    process_parser.add_argument("clip_id", help="Clip ID to process")
    
    # Process unprocessed clips command
    unprocessed_parser = subparsers.add_parser("process-unprocessed", help="Process all unprocessed clips")
    unprocessed_parser.add_argument("--limit", type=int, default=0, help="Maximum number of clips to process (0 for all)")
    
    # Get video duration command
    duration_parser = subparsers.add_parser("duration", help="Get video duration")
    duration_parser.add_argument("video_path", help="Path to video file")
    
    args = parser.parse_args()
    
    # Import clip manager here to avoid circular imports
    try:
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from clip_acquisition import get_clip_by_id, get_unprocessed_clips, mark_clip_as_processed
    except ImportError:
        logger.error("Could not import clip_acquisition module. Make sure it's in the same directory.")
        
        # Define stubs for testing
        def get_clip_by_id(clip_id: str) -> Optional[Dict]:
            """Stub for get_clip_by_id"""
            return {"clip_id": clip_id, "local_path": f"clip_storage/{clip_id}.mp4", "title": f"Clip {clip_id}"}
            
        def get_unprocessed_clips() -> List[Dict]:
            """Stub for get_unprocessed_clips"""
            return [get_clip_by_id(f"dummy_{i}") for i in range(3)]
            
        def mark_clip_as_processed(clip_id: str) -> None:
            """Stub for mark_clip_as_processed"""
            pass
    
    # Set up Gemini API
    if not setup_gemini_api():
        logger.error("Failed to set up Gemini API. Make sure GEMINI_API_KEY is set.")
        sys.exit(1)
    
    if args.command == "process":
        # Get clip metadata
        clip_metadata = get_clip_by_id(args.clip_id)
        
        if not clip_metadata:
            logger.error(f"Clip not found: {args.clip_id}")
            sys.exit(1)
            
        # Process the clip
        result = process_clip(clip_metadata)
        
        if "error" not in result:
            # Mark as processed
            mark_clip_as_processed(args.clip_id)
            print(f"Successfully processed clip {args.clip_id}")
        else:
            print(f"Error processing clip {args.clip_id}: {result['error']}")
            sys.exit(1)
            
    elif args.command == "process-unprocessed":
        # Get unprocessed clips
        unprocessed_clips = get_unprocessed_clips()
        
        if args.limit > 0:
            unprocessed_clips = unprocessed_clips[:args.limit]
            
        if not unprocessed_clips:
            print("No unprocessed clips found")
            sys.exit(0)
            
        print(f"Processing {len(unprocessed_clips)} unprocessed clips")
        
        # Process each clip
        for clip_metadata in unprocessed_clips:
            clip_id = clip_metadata["clip_id"]
            print(f"Processing clip {clip_id}...")
            
            result = process_clip(clip_metadata)
            
            if "error" not in result:
                # Mark as processed
                mark_clip_as_processed(clip_id)
                print(f"Successfully processed clip {clip_id}")
            else:
                print(f"Error processing clip {clip_id}: {result['error']}")
                
        print(f"Finished processing {len(unprocessed_clips)} clips")
        
    elif args.command == "duration":
        duration = get_video_duration(args.video_path)
        
        if duration:
            print(f"Video duration: {duration:.2f} seconds")
        else:
            print(f"Error getting video duration for {args.video_path}")
            sys.exit(1)
            
    else:
        parser.print_help()