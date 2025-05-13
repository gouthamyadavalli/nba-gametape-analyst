# direct_analysis_engine.py

import os
import json
import logging
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
import google.generativeai as genai
import time
import base64

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('direct_analysis_engine')

# Constants
ANALYSIS_DIR = "analyses"
os.makedirs(ANALYSIS_DIR, exist_ok=True)

class DirectAnalysisEngine:
    """Direct video-to-analysis engine using Gemini"""
    
    def __init__(self, api_key: str = None):
        """
        Initialize the analysis engine
        
        Args:
            api_key: Gemini API key (defaults to GEMINI_API_KEY environment variable)
        """
        self.api_key = os.environ.get("GEMINI_API_KEY")
        
        if not self.api_key:
            logger.error("No Gemini API key provided. Set GEMINI_API_KEY environment variable.")
            raise ValueError("Gemini API key is required")
            
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        
        # Use Gemini Pro Vision for video analysis
        self.model_name = "gemini-2.0-flash"
        self.model = genai.GenerativeModel(self.model_name)
        
        logger.info(f"Initialized Direct Analysis Engine with model: {self.model_name}")
    
    def create_analysis_prompt(self, video_title: str, analysis_type: str = "general") -> str:
        """
        Create a prompt for video analysis
        
        Args:
            video_title: Title of the video
            analysis_type: Type of analysis to perform
            
        Returns:
            Formatted prompt text
        """
        # Analysis prompt templates for different analysis types
        prompt_templates = {
            "general": f"""
                You are a professional NBA sports analyst. Analyze this basketball clip titled "{video_title}".
                
                Provide a professional, insightful analysis covering:
                1. Key plays and moments
                2. Player performance and techniques
                3. Strategic elements and team dynamics
                4. Notable statistics or achievements
                
                Your analysis should:
                - Include specific timestamps when referencing moments in the clip
                - Use basketball terminology appropriately
                - Provide meaningful insights beyond what's obvious
                - Highlight both offensive and defensive aspects
                - Note any remarkable player skills or decisions
                
                Format your analysis in clear sections with professional terminology. Always include timestamps when referencing specific moments.
                
                Include a section at the end called "Key Plays" that lists the most important moments with their timestamps in a concise format.
            """,
            
            "offensive": f"""
                You are a professional NBA offensive coordinator analyst. Analyze the offensive aspects of this basketball clip titled "{video_title}".
                
                Provide a detailed analysis of the offensive strategies and execution, covering:
                1. Offensive formations and play patterns
                2. Shot selection and shooting efficiency
                3. Ball movement and passing lanes
                4. Screen setting and player positioning
                5. Spacing and movement without the ball
                6. Decision-making by ball handlers
                
                Your analysis should:
                - Include specific timestamps when referencing moments in the clip
                - Evaluate the effectiveness of offensive choices
                - Identify successful patterns and missed opportunities
                - Consider how defenders were manipulated or countered
                - Note any remarkable offensive skills or decisions
                
                Format your analysis with clear sections using professional offensive terminology. Always include timestamps when referencing specific moments.
                
                Include a section at the end called "Key Offensive Plays" that lists the most important offensive moments with their timestamps in a concise format.
            """,
            
            "defensive": f"""
                You are a professional NBA defensive specialist analyst. Analyze the defensive aspects of this basketball clip titled "{video_title}".
                
                Provide a detailed analysis of the defensive strategies and execution, covering:
                1. Defensive schemes and approaches
                2. Individual defensive assignments and execution
                3. Help defense and rotations
                4. Rebounding positioning and technique
                5. Transition defense
                6. Defensive communication and coordination
                
                Your analysis should:
                - Include specific timestamps when referencing moments in the clip
                - Evaluate the effectiveness of defensive choices
                - Identify successful stops and defensive breakdowns
                - Consider how defenders reacted to offensive actions
                - Note any remarkable defensive skills or decisions
                
                Format your analysis with clear sections using professional defensive terminology. Always include timestamps when referencing specific moments.
                
                Include a section at the end called "Key Defensive Plays" that lists the most important defensive moments with their timestamps in a concise format.
            """,
            
            "player_focus": f"""
                You are a professional NBA player development analyst. Focus your analysis on the individual players in this basketball clip titled "{video_title}".
                
                Provide a detailed player-focused analysis, covering:
                1. Individual strengths demonstrated in the clip
                2. Technical skills showcased (shooting form, dribbling, footwork, etc.)
                3. Decision-making and basketball IQ moments
                4. Off-ball movement and positioning
                5. Areas for potential improvement
                
                Your analysis should:
                - Include specific timestamps when referencing moments in the clip
                - Break down analysis by individual players when possible
                - Evaluate technical execution of basketball fundamentals
                - Identify highest-impact player contributions
                - Note any unique or signature moves by specific players
                
                Format your analysis by player where possible, using professional terminology. Always include timestamps when referencing specific moments.
                
                Include a section at the end called "Player Highlights" that lists the most notable player moments with their timestamps in a concise format.
            """,
            
            "coaching": f"""
                You are a professional NBA coach. Analyze this basketball clip titled "{video_title}" from a coaching perspective.
                
                Provide a coaching-focused analysis, covering:
                1. Set plays and offensive/defensive schemes identified
                2. Tactical adjustments that worked or could have been made
                3. Player utilization and matchup exploitation
                4. Clock management and situational decision-making
                5. Teaching points for practice and player development
                
                Your analysis should:
                - Include specific timestamps when referencing moments in the clip
                - Evaluate coaching decisions and their outcomes
                - Identify alternative approaches that could have been used
                - Consider how this relates to typical team strategies
                - Provide specific drills or teaching points to address any issues
                
                Format your analysis as if you were breaking down film with assistant coaches. Always include timestamps when referencing specific moments.
                
                Include a section at the end called "Coaching Points" that lists the most important teaching moments with their timestamps in a concise format.
            """
        }
        
        # Use the appropriate template or fall back to general
        prompt = prompt_templates.get(analysis_type, prompt_templates["general"])
        
        return prompt.strip()
    
    def analyze_video_file(self, video_path: str, video_title: str = None, 
                          analysis_type: str = "general") -> Dict:
        """
        Analyze a video file directly with Gemini
        
        Args:
            video_path: Path to video file
            video_title: Optional title of video (defaults to filename)
            analysis_type: Type of analysis to perform
            
        Returns:
            Dictionary with analysis results
        """
        try:
            if not os.path.exists(video_path):
                logger.error(f"Video file not found: {video_path}")
                return {"error": f"Video file not found: {video_path}"}
                
            # Get video title if not provided
            if not video_title:
                video_title = os.path.basename(video_path)
                
            logger.info(f"Analyzing video: {video_title} ({analysis_type})")
            
            # Create the analysis prompt
            prompt = self.create_analysis_prompt(video_title, analysis_type)
            
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
            
            # Check file size
            file_size = os.path.getsize(video_path) / (1024 * 1024)  # Size in MB
            
            if file_size > 100:
                logger.warning(f"Video file is large ({file_size:.2f} MB), which may exceed model limits")
            
            # Read video file in binary mode
            with open(video_path, 'rb') as f:
                video_data = f.read()
            
            # Create a multipart prompt with the text and video
            try:
                response = self.model.generate_content([
                    prompt,
                    {"mime_type": mimetype, "data": video_data}
                ])
                
                # Extract analysis text
                analysis_text = response.text
                
            except Exception as e:
                logger.error(f"Error generating analysis with Gemini: {str(e)}")
                
                # If file is too large, try to send a portion
                if file_size > 10:
                    logger.info("Attempting to analyze a portion of the video...")
                    # Just use the first 10MB of the video
                    video_data = video_data[:10 * 1024 * 1024]
                    
                    response = self.model.generate_content([
                        prompt + "\n\nNote: Due to size limitations, only the first portion of the video is being analyzed.",
                        {"mime_type": mimetype, "data": video_data}
                    ])
                    
                    analysis_text = response.text
                else:
                    # Re-raise if the file isn't too large
                    raise
            
            # Create analysis result
            result = {
                "video_path": video_path,
                "video_title": video_title,
                "analysis_type": analysis_type,
                "analysis": analysis_text,
                "analyzed_at": datetime.now().isoformat()
            }
            
            # Save analysis to file
            saved_path = self._save_analysis(result)
            result["saved_path"] = saved_path
            
            logger.info(f"Successfully analyzed video: {video_title}")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing video: {str(e)}")
            return {
                "video_path": video_path,
                "video_title": video_title or os.path.basename(video_path),
                "error": str(e),
                "analysis_type": analysis_type,
                "analyzed_at": datetime.now().isoformat()
            }
    
    def _save_analysis(self, analysis_result: Dict) -> str:
        """
        Save analysis result to file with properly formatted text
        
        Args:
            analysis_result: Analysis result dictionary
            
        Returns:
            Path to saved file
        """
        try:
            video_name = os.path.splitext(os.path.basename(analysis_result["video_path"]))[0]
            analysis_type = analysis_result.get("analysis_type", "general")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create filename
            filename = f"{video_name}_{analysis_type}_{timestamp}.json"
            filepath = os.path.join(ANALYSIS_DIR, filename)
            
            # Create a formatted copy of the result for saving
            formatted_result = analysis_result.copy()
            
            # Format the analysis text to preserve real line breaks
            # This ensures the saved JSON has proper formatting and newlines are preserved
            
            # Save to file using json.dump with indent and ensuring_ascii=False for better readability
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(formatted_result, f, indent=2, ensure_ascii=False)
                    
            logger.info(f"Saved analysis to {filepath}")
            
            # Also create a plaintext version for easy reading
            txt_filepath = filepath.replace('.json', '.txt')
            with open(txt_filepath, 'w', encoding='utf-8') as f:
                f.write(f"Analysis of: {video_name}\n")
                f.write(f"Type: {analysis_type}\n")
                f.write(f"Date: {analysis_result.get('analyzed_at', '')}\n\n")
                f.write(analysis_result.get('analysis', ''))
            
            return filepath
                
        except Exception as e:
            logger.error(f"Error saving analysis: {str(e)}")
            return ""
        
    def extract_key_segments(self, analysis_text: str) -> List[Dict]:
        """
        Extract key segments with timestamps from analysis
        
        Args:
            analysis_text: Analysis text from Gemini
            
        Returns:
            List of segments with timestamps
        """
        try:
            # Use Gemini to extract key segments
            prompt = f"""
            Extract the key moments with timestamps from this basketball analysis:
            
            {analysis_text}
            
            Format the output as valid JSON with the following structure:
            ```json
            [
                {{
                    "timestamp": "10.5",
                    "description": "Brief description of what happens",
                    "significance": "Why this moment is important"
                }},
                ...
            ]
            ```
            
            Include only the JSON in your response, nothing else. Extract at least 5 key moments if possible.
            """
            
            # Use regular Gemini Pro for text processing
            text_model = genai.GenerativeModel('gemini-2.0-flash')
            
            # Generate key segments with Gemini
            response = text_model.generate_content(prompt)
            
            # Extract JSON from response
            response_text = response.text
            
            # Clean up the response if it contains markdown code block
            if "```json" in response_text:
                json_content = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_content = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_content = response_text.strip()
                
            # Parse the JSON
            segments = json.loads(json_content)
            
            logger.info(f"Extracted {len(segments)} key segments")
            return segments
            
        except Exception as e:
            logger.error(f"Error extracting key segments: {str(e)}")
            return []
    
    def create_analysis_summary(self, analysis_text: str, max_length: int = 200) -> str:
        """
        Create a brief summary of the analysis
        
        Args:
            analysis_text: Analysis text from Gemini
            max_length: Maximum length of summary in characters
            
        Returns:
            Brief summary text
        """
        try:
            # Use Gemini to create a summary
            prompt = f"""
            Summarize this basketball analysis in about 2-3 sentences:
            
            {analysis_text}
            
            Keep the summary concise, informative, and focused on the most important insights.
            """
            
            # Use regular Gemini Pro for text processing
            text_model = genai.GenerativeModel("gemini-pro")
            
            # Generate summary with Gemini
            response = text_model.generate_content(prompt)
            
            # Extract summary text
            summary = response.text.strip()
            
            # Truncate if too long
            if len(summary) > max_length:
                summary = summary[:max_length].rsplit('.', 1)[0] + '.'
                
            logger.info(f"Created analysis summary ({len(summary)} chars)")
            return summary
            
        except Exception as e:
            logger.error(f"Error creating summary: {str(e)}")
            return "Analysis summary not available."


