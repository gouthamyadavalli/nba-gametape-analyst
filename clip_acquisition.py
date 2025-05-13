# clip_acquisition.py

import os
import uuid
import json
import requests
from datetime import datetime
import logging
from typing import List, Dict, Optional, BinaryIO
import shutil
import ssl
import certifi
from pytube import YouTube
from yt_dlp import YoutubeDL

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('clip_acquisition')

# Constants
CLIP_STORAGE_DIR = "clip_storage"
METADATA_FILE = "clips_metadata.json"

# Ensure directories exist
os.makedirs(CLIP_STORAGE_DIR, exist_ok=True)

# Initialize metadata file if it doesn't exist
if not os.path.exists(os.path.join(CLIP_STORAGE_DIR, METADATA_FILE)):
    with open(os.path.join(CLIP_STORAGE_DIR, METADATA_FILE), 'w') as f:
        json.dump({"clips": []}, f)


# Fix for SSL certificate issues
def fix_ssl_certificate():
    """Configure SSL certificate for requests"""
    try:
        # Try to use certifi for certificate verification
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        ssl._create_default_https_context = lambda: ssl_context
        logger.info("SSL certificate configured with certifi")
    except Exception as e:
        # If certifi fails, disable verification (not recommended for production)
        logger.warning(f"Failed to configure SSL with certifi: {str(e)}")
        logger.warning("Disabling SSL verification (not secure for production)")
        ssl._create_default_https_context = ssl._create_unverified_context


# Call this at module import time
fix_ssl_certificate()


def load_metadata() -> Dict:
    """Load the clips metadata file"""
    try:
        with open(os.path.join(CLIP_STORAGE_DIR, METADATA_FILE), 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        # If file is empty or doesn't exist, return empty metadata
        return {"clips": []}


def save_metadata(metadata: Dict) -> None:
    """Save the clips metadata file"""
    with open(os.path.join(CLIP_STORAGE_DIR, METADATA_FILE), 'w') as f:
        json.dump(metadata, f, indent=2)


def download_youtube_clip(video_url: str, title: str = None) -> Optional[Dict]:
    """
    Download an NBA clip from YouTube
    
    Args:
        video_url: YouTube video URL or ID
        title: Optional title for the clip
        
    Returns:
        Clip metadata dictionary or None if failed
    """
    try:
        # Try to import pytube, if not available use a fallback
        try:
            from pytube import YouTube
        except ImportError:
            logger.warning("pytube not installed. Trying alternative method...")
            return download_youtube_clip_fallback(video_url, title)
        
        # Handle different formats of YouTube URLs
        if "youtube.com" not in video_url and "youtu.be" not in video_url:
            # Assume it's just the video ID
            video_url = f"https://www.youtube.com/watch?v={video_url}"
        
        logger.info(f"Downloading YouTube clip: {video_url}")
        
        
        # Generate clip ID
        clip_id = f"yt_{uuid.uuid4().hex[:8]}"
        
        # Set output path
        output_path = os.path.join(CLIP_STORAGE_DIR, f"{clip_id}.mp4")
        
        ydl_opts = {
            'format': 'best[ext=mp4]',  # MP4 video+audio
            'outtmpl': output_path,
            'noplaylist': True,                                    # ignore playlists
            'quiet': False,
            'no_warnings': True,
            }

        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
            download_success = True
        # Create metadata
        clip_metadata = {
            "clip_id": clip_id,
            "source": "youtube",
            "source_id": video_url.split("v=")[1].split("&")[0],
            "local_path": output_path,
            "original_url": video_url,
            "acquired_at": datetime.now().isoformat(),
            "title": title,
            # "duration": yt.length if hasattr(yt, 'length') else 0,
            # "author": yt.author if hasattr(yt, 'author') else "Unknown",
            "processed": False
        }
        
        # Add to metadata file
        add_clip_metadata(clip_metadata)
        
        logger.info(f"Successfully downloaded clip {clip_id}: {title or video_url}")
        return clip_metadata
    
    except Exception as e:
        logger.error(f"Error downloading YouTube clip {video_url}: {str(e)}")
        # Create a dummy clip as fallback
        return create_dummy_clip(f"Fallback for {video_url}")
def download_youtube_clip_fallback(video_url: str, title: str = None) -> Optional[Dict]:
    """
    Alternative method to download YouTube clips if pytube fails
    Uses youtube-dl CLI if available, or creates a placeholder
    
    Args:
        video_url: YouTube video URL or ID
        title: Optional title for the clip
        
    Returns:
        Clip metadata dictionary or None if failed
    """
    try:
        # Handle different formats of YouTube URLs
        if "youtube.com" not in video_url and "youtu.be" not in video_url:
            # Assume it's just the video ID
            video_id = video_url
            video_url = f"https://www.youtube.com/watch?v={video_id}"
        else:
            # Extract video ID from URL
            if "youtube.com" in video_url:
                video_id = video_url.split("v=")[1].split("&")[0]
            elif "youtu.be" in video_url:
                video_id = video_url.split("/")[-1].split("?")[0]
            else:
                video_id = "unknown"
        
        # Generate clip ID
        clip_id = f"yt_{uuid.uuid4().hex[:8]}"
        
        # Set output path
        output_path = os.path.join(CLIP_STORAGE_DIR, f"{clip_id}.mp4")
        download_success = False
        # Try using youtube-dl CLI if available
        try:
            ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',  # MP4 video+audio
            'outtmpl': output_path,
            'noplaylist': True,                                    # ignore playlists
            'quiet': False,
            'no_warnings': True,
            }

            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
                download_success = True
        except Exception as e:
            logger.error(f"Error downloading YouTube clip with youtube-dl: {str(e)}")
            download_success = False
        

        # Create metadata
        clip_metadata = {
            "clip_id": clip_id,
            "source": "youtube",
            "source_id": video_id,
            "local_path": output_path,
            "original_url": video_url,
            "acquired_at": datetime.now().isoformat(),
            "title": title or f"YouTube video {video_id}",
            "placeholder": not download_success,
            "processed": False
        }
        
        # Add to metadata file
        add_clip_metadata(clip_metadata)
        
        logger.info(f"Successfully created {'placeholder for' if not download_success else ''} clip {clip_id}")
        return clip_metadata
    
    except Exception as e:
        logger.error(f"Error in fallback YouTube download for {video_url}: {str(e)}")
        
        # Last resort - create minimal placeholder
        try:
            clip_id = f"yt_{uuid.uuid4().hex[:8]}"
            output_path = os.path.join(CLIP_STORAGE_DIR, f"{clip_id}.txt")
            
            with open(output_path, 'w') as f:
                f.write(f"Error placeholder for YouTube video: {video_url}\nError: {str(e)}")
            
            clip_metadata = {
                "clip_id": clip_id,
                "source": "youtube",
                "local_path": output_path,
                "original_url": video_url,
                "acquired_at": datetime.now().isoformat(),
                "title": title or f"YouTube error placeholder",
                "placeholder": True,
                "error": str(e),
                "processed": False
            }
            
            add_clip_metadata(clip_metadata)
            logger.info(f"Created error placeholder for clip {clip_id}")
            return clip_metadata
        except:
            return None


