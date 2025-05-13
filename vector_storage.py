# vector_storage.py

import os
import json
import logging
import numpy as np
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
import chromadb
from chromadb.utils import embedding_functions
import uuid

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('vector_storage')

# Constants
DB_DIRECTORY = "vector_db"
COLLECTION_NAME = "nba_clips_v2"
os.makedirs(DB_DIRECTORY, exist_ok=True)

# Initialize Chroma client
def init_chroma_client():
    """Initialize ChromaDB client"""
    try:
        client = chromadb.PersistentClient(path=DB_DIRECTORY)
        logger.info(f"Initialized ChromaDB client at {DB_DIRECTORY}")
        return client
    except Exception as e:
        logger.error(f"Error initializing ChromaDB client: {str(e)}")
        return None

## Alternative approach using ChromaDB's embedding functions directly
def init_embedding_function():
    """Initialize embedding function using ChromaDB's built-in providers"""
    try:
        # Use ChromaDB's built-in sentence-transformers implementation
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        logger.info("Using ChromaDB's SentenceTransformerEmbeddingFunction")
        return ef
    except Exception as e:
        logger.error(f"Error initializing embedding function: {str(e)}")
        # Fall back to default embedding function
        ef = embedding_functions.DefaultEmbeddingFunction()
        logger.info("Falling back to default embedding function due to error")
        return ef
    
def get_collection(client, embedding_function):
    """Get or create ChromaDB collection"""
    try:
        # Try to get existing collection
        try:
            collection = client.get_collection(
                name=COLLECTION_NAME,
                embedding_function=embedding_function
            )
            logger.info(f"Retrieved existing collection: {COLLECTION_NAME}")
        except Exception:
            # Create new collection if it doesn't exist
            collection = client.create_collection(
                name=COLLECTION_NAME,
                embedding_function=embedding_function
            )
            logger.info(f"Created new collection: {COLLECTION_NAME}")
        
        return collection
    except Exception as e:
        logger.error(f"Error getting/creating collection: {str(e)}")
        return None

