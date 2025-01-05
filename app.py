from flask import Flask, request, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
import json

app = Flask(__name__)

@app.route('/get_transcript', methods=['GET'])
def get_transcript():
    video_url = request.args.get('url')
    if not video_url:
        return jsonify({'error': 'You must provide a YouTube video URL.'}), 400
    
    # Extract video ID from the YouTube URL
    video_id = video_url.split("v=")[-1]

    try:
        # Attempt to get the transcript in English first
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
    except NoTranscriptFound:
        try:
            # If English is not available, fetch the transcript in Hindi or other available languages
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['hi', 'en'])
        except Exception as e:
            # If neither English nor Hindi is available, return an error
            return jsonify({'error': str(e)}), 500

    # Combine all text parts into a single string
    combined_transcript = " ".join([entry['text'] for entry in transcript])

    # Return the response with properly decoded characters
    return app.response_class(
        response=json.dumps({'transcript': combined_transcript}, ensure_ascii=False),
        status=200,
        mimetype='application/json'
    )

if __name__ == '__main__':
    app.run(debug=True)