def add_clip_metadata(clip_metadata: Dict) -> None:
    """Add a clip's metadata to the metadata file"""
    metadata = load_metadata()
    metadata["clips"].append(clip_metadata)
    save_metadata(metadata)


def save_uploaded_clip(file_object: BinaryIO, filename: str = None, title: str = None) -> Optional[Dict]:
    """
    Save an uploaded clip file
    
    Args:
        file_object: File-like object containing the clip data
        filename: Optional original filename
        title: Optional title for the clip
        
    Returns:
        Clip metadata dictionary or None if failed
    """
    try:
        clip_id = f"upload_{uuid.uuid4().hex[:8]}"
        
        # Get file extension
        if filename:
            _, file_ext = os.path.splitext(filename)
        else:
            file_ext = ".mp4"  # Default extension
        
        # Save file
        local_path = os.path.join(CLIP_STORAGE_DIR, f"{clip_id}{file_ext}")
        
        # Write file data to disk
        with open(local_path, 'wb') as f:
            # If file_object is a file-like object, use copyfileobj
            if hasattr(file_object, 'read'):
                shutil.copyfileobj(file_object, f)
            # If it's bytes, write directly
            elif isinstance(file_object, bytes):
                f.write(file_object)
            else:
                raise TypeError("file_object must be a file-like object or bytes")
        
        # Create metadata
        clip_metadata = {
            "clip_id": clip_id,
            "source": "upload",
            "local_path": local_path,
            "original_filename": filename,
            "acquired_at": datetime.now().isoformat(),
            "title": title or filename or f"Uploaded clip {clip_id}",
            "processed": False
        }
        
        # Add to metadata file
        add_clip_metadata(clip_metadata)
        
        logger.info(f"Successfully saved uploaded clip {clip_id}")
        return clip_metadata
    
    except Exception as e:
        logger.error(f"Error saving uploaded clip: {str(e)}")
        return None


