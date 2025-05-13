# nba_analysis_app.py

import streamlit as st
import os
import json
import tempfile
import time
import pandas as pd
from datetime import datetime
import base64
from typing import Dict, List, Optional
import sys
import uuid

# Import our modules
# Add proper paths to ensure imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import our custom modules
try:
    from clip_manager import ClipManager
    from direct_analysis_engine import DirectAnalysisEngine
except ImportError:
    st.error("Cannot import required modules. Make sure clip_acquisition.py and direct_analysis_engine.py are in the same directory.")
    st.stop()

# Constants
TEMP_DIR = "temp_uploads"
ANALYSIS_DIR = "analyses"
CLIP_STORAGE_DIR = "clip_storage"

# Ensure directories exist
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(ANALYSIS_DIR, exist_ok=True)
os.makedirs(CLIP_STORAGE_DIR, exist_ok=True)

# Set page configuration
st.set_page_config(
    page_title="NBA Game Analysis System",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Functions to handle file downloading
def get_binary_file_downloader_html(bin_file, file_label='File'):
    with open(bin_file, 'rb') as f:
        data = f.read()
    bin_str = base64.b64encode(data).decode()
    href = f'<a href="data:application/octet-stream;base64,{bin_str}" download="{os.path.basename(bin_file)}">Download {file_label}</a>'
    return href

def read_analysis_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error reading analysis file: {str(e)}")
        return None

# Initialize session state
if 'analysis_engine' not in st.session_state:
    try:
        st.session_state.analysis_engine = DirectAnalysisEngine()
    except Exception as e:
        st.error(f"Error initializing analysis engine: {str(e)}")
        st.error("Make sure you have set the GEMINI_API_KEY environment variable.")
        st.stop()

if 'clip_manager' not in st.session_state:
    st.session_state.clip_manager = ClipManager()

if 'current_clip_path' not in st.session_state:
    st.session_state.current_clip_path = None
    
if 'current_clip_id' not in st.session_state:
    st.session_state.current_clip_id = None
    
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = {}

# App title and description
st.title("🏀 NBA Game Analysis System")
st.markdown("""
This system uses AI to analyze NBA game clips and provide professional-level insights.
Upload a clip or provide a YouTube link to get started.
""")

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", 
    ["Upload Clips", "Analyze Clips", "View Analysis", "About"])

