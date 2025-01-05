from flask import Flask, request, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
)
import json
import re
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def extract_video_id(url):
    """
    Extract video ID from different formats of YouTube URLs
    """
    if match := re.search(r'(?:v=|/v/|youtu\.be/)([^"&?/\s]{11})', url):
        return match.group(1)
    return None

def get_available_transcript(video_id):
    """
    Try to get transcript in English or available languages and translate if needed.
    """
    try:
        # Attempt to fetch the transcript in English
        logger.info(f"Trying to fetch English transcript for video ID: {video_id}")
        return YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
    except NoTranscriptFound:
        logger.info(f"English transcript not found. Attempting other languages for video ID: {video_id}")
        try:
            # Fetch the list of transcripts available for the video
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = None

            # Try to find a Hindi transcript
            try:
                transcript = transcript_list.find_transcript(['hi'])  # 'hi' is the language code for Hindi
            except NoTranscriptFound:
                logger.info("Hindi transcript not found. Trying other available transcripts.")

            # If no Hindi transcript, fallback to other available languages
            if not transcript:
                transcript = transcript_list.find_manually_created_transcript(['es', 'fr', 'de', 'zh', 'ja', 'ar'])

            # Translate the transcript to English if necessary
            if transcript:
                if 'en' not in transcript.language_code:
                    logger.info(f"Translating transcript to English from {transcript.language_code}")
                    transcript = transcript.translate('en')

                return transcript.fetch()

        except Exception as e:
            logger.error(f"Error fetching transcript in other languages: {str(e)}")
            raise NoTranscriptFound(f"Transcript not found in any language for video ID {video_id}")

    # If no transcript is found, raise an exception
    raise NoTranscriptFound(f"No transcript available for video ID {video_id}")

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
    app.run(host='0.0.0.0', port=5000, debug=True)
