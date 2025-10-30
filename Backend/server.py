import os
import asyncio
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import datetime

try:
    from livekit import api
    AccessToken = api.AccessToken
    VideoGrants = api.VideoGrants
except ImportError:
    AccessToken = None
    VideoGrants = None

import jwt
from agent import HotelReceptionistAgent

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
logger = logging.getLogger("flask_server")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

# Initialize agent
agent_instance = HotelReceptionistAgent()

@app.route('/api/agent', methods=['POST'])
def agent_endpoint():
    """Chat endpoint"""
    data = request.json
    user_message = data.get('message', '')
    logger.info(f"📨 Message: {user_message}")
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        response = loop.run_until_complete(agent_instance.handle_user_message(user_message))
        loop.close()
        return jsonify({'response': response})
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return jsonify({'response': f"Error: {str(e)}"}), 500

@app.route('/api/livekit-token', methods=['POST'])
def generate_livekit_token():
    """Generate LiveKit token with proper permissions"""
    data = request.json
    identity = data.get("identity", "user")
    room = data.get("room", "corelance-main-room")

    api_key = os.getenv('LIVEKIT_API_KEY')
    api_secret = os.getenv('LIVEKIT_API_SECRET')
    
    if not api_key or not api_secret:
        logger.error("❌ Missing LIVEKIT_API_KEY or LIVEKIT_API_SECRET")
        return jsonify({"error": "Missing credentials"}), 500

    try:
        token_obj = AccessToken(api_key, api_secret)
        token_obj = token_obj.with_identity(identity).with_name(identity)
        
        # CRITICAL: Grant full audio permissions
        token_obj = token_obj.with_grants(VideoGrants(
            room_join=True,
            room=room,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
            can_publish_sources=['microphone', 'camera']  # Explicit sources
        ))
        
        # Set expiration to 2 hours
        token_obj = token_obj.with_ttl(datetime.timedelta(hours=2))
        
        token = token_obj.to_jwt()
        
        logger.info(f"🎫 Token generated successfully")
        logger.info(f"   Identity: {identity}")
        logger.info(f"   Room: {room}")
        logger.info(f"   Permissions: publish=True, subscribe=True")
        
        return jsonify({
            "token": token,
            "room": room,
            "identity": identity
        })
    except Exception as e:
        logger.error(f"❌ Token generation error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "livekit_configured": bool(os.getenv('LIVEKIT_API_KEY'))
    })

if __name__ == "__main__":
    print("=" * 70)
    print("🚀 Flask Server Starting")
    print("=" * 70)
    print(f"📍 Host: http://localhost:5000")
    print(f"🔗 LiveKit URL: {os.getenv('LIVEKIT_URL', 'Not set')}")
    print(f"🔑 API Key: {os.getenv('LIVEKIT_API_KEY', 'Not set')[:10]}...")
    print("=" * 70)
    app.run(host='0.0.0.0', port=5000, debug=True)