class VectorStorage:
    """Class for managing NBA clip vector storage"""
    
    def __init__(self):
        """Initialize vector storage"""
        self.client = init_chroma_client()
        self.embedding_function = init_embedding_function()
        self.collection = get_collection(self.client, self.embedding_function)
        
        if not self.client or not self.embedding_function or not self.collection:
            logger.error("Failed to initialize vector storage components")
            raise RuntimeError("Vector storage initialization failed")
    
    def prepare_clip_data(self, processed_data: Dict) -> Dict:
        """
        Prepare clip data for vector storage
        
        Args:
            processed_data: Processed clip data from clip_processor
            
        Returns:
            Dictionary with prepared data
        """
        try:
            clip_id = processed_data.get("clip_id")
            
            # Extract the full transcript
            transcript = processed_data.get("transcript", "")
            
            # Extract segments
            segments = processed_data.get("segments", [])
            
            # Extract players mentioned
            players = processed_data.get("players_mentioned", [])
            
            # Extract key events
            events = processed_data.get("key_events", [])
            
            # Create segment texts with timestamps
            segment_texts = []
            for segment in segments:
                start = segment.get("start_time", 0)
                end = segment.get("end_time", 0)
                text = segment.get("text", "")
                segment_texts.append(f"[{start:.1f}-{end:.1f}] {text}")
            
            # Create event texts with timestamps
            event_texts = []
            for event in events:
                time = event.get("time", 0)
                description = event.get("event", "")
                event_texts.append(f"[{time:.1f}] {description}")
            
            # Create a rich text for embedding
            rich_text = f"""
            Transcript: {transcript}
            
            Players: {', '.join(players)}
            
            Segments:
            {' '.join(segment_texts)}
            
            Key Events:
            {' '.join(event_texts)}
            """
            
            # Metadata to store with the embedding
            metadata = {
                "clip_id": str(clip_id),
                "title": str(processed_data.get("original_metadata", {}).get("title", f"Clip {clip_id}")),
                "source": str(processed_data.get("original_metadata", {}).get("source", "unknown")),
                "duration": str(processed_data.get("duration", 0)),
                "players": str(json.dumps(players)),
                "processed_at": str(processed_data.get("processed_at", datetime.now().isoformat()))
            }
            
            # Documents to be indexed: full transcript, segments, and events
            documents = [
                rich_text,
                transcript,
                *segment_texts,
                *event_texts
            ]
            
            return {
                "id": clip_id,
                "rich_text": rich_text,
                "documents": documents,
                "metadata": metadata,
                "processed_data": processed_data
            }
            
        except Exception as e:
            logger.error(f"Error preparing clip data: {str(e)}")
            return {"error": str(e)}
    
    def add_clip(self, processed_data: Dict) -> bool:
        """
        Add a processed clip to the vector database
        
        Args:
            processed_data: Processed clip data from clip_processor
            
        Returns:
            Success status
        """
        try:
            clip_id = processed_data.get("clip_id")
            if not clip_id:
                logger.error("No clip_id found in processed data")
                return False
            
            # Prepare data for storage
            prepared_data = self.prepare_clip_data(processed_data)
            if "error" in prepared_data:
                return False
            
            # Check if clip already exists
            try:
                existing = self.collection.get(ids=[clip_id])
                if existing and existing['ids']:
                    # Delete existing to update
                    self.collection.delete(ids=[clip_id])
                    logger.info(f"Removed existing clip {clip_id} for update")
            except Exception:
                # Clip doesn't exist, continue
                pass
            
            # Add the main clip document with rich text
            self.collection.add(
                ids=[clip_id],
                documents=[prepared_data["rich_text"]],
                metadatas=[prepared_data["metadata"]]
            )
            
            # Add individual segments and events with compound IDs
            # This allows for more granular retrieval
            for i, doc in enumerate(prepared_data["documents"][1:]):  # Skip the rich text
                doc_id = f"{clip_id}_doc_{i}"
                self.collection.add(
                    ids=[doc_id],
                    documents=[doc],
                    metadatas=[{
                        **prepared_data["metadata"],
                        "parent_clip_id": clip_id,
                        "doc_type": "segment" if i < len(prepared_data["processed_data"].get("segments", [])) + 1 else "event"
                    }]
                )
            
            logger.info(f"Added clip {clip_id} to vector database")
            return True
            
        except Exception as e:
            logger.error(f"Error adding clip to vector database: {str(e)}")
            return False
    
    def add_clips_batch(self, processed_data_list: List[Dict]) -> Dict:
        """
        Add multiple processed clips to the vector database
        
        Args:
            processed_data_list: List of processed clip data
            
        Returns:
            Dictionary with success and failure counts
        """
        results = {"success": 0, "failed": 0, "failed_ids": []}
        
        for processed_data in processed_data_list:
            clip_id = processed_data.get("clip_id", "unknown")
            success = self.add_clip(processed_data)
            
            if success:
                results["success"] += 1
            else:
                results["failed"] += 1
                results["failed_ids"].append(clip_id)
        
        logger.info(f"Batch add: {results['success']} succeeded, {results['failed']} failed")
        return results
    
    def search_clips(self, query: str, n_results: int = 5, 
                    filter_metadata: Dict = None) -> List[Dict]:
        """
        Search for clips based on query text
        
        Args:
            query: Search query
            n_results: Maximum number of results to return
            filter_metadata: Optional metadata filters
            
        Returns:
            List of matching clips with similarity scores
        """
        try:
            # Execute the query
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=filter_metadata
            )
            
            # Process results
            processed_results = []
            
            if results and results['ids'] and results['ids'][0]:
                for i, clip_id in enumerate(results['ids'][0]):
                    # Skip segment/event documents, only include main clips
                    if "_doc_" in clip_id:
                        continue
                        
                    metadata = results['metadatas'][0][i]
                    distance = results['distances'][0][i] if 'distances' in results else 0
                    
                    # Convert distance to similarity score (1.0 is perfect match)
                    similarity = 1.0 - min(distance, 1.0) if distance is not None else 0
                    
                    processed_results.append({
                        "clip_id": clip_id,
                        "title": metadata.get("title", f"Clip {clip_id}"),
                        "similarity": similarity,
                        "metadata": metadata
                    })
            
            logger.info(f"Search for '{query}' returned {len(processed_results)} results")
            return processed_results
            
        except Exception as e:
            logger.error(f"Error searching clips: {str(e)}")
            return []
    
    def get_clip_details(self, clip_id: str) -> Optional[Dict]:
        """
        Get detailed information for a specific clip
        
        Args:
            clip_id: Clip ID
            
        Returns:
            Dictionary with clip details or None if not found
        """
        try:
            # Get the clip from the collection
            result = self.collection.get(ids=[clip_id])
            
            if not result or not result['ids']:
                logger.warning(f"Clip {clip_id} not found in vector database")
                return None
            
            # Get metadata
            metadata = result['metadatas'][0]
            
            # Get all segments and events for this clip
            related_docs = self.collection.get(
                where={"parent_clip_id": clip_id}
            )
            
            segments = []
            events = []
            
            if related_docs and related_docs['ids']:
                for i, doc_id in enumerate(related_docs['ids']):
                    doc_metadata = related_docs['metadatas'][i]
                    doc_text = related_docs['documents'][i]
                    
                    doc_type = doc_metadata.get("doc_type", "")
                    
                    if doc_type == "segment":
                        # Parse timestamps from text like "[10.5-15.2] Player passes the ball"
                        if doc_text.startswith("[") and "]" in doc_text:
                            time_part = doc_text[1:doc_text.index("]")]
                            text_part = doc_text[doc_text.index("]")+1:].strip()
                            
                            if "-" in time_part:
                                start, end = time_part.split("-")
                                segments.append({
                                    "start_time": float(start),
                                    "end_time": float(end),
                                    "text": text_part
                                })
                    elif doc_type == "event":
                        # Parse timestamps from text like "[12.5] Shot made"
                        if doc_text.startswith("[") and "]" in doc_text:
                            time_part = doc_text[1:doc_text.index("]")]
                            text_part = doc_text[doc_text.index("]")+1:].strip()
                            
                            events.append({
                                "time": float(time_part),
                                "event": text_part
                            })
            
            # Deserialize players list
            players = []
            if metadata.get("players"):
                try:
                    players = json.loads(metadata.get("players", "[]"))
                except json.JSONDecodeError:
                    pass
            
            # Construct result
            clip_details = {
                "clip_id": clip_id,
                "title": metadata.get("title", f"Clip {clip_id}"),
                "source": metadata.get("source", "unknown"),
                "duration": metadata.get("duration", 0),
                "players": players,
                "processed_at": metadata.get("processed_at", ""),
                "transcript": result['documents'][0],
                "segments": segments,
                "key_events": events
            }
            
            logger.info(f"Retrieved details for clip {clip_id}")
            return clip_details
            
        except Exception as e:
            logger.error(f"Error getting clip details: {str(e)}")
            return None
    
    def delete_clip(self, clip_id: str) -> bool:
        """
        Delete a clip from the vector database
        
        Args:
            clip_id: Clip ID
            
        Returns:
            Success status
        """
        try:
            # Delete the main clip
            self.collection.delete(ids=[clip_id])
            
            # Delete all related segments and events
            try:
                related_docs = self.collection.get(
                    where={"parent_clip_id": clip_id}
                )
                
                if related_docs and related_docs['ids']:
                    self.collection.delete(ids=related_docs['ids'])
            except Exception as e:
                logger.warning(f"Error deleting related documents: {str(e)}")
            
            logger.info(f"Deleted clip {clip_id} from vector database")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting clip: {str(e)}")
            return False
    
    def get_all_clips(self, limit: int = 100) -> List[Dict]:
        """
        Get all clips in the database
        
        Args:
            limit: Maximum number of clips to return
            
        Returns:
            List of clips
        """
        try:
            # Get all documents, but filter out segments and events
            all_docs = self.collection.get()
            
            clips = []
            included_ids = set()
            
            if all_docs and all_docs['ids']:
                for i, doc_id in enumerate(all_docs['ids']):
                    # Skip segment/event documents, only include main clips
                    if "_doc_" in doc_id or doc_id in included_ids:
                        continue
                        
                    metadata = all_docs['metadatas'][i]
                    
                    clips.append({
                        "clip_id": doc_id,
                        "title": metadata.get("title", f"Clip {doc_id}"),
                        "source": metadata.get("source", "unknown"),
                        "duration": metadata.get("duration", 0),
                        "processed_at": metadata.get("processed_at", "")
                    })
                    
                    included_ids.add(doc_id)
                    
                    if len(clips) >= limit:
                        break
            
            logger.info(f"Retrieved {len(clips)} clips from vector database")
            return clips
            
        except Exception as e:
            logger.error(f"Error getting all clips: {str(e)}")
            return []