# Command-line interface
if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="NBA Direct Video Analysis Engine")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Analyze video command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a video file")
    analyze_parser.add_argument("video_path", help="Path to video file")
    analyze_parser.add_argument("--title", help="Optional video title")
    analyze_parser.add_argument("--type", choices=["general", "offensive", "defensive", 
                                                "player_focus", "coaching"],
                              default="general", help="Analysis type")
    
    # Extract key segments command
    segments_parser = subparsers.add_parser("segments", help="Extract key segments from analysis")
    segments_parser.add_argument("analysis_file", help="Path to analysis JSON file")
    
    # Summarize command
    summary_parser = subparsers.add_parser("summarize", help="Create summary of analysis")
    summary_parser.add_argument("analysis_file", help="Path to analysis JSON file")
    summary_parser.add_argument("--max-length", type=int, default=200, help="Maximum summary length")
    
    args = parser.parse_args()
    
    # Create analysis engine
    try:
        engine = DirectAnalysisEngine()
    except ValueError as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
    
    if args.command == "analyze":
        # Analyze video
        result = engine.analyze_video_file(args.video_path, args.title, args.type)
        
        if "error" in result:
            print(f"Error: {result['error']}")
            sys.exit(1)
            
        # Print brief result
        print(f"Successfully analyzed video: {result['video_title']}")
        print(f"Analysis type: {result['analysis_type']}")
        print(f"Analysis length: {len(result['analysis'])} characters")
        print(f"Saved to: {result.get('saved_path', 'unknown')}")
        
        # Print a brief excerpt
        excerpt_length = min(200, len(result['analysis']))
        print("\nExcerpt:")
        print(result['analysis'][:excerpt_length] + "...")
            
    elif args.command == "segments":
        # Load analysis
        try:
            with open(args.analysis_file, 'r') as f:
                analysis_data = json.load(f)
                
            # Extract key segments
            segments = engine.extract_key_segments(analysis_data['analysis'])
            
            # Print segments
            print(f"Extracted {len(segments)} key segments:")
            for i, segment in enumerate(segments):
                print(f"{i+1}. [{segment.get('timestamp', '?')}] {segment.get('description', '')}")
                if 'significance' in segment:
                    print(f"   Significance: {segment.get('significance', '')}")
                print()
                
        except Exception as e:
            print(f"Error: {str(e)}")
            sys.exit(1)
            
    elif args.command == "summarize":
        # Load analysis
        try:
            with open(args.analysis_file, 'r') as f:
                analysis_data = json.load(f)
                
            # Create summary
            summary = engine.create_analysis_summary(analysis_data['analysis'], args.max_length)
            
            # Print summary
            print("Analysis Summary:")
            print(summary)
                
        except Exception as e:
            print(f"Error: {str(e)}")
            sys.exit(1)
            
    else:
        parser.print_help()