# 1. UPLOAD CLIPS PAGE
if page == "Upload Clips":
    st.header("Upload Game Clips")
    
    tab1, tab2 = st.tabs(["Upload Video", "YouTube Link"])
    
    # Tab 1: Upload Video
    with tab1:
        uploaded_file = st.file_uploader("Choose a video file", 
                                         type=["mp4", "mov", "avi"])
        
        if uploaded_file:
            # Show video preview
            st.video(uploaded_file)
            
            col1, col2 = st.columns(2)
            with col1:
                video_title = st.text_input("Video Title (optional)", 
                                           value=uploaded_file.name)
            
            if st.button("Process Video"):
                with st.spinner("Processing video..."):
                    # Save to temporary file
                    temp_path = os.path.join(TEMP_DIR, uploaded_file.name)
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # Save to clip storage
                    clip_metadata = st.session_state.clip_manager.upload_clip(
                        uploaded_file.getbuffer(), 
                        uploaded_file.name, 
                        video_title
                    )
                    
                    if clip_metadata:
                        st.session_state.current_clip_path = clip_metadata["local_path"]
                        st.session_state.current_clip_id = clip_metadata["clip_id"]
                        
                        st.success(f"Video processed successfully! Clip ID: {clip_metadata['clip_id']}")
                        st.markdown("Go to the **Analyze Clips** page to generate insights.")
                    else:
                        st.error("Error processing video.")
    
    # Tab 2: YouTube Link
    with tab2:
        youtube_url = st.text_input("YouTube Video URL")
        video_title = st.text_input("Video Title (optional for YouTube)")
        
        if youtube_url:
            if st.button("Fetch from YouTube"):
                with st.spinner("Downloading from YouTube..."):
                    try:
                        # Download from YouTube
                        clip_metadata = st.session_state.clip_manager.download_youtube_clip(
                            youtube_url, 
                            video_title
                        )
                        
                        if clip_metadata:
                            st.session_state.current_clip_path = clip_metadata["local_path"]
                            st.session_state.current_clip_id = clip_metadata["clip_id"]
                            
                            # Display video if available
                            if os.path.exists(clip_metadata["local_path"]):
                                st.video(clip_metadata["local_path"])
                            
                            st.success(f"Video downloaded successfully! Clip ID: {clip_metadata['clip_id']}")
                            st.markdown("Go to the **Analyze Clips** page to generate insights.")
                        else:
                            st.error("Error downloading video from YouTube.")
                            st.info("Try using the 'sample clips' option on the Analyze page instead.")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
                        st.info("Try using the 'sample clips' option on the Analyze page instead.")
    
    # List previously uploaded clips
    st.subheader("Previously Uploaded Clips")
    try:
        clips = st.session_state.clip_manager.get_all_clips()
        
        if clips:
            clip_df = []
            for clip in clips:
                clip_df.append({
                    "Clip ID": clip.get("clip_id", "Unknown"),
                    "Title": clip.get("title", "Untitled"),
                    "Source": clip.get("source", "Unknown"),
                    "Uploaded": clip.get("acquired_at", "Unknown"),
                })
            
            clip_df = pd.DataFrame(clip_df)
            st.dataframe(clip_df)
            
            # Allow selecting a clip
            selected_clip_id = st.selectbox(
                "Select a clip to analyze", 
                options=[clip["Clip ID"] for clip in clips],
                format_func=lambda x: f"{x} - {next((c['Title'] for c in clips if c['Clip ID'] == x), 'Unknown')}"
            )
            
            if st.button("Use Selected Clip"):
                selected_clip = st.session_state.clip_manager.get_clip(selected_clip_id)
                if selected_clip:
                    st.session_state.current_clip_path = selected_clip["local_path"]
                    st.session_state.current_clip_id = selected_clip["clip_id"]
                    st.success(f"Selected clip: {selected_clip['title']}")
                    st.markdown("Go to the **Analyze Clips** page to generate insights.")
        else:
            st.info("No clips uploaded yet.")
    except Exception as e:
        st.error(f"Error loading clips: {str(e)}")