# Initialize vector storage
def create_vector_storage() -> Optional[VectorStorage]:
    """Create and initialize vector storage"""
    try:
        storage = VectorStorage()
        return storage
    except Exception as e:
        logger.error(f"Error creating vector storage: {str(e)}")
        return None


# Command-line interface
if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="NBA Clip Vector Storage Tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Add a clip command
    add_parser = subparsers.add_parser("add", help="Add a processed clip to vector storage")
    add_parser.add_argument("processed_file", help="Path to processed clip JSON file")
    
    # Search clips command
    search_parser = subparsers.add_parser("search", help="Search for clips")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", type=int, default=5, help="Maximum number of results")
    
    # Get clip details command
    get_parser = subparsers.add_parser("get", help="Get clip details")
    get_parser.add_argument("clip_id", help="Clip ID")
    
    # List all clips command
    list_parser = subparsers.add_parser("list", help="List all clips")
    list_parser.add_argument("--limit", type=int, default=100, help="Maximum number of clips to list")
    
    # Delete clip command
    delete_parser = subparsers.add_parser("delete", help="Delete a clip")
    delete_parser.add_argument("clip_id", help="Clip ID")
    
    args = parser.parse_args()
    
    # Create vector storage
    storage = create_vector_storage()
    if not storage:
        print("Failed to initialize vector storage")
        sys.exit(1)
    
    if args.command == "add":
        # Load processed clip data
        try:
            with open(args.processed_file, 'r') as f:
                processed_data = json.load(f)
                
            success = storage.add_clip(processed_data)
            
            if success:
                print(f"Successfully added clip {processed_data.get('clip_id')} to vector storage")
            else:
                print(f"Failed to add clip {processed_data.get('clip_id')} to vector storage")
                sys.exit(1)
                
        except Exception as e:
            print(f"Error: {str(e)}")
            sys.exit(1)
            
    elif args.command == "search":
        results = storage.search_clips(args.query, args.limit)
        
        if not results:
            print("No matching clips found")
        else:
            print(f"Found {len(results)} matching clips:")
            for i, result in enumerate(results):
                print(f"{i+1}. {result['title']} (Score: {result['similarity']:.2f})")
                print(f"   Clip ID: {result['clip_id']}")
                print(f"   Source: {result['metadata'].get('source', 'unknown')}")
                print()
                
    elif args.command == "get":
        details = storage.get_clip_details(args.clip_id)
        
        if not details:
            print(f"Clip {args.clip_id} not found")
            sys.exit(1)
        else:
            print(f"Clip: {details['title']} (ID: {details['clip_id']})")
            print(f"Source: {details['source']}")
            print(f"Duration: {details['duration']} seconds")
            print(f"Players: {', '.join(details['players'])}")
            print(f"Processed: {details['processed_at']}")
            print("\nTranscript:")
            print(details['transcript'])
            print("\nSegments:")
            for segment in details['segments']:
                print(f"[{segment['start_time']:.1f}-{segment['end_time']:.1f}] {segment['text']}")
            print("\nKey Events:")
            for event in details['key_events']:
                print(f"[{event['time']:.1f}] {event['event']}")
                
    elif args.command == "list":
        clips = storage.get_all_clips(args.limit)
        
        if not clips:
            print("No clips found in vector storage")
        else:
            print(f"Found {len(clips)} clips:")
            for i, clip in enumerate(clips):
                print(f"{i+1}. {clip['title']} (ID: {clip['clip_id']})")
                print(f"   Source: {clip['source']}")
                print(f"   Duration: {clip['duration']} seconds")
                print(f"   Processed: {clip['processed_at']}")
                print()
                
    elif args.command == "delete":
        success = storage.delete_clip(args.clip_id)
        
        if success:
            print(f"Successfully deleted clip {args.clip_id}")
        else:
            print(f"Failed to delete clip {args.clip_id}")
            sys.exit(1)
            
    else:
        parser.print_help()