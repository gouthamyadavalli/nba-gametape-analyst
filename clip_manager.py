# clip_manager.py

from typing import List, Dict, Optional, BinaryIO
from clip_acquisition import (
    download_youtube_clip, fetch_nba_highlights, save_uploaded_clip,
    get_all_clips, get_clip_by_id, mark_clip_as_processed,
    get_unprocessed_clips, upload_to_cloud_storage
)

class ClipManager:
    """
    A wrapper class for NBA clip acquisition functionality
    """
    
    @staticmethod
    def download_youtube_clip(video_url: str, title: str = None) -> Optional[Dict]:
        """Download an NBA clip from YouTube"""
        return download_youtube_clip(video_url, title)
    
    @staticmethod
    def fetch_nba_highlights(count: int = 5) -> List[Dict]:
        """Fetch recent NBA highlight clips"""
        return fetch_nba_highlights(count)
    
    @staticmethod
    def upload_clip(file_data: BinaryIO, filename: str = None, 
                   title: str = None) -> Optional[Dict]:
        """Upload a clip file"""
        return save_uploaded_clip(file_data, filename, title)
    
    @staticmethod
    def get_all_clips() -> List[Dict]:
        """Get all clips"""
        return get_all_clips()
    
    @staticmethod
    def get_clip(clip_id: str) -> Optional[Dict]:
        """Get a specific clip by ID"""
        return get_clip_by_id(clip_id)
    
    @staticmethod
    def mark_processed(clip_id: str) -> None:
        """Mark a clip as processed"""
        mark_clip_as_processed(clip_id)
    
    @staticmethod
    def get_unprocessed_clips() -> List[Dict]:
        """Get all unprocessed clips"""
        return get_unprocessed_clips()
    
    @staticmethod
    def upload_to_cloud(local_path: str, destination_path: str, 
                        bucket_name: str = "nba-analysis-clips") -> Optional[str]:
        """Upload a file to cloud storage"""
        return upload_to_cloud_storage(local_path, destination_path, bucket_name)