# 2. ANALYZE CLIPS PAGE
elif page == "Analyze Clips":
    st.header("Analyze Game Clips")
    
    # Option to create sample clip if no clip is selected
    if not st.session_state.current_clip_path or not os.path.exists(st.session_state.current_clip_path):
        st.warning("No clip selected or the clip file is missing.")
        
        if st.button("Create Sample Clip"):
            with st.spinner("Creating sample clip..."):
                # Create a dummy clip
                sample_title = "Sample NBA Highlight"
                clip_id = f"sample_{uuid.uuid4().hex[:8]}"
                local_path = os.path.join(CLIP_STORAGE_DIR, f"{clip_id}.txt")
                
                # Create a dummy file with NBA play description
                with open(local_path, 'w') as f:
                    f.write(f"Sample NBA clip: {sample_title}\n\n")
                    f.write("Play-by-play description:\n")
                    f.write("LeBron drives to the basket, crossover on defender, elevates for a powerful dunk!\n")
                    f.write("Defense collapses, LeBron finds an open shooter in the corner for three!\n")
                    f.write("Fast break opportunity, LeBron with a chase-down block on the opposing player!\n")
                
                # Create metadata
                clip_metadata = {
                    "clip_id": clip_id,
                    "source": "sample",
                    "local_path": local_path,
                    "acquired_at": datetime.now().isoformat(),
                    "title": sample_title,
                    "duration": 30,
                    "is_sample": True,
                    "processed": False
                }
                
                # Add to metadata file
                try:
                    st.session_state.clip_manager.upload_clip = lambda *args, **kwargs: clip_metadata
                    st.session_state.current_clip_path = local_path
                    st.session_state.current_clip_id = clip_id
                    st.success(f"Created sample clip: {sample_title}")
                except Exception as e:
                    st.error(f"Error creating sample clip: {str(e)}")
        
        st.markdown("Or go to the **Upload Clips** page to upload a video.")
        st.stop()
    
    # Display information about the current clip
    clip_data = st.session_state.clip_manager.get_clip(st.session_state.current_clip_id)
    
    if clip_data:
        st.subheader(f"Current Clip: {clip_data.get('title', 'Untitled')}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Clip ID:** {clip_data.get('clip_id', 'Unknown')}")
            st.write(f"**Source:** {clip_data.get('source', 'Unknown')}")
        with col2:
            st.write(f"**Uploaded:** {clip_data.get('acquired_at', 'Unknown')}")
            st.write(f"**Duration:** {clip_data.get('duration', 'Unknown')} seconds")
        
        # Display video if available and not a text file
        if os.path.exists(clip_data["local_path"]) and not clip_data["local_path"].endswith(".txt"):
            st.video(clip_data["local_path"])
        elif clip_data["local_path"].endswith(".txt"):
            st.info("This is a sample/placeholder clip. Analysis will use a pre-defined basketball scenario.")
            with open(clip_data["local_path"], 'r') as f:
                st.code(f.read())
    
    # Analysis options
    st.subheader("Analysis Options")
    
    analysis_type = st.selectbox(
        "Select Analysis Type",
        options=["general", "offensive", "defensive", "player_focus", "coaching"],
        format_func=lambda x: {
            "general": "General Analysis",
            "offensive": "Offensive Analysis",
            "defensive": "Defensive Analysis",
            "player_focus": "Player Focus",
            "coaching": "Coaching Perspective"
        }.get(x, x.title())
    )
    
    # Analysis description
    analysis_descriptions = {
        "general": "Overall assessment of plays, players, and strategies",
        "offensive": "Focus on offensive tactics, plays, and execution",
        "defensive": "Focus on defensive schemes, rotations, and effectiveness",
        "player_focus": "Detailed analysis of individual player techniques and decisions",
        "coaching": "Breakdown from a coach's perspective with teaching points"
    }
    
    st.info(analysis_descriptions.get(analysis_type, ""))
    
    # Generate analysis button
    if st.button("Generate Analysis"):
        with st.spinner("Analyzing clip... This may take a minute."):
            try:
                # Call the analysis engine
                result = st.session_state.analysis_engine.analyze_video_file(
                    clip_data["local_path"],
                    clip_data.get("title", "NBA Clip"),
                    analysis_type
                )
                
                if "error" in result:
                    st.error(f"Error analyzing clip: {result['error']}")
                else:
                    # Store the result
                    result_key = f"{clip_data['clip_id']}_{analysis_type}"
                    st.session_state.analysis_results[result_key] = result
                    
                    st.success("Analysis complete!")
                    
                    # Show a preview
                    st.subheader("Analysis Preview")
                    st.markdown(result["analysis"][:500] + "...")
                    
                    # Link to view full analysis
                    st.markdown("View the full analysis on the **View Analysis** page.")
            except Exception as e:
                st.error(f"Error generating analysis: {str(e)}")

