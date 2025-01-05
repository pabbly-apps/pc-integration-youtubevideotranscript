from flask import Flask, request, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
import json
import re
import logging
from urllib.parse import urlparse, parse_qs

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def extract_video_id(url):
    """
    Extract video ID from different formats of YouTube URLs
    """
    # Handle various YouTube URL formats
    if match := re.search(r'(?:v=|/v/|youtu\.be/)([^"&?/\s]{11})', url):
        return match.group(1)
    return None

def get_available_transcript(video_id):
    """
    Try to get transcript in different languages and with different methods
    """
    try:
        # First attempt: Get English transcript
        return YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
    except NoTranscriptFound:
        # Second attempt: Get transcript in any language and translate to English
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = transcript_list.find_transcript(['en'])
            if not transcript:
                # If no English transcript, get the first available and translate
                transcript = transcript_list.find_transcript(['hi', 'es', 'fr', 'de'])
                transcript = transcript.translate('en')
            return transcript.fetch()
        except Exception as e:
            logger.error(f"Error getting transcript: {str(e)}")
            raise

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    """
    return jsonify({'status': 'healthy'}), 200

@app.route('/get_transcript', methods=['GET'])
def get_transcript():
    try:
        video_url = request.args.get('url')
        if not video_url:
            return jsonify({'error': 'You must provide a YouTube video URL.'}), 400

        # Extract and validate video ID
        video_id = extract_video_id(video_url)
        if not video_id:
            return jsonify({'error': 'Invalid YouTube URL format.'}), 400

        logger.info(f"Attempting to fetch transcript for video ID: {video_id}")
        
        try:
            transcript = get_available_transcript(video_id)
        except TranscriptsDisabled:
            return jsonify({
                'error': 'Transcripts are disabled for this video.',
                'video_id': video_id
            }), 403
        except VideoUnavailable:
            return jsonify({
                'error': 'Video is unavailable.',
                'video_id': video_id
            }), 404
        except Exception as e:
            logger.error(f"Error processing video {video_id}: {str(e)}")
            return jsonify({
                'error': f'Failed to retrieve transcript: {str(e)}',
                'video_id': video_id
            }), 500

        # Combine all text parts into a single string
        combined_transcript = " ".join([entry['text'] for entry in transcript])

        # Return the response with properly decoded characters
        return app.response_class(
            response=json.dumps({
                'transcript': combined_transcript,
                'video_id': video_id,
                'length': len(combined_transcript)
            }, ensure_ascii=False),
            status=200,
            mimetype='application/json'
        )

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)