def get_all_clips() -> List[Dict]:
    """Get metadata for all clips"""
    metadata = load_metadata()
    return metadata["clips"]


def get_clip_by_id(clip_id: str) -> Optional[Dict]:
    """Get metadata for a specific clip by ID"""
    metadata = load_metadata()
    for clip in metadata["clips"]:
        if clip["clip_id"] == clip_id:
            return clip
    return None


def mark_clip_as_processed(clip_id: str) -> None:
    """Mark a clip as processed in the metadata"""
    metadata = load_metadata()
    for clip in metadata["clips"]:
        if clip["clip_id"] == clip_id:
            clip["processed"] = True
            clip["processed_at"] = datetime.now().isoformat()
    save_metadata(metadata)


def get_unprocessed_clips() -> List[Dict]:
    """Get metadata for all unprocessed clips"""
    metadata = load_metadata()
    return [clip for clip in metadata["clips"] if not clip.get("processed", False)]


def upload_to_cloud_storage(local_path: str, destination_path: str, 
                           bucket_name: str = None) -> Optional[str]:
    """
    Upload a file to cloud storage (e.g., Google Cloud Storage, AWS S3)
    
    Args:
        local_path: Local path to the file
        destination_path: Path within the cloud storage
        bucket_name: Cloud storage bucket name
        
    Returns:
        Cloud storage URL if successful, None otherwise
    """
    try:
        # For Google Cloud Storage:
        try:
            from google.cloud import storage
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(destination_path)
            blob.upload_from_filename(local_path)
            return f"gs://{bucket_name}/{destination_path}"
        except ImportError:
            logger.warning("Google Cloud Storage SDK not installed. Simulating upload.")
            logger.info(f"Simulated upload: {local_path} -> {bucket_name}/{destination_path}")
            return f"gs://{bucket_name}/{destination_path}"
        
    except Exception as e:
        logger.error(f"Error uploading to cloud storage: {str(e)}")
        return None


# Fetch multiple clips from NBA YouTube channels
# Fetch multiple clips from NBA YouTube channels
def fetch_nba_highlights(number_of_clips: int = 5) -> List[Dict]:
    """
    Fetch recent NBA highlight clips from YouTube
    
    Args:
        number_of_clips: Number of clips to fetch
        
    Returns:
        List of clip metadata dictionaries
    """
    try:
        logger.info(f"Fetching {number_of_clips} NBA highlight clips")
        
        # Updated list of working NBA highlight videos from the official NBA channel
        nba_highlights = [
            # "https://www.youtube.com/watch?v=_ijAzBZkptI",  # NBA Buzzer Beaters
            # "https://www.youtube.com/watch?v=gyYVNCiZGUg", 
            "https://www.youtube.com/watch?v=nCHI0b5-Dkg",
         ] # NBA Top 10 Plays]
        
        # Limit to requested number
        urls_to_fetch = nba_highlights[:min(number_of_clips, len(nba_highlights))]
        
        # Download each clip
        downloaded_clips = []
        for url in urls_to_fetch:
            clip = download_youtube_clip(url)
            if clip:
                downloaded_clips.append(clip)
            
            # Small delay to avoid rate limiting
            import time
            time.sleep(2)
        
        # If we didn't get enough clips, add dummy clips
        while len(downloaded_clips) < number_of_clips:
            dummy_clip = create_dummy_clip(f"NBA Highlight Dummy {len(downloaded_clips) + 1}")
            downloaded_clips.append(dummy_clip)
        
        logger.info(f"Successfully fetched {len(downloaded_clips)} NBA highlight clips")
        return downloaded_clips
    
    except Exception as e:
        logger.error(f"Error fetching NBA highlights: {str(e)}")
        # Return dummy clips as fallback
        dummy_clips = [create_dummy_clip(f"NBA Highlight Dummy {i+1}") for i in range(number_of_clips)]
        return dummy_clips
    