# 3. VIEW ANALYSIS PAGE
elif page == "View Analysis":
    st.header("View Analysis Results")
    
    # Check if we have any analysis results
    if not st.session_state.analysis_results:
        # Try to load from files
        try:
            analysis_files = [f for f in os.listdir(ANALYSIS_DIR) if f.endswith('.json')]
            
            if not analysis_files:
                st.warning("No analysis results available.")
                st.markdown("Go to the **Analyze Clips** page to generate an analysis.")
                st.stop()
                
            # Load all analysis files
            for file in analysis_files:
                file_path = os.path.join(ANALYSIS_DIR, file)
                analysis_data = read_analysis_file(file_path)
                
                if analysis_data:
                    clip_id = analysis_data.get("video_path", "").split("/")[-1].split(".")[0]
                    analysis_type = analysis_data.get("analysis_type", "general")
                    result_key = f"{clip_id}_{analysis_type}"
                    st.session_state.analysis_results[result_key] = analysis_data
                    
        except Exception as e:
            st.error(f"Error loading analysis files: {str(e)}")
    
    if not st.session_state.analysis_results:
        st.warning("No analysis results available.")
        st.markdown("Go to the **Analyze Clips** page to generate an analysis.")
        st.stop()
    
    # Select analysis to view
    analysis_options = list(st.session_state.analysis_results.keys())
    selected_analysis = st.selectbox(
        "Select Analysis to View",
        options=analysis_options,
        format_func=lambda x: f"{x.split('_')[0]} - {x.split('_')[-1].title()}"
    )
    
    if selected_analysis and selected_analysis in st.session_state.analysis_results:
        analysis_data = st.session_state.analysis_results[selected_analysis]
        
        # Display analysis information
        st.subheader(f"Analysis of: {analysis_data.get('video_title', 'Unknown')}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Analysis Type:** {analysis_data.get('analysis_type', 'general').title()}")
            st.write(f"**Generated:** {analysis_data.get('analyzed_at', 'Unknown')}")
        
        # Display full analysis
        st.subheader("Analysis")
        st.markdown(analysis_data.get("analysis", "Analysis not available."))
        
        # Extract key segments
        if st.button("Extract Key Segments"):
            with st.spinner("Extracting key segments..."):
                try:
                    segments = st.session_state.analysis_engine.extract_key_segments(
                        analysis_data.get("analysis", "")
                    )
                    
                    if segments:
                        st.subheader("Key Segments")
                        for i, segment in enumerate(segments):
                            with st.expander(f"[{segment.get('timestamp', '?')}] {segment.get('description', '')[:50]}..."):
                                st.write(f"**Description:** {segment.get('description', '')}")
                                if 'significance' in segment:
                                    st.write(f"**Significance:** {segment.get('significance', '')}")
                    else:
                        st.info("No key segments found.")
                except Exception as e:
                    st.error(f"Error extracting segments: {str(e)}")
        
        # Download options
        st.subheader("Download Options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Save as JSON
            if st.button("Save as JSON"):
                # Create a temporary file
                temp_file = os.path.join(TEMP_DIR, f"analysis_{selected_analysis}.json")
                with open(temp_file, 'w') as f:
                    json.dump(analysis_data, f, indent=2)
                
                # Provide download link
                st.markdown(get_binary_file_downloader_html(temp_file, 'JSON File'), unsafe_allow_html=True)
        
        with col2:
            # Save as Text
            if st.button("Save as Text"):
                # Create a temporary file
                temp_file = os.path.join(TEMP_DIR, f"analysis_{selected_analysis}.txt")
                with open(temp_file, 'w') as f:
                    f.write(f"Analysis of: {analysis_data.get('video_title', 'Unknown')}\n")
                    f.write(f"Type: {analysis_data.get('analysis_type', 'general').title()}\n")
                    f.write(f"Generated: {analysis_data.get('analyzed_at', 'Unknown')}\n\n")
                    f.write(analysis_data.get("analysis", "Analysis not available."))
                
                # Provide download link
                st.markdown(get_binary_file_downloader_html(temp_file, 'Text File'), unsafe_allow_html=True)

# 4. ABOUT PAGE
else:  # About page
    st.header("About NBA Game Analysis System")
    
    st.markdown("""
    ## System Overview
    
    This NBA Game Analysis System leverages artificial intelligence to provide professional-level analysis of basketball clips. It's designed to be a proof-of-concept for sports analytics that combines:
    
    1. **Video Processing**: Upload clips or get them from YouTube
    2. **AI Analysis**: Generate detailed basketball insights with Gemini AI
    3. **Multiple Analysis Types**: General, offensive, defensive, player-focused, and coaching perspectives
    
    ## How It Works
    
    1. **Upload clips** through the upload page
    2. **Generate analysis** using Google's Gemini AI model
    3. **View and export** the detailed insights
    
    ## Technical Architecture
    
    The system consists of the following components:
    
    - **Clip Acquisition**: Handles video uploads and YouTube fetching
    - **Direct Analysis Engine**: Sends videos to Gemini AI for basketball analysis
    - **User Interface**: Streamlit-based web interface for interaction
    
    ## Use Cases
    
    - **Coaches**: Analyze game footage for strategic insights
    - **Players**: Study techniques and decision-making
    - **Teams**: Evaluate performance patterns
    - **Fans**: Get deeper understanding of game dynamics
    
    ## Limitations
    
    - Works best with shorter clips (under 2 minutes)
    - Video file size should ideally be under 20MB
    - Analysis quality depends on video clarity and content
    """)
    
    st.subheader("API Keys Required")
    st.markdown("""
    This application requires:
    - **GEMINI_API_KEY**: For AI analysis (from Google AI Studio)
    """)

# Add footer
st.markdown("---")
st.markdown(
    "NBA Game Analysis System | Developed as a Proof of Concept"
)