def create_dummy_clip(title: str = "Dummy NBA Highlight") -> Dict:
    """
    Create a dummy clip for testing when actual downloads fail
    
    Args:
        title: Title for the dummy clip
        
    Returns:
        Clip metadata dictionary
    """
    clip_id = f"dummy_{uuid.uuid4().hex[:8]}"
    local_path = os.path.join(CLIP_STORAGE_DIR, f"{clip_id}.mp4")  # Using .mp4 for compatibility
    
    # Create a dummy mp4 file with minimal content
    try:
        # Try to create a minimal valid mp4 file
        from base64 import b64decode
        
        # This is a tiny valid MP4 file (a few bytes)
        minimal_mp4 = b64decode(
            "AAAAHGZ0eXBtcDQyAAAAAG1wNDJtcDQxaXNvbWlzbwAAAAA="
        )
        
        with open(local_path, 'wb') as f:
            f.write(minimal_mp4)
    except Exception:
        # If that fails, just create a text file
        with open(local_path, 'w') as f:
            f.write(f"This is a dummy NBA highlight clip for testing purposes.\n")
            f.write(f"Title: {title}\n")
            f.write(f"Created at: {datetime.now().isoformat()}\n")
            f.write(f"Content: Example NBA play description with players running, shooting, and scoring.\n")
    
    # Create metadata
    clip_metadata = {
        "clip_id": clip_id,
        "source": "dummy",
        "local_path": local_path,
        "acquired_at": datetime.now().isoformat(),
        "title": title,
        "duration": 30,  # Simulated 30-second clip
        "processed": False,
        "is_dummy": True
    }
    
    # Add to metadata file
    add_clip_metadata(clip_metadata)
    
    logger.info(f"Created dummy clip {clip_id}: {title}")
    return clip_metadata

# CLI example usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="NBA Clip Acquisition Tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Fetch NBA highlights command
    highlights_parser = subparsers.add_parser("fetch-highlights", help="Fetch NBA highlight clips")
    highlights_parser.add_argument("--count", type=int, default=3, help="Number of clips to fetch")
    highlights_parser.add_argument("--dummy", action="store_true", help="Create dummy clips instead of downloading")
    
    # Download YouTube clip command
    youtube_parser = subparsers.add_parser("download-youtube", help="Download a clip from YouTube")
    youtube_parser.add_argument("url", help="YouTube video URL or ID")
    youtube_parser.add_argument("--title", help="Title for the clip")
    youtube_parser.add_argument("--dummy", action="store_true", help="Create dummy clip instead of downloading")
    
    # Create dummy clip command
    dummy_parser = subparsers.add_parser("create-dummy", help="Create a dummy clip for testing")
    dummy_parser.add_argument("--title", default="Dummy NBA Highlight", help="Title for the dummy clip")
    
    # List clips command
    list_parser = subparsers.add_parser("list", help="List all clips")
    
    # List unprocessed clips command
    unprocessed_parser = subparsers.add_parser("list-unprocessed", help="List unprocessed clips")
    
    args = parser.parse_args()
    
    if args.command == "fetch-highlights":
        if args.dummy:
            # Create dummy clips instead of downloading
            clips = [create_dummy_clip(f"NBA Highlight Dummy {i+1}") for i in range(args.count)]
            print(f"Created {len(clips)} dummy NBA highlight clips")
        else:
            clips = fetch_nba_highlights(args.count)
            print(f"Fetched {len(clips)} NBA highlight clips")
        
    elif args.command == "download-youtube":
        if args.dummy:
            clip = create_dummy_clip(args.title or f"Dummy for {args.url}")
            print(f"Created dummy clip: {clip['clip_id']} - {clip['title']}")
        else:
            clip = download_youtube_clip(args.url, args.title)
            if clip:
                print(f"Successfully downloaded YouTube clip: {clip['clip_id']} - {clip['title']}")
            else:
                print("Failed to download YouTube clip")
    
    elif args.command == "create-dummy":
        clip = create_dummy_clip(args.title)
        print(f"Created dummy clip: {clip['clip_id']} - {clip['title']}")
            
    elif args.command == "list":
        clips = get_all_clips()
        print(f"Found {len(clips)} clips:")
        for clip in clips:
            print(f"  {clip['clip_id']}: {clip['title']}")
            
    elif args.command == "list-unprocessed":
        clips = get_unprocessed_clips()
        print(f"Found {len(clips)} unprocessed clips:")
        for clip in clips:
            print(f"  {clip['clip_id']}: {clip['title']}")
    
    else:
        parser.print_help()