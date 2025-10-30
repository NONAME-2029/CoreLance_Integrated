import asyncio
from livekit import agents
from agent import entrypoint
import os
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# CRITICAL: Must match frontend room name exactly
ROOM_NAME = "corelance-main-room"

async def request_fnc(req: agents.JobRequest):
    """Accept job requests for our room"""
    logger.info("=" * 70)
    logger.info(f"📨 JOB REQUEST RECEIVED")
    logger.info(f"   Room Name: {req.room.name}")
    logger.info(f"   Job ID: {req.id}")
    logger.info("=" * 70)
    
    # Accept the job request (no argument needed)
    await req.accept()
    logger.info(f"✅ Job accepted! Agent will join room: {req.room.name}")

if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("🚀 STARTING CORELANCE AI AGENT WORKER")
    logger.info("=" * 70)
    logger.info(f"📍 Primary Room: {ROOM_NAME}")
    logger.info(f"🔗 LiveKit URL: {os.getenv('LIVEKIT_URL', 'wss://corelance-1egb2q0f.livekit.cloud')}")
    logger.info(f"🔑 API Key: {os.getenv('LIVEKIT_API_KEY', 'NOT SET')[:15]}...")
    logger.info(f"🔐 API Secret: {os.getenv('LIVEKIT_API_SECRET', 'NOT SET')[:10]}...")
    logger.info("=" * 70)
    logger.info("✅ Agent worker ready - Waiting for participant to join room...")
    logger.info("💡 Agent will automatically join when someone connects to the room")
    logger.info("=" * 70)
    
    try:
        # Run the worker with explicit configuration
        agents.cli.run_app(
            agents.WorkerOptions(
                entrypoint_fnc=entrypoint,
                request_fnc=request_fnc,
                api_key=os.getenv("LIVEKIT_API_KEY"),
                api_secret=os.getenv("LIVEKIT_API_SECRET"),
                ws_url=os.getenv("LIVEKIT_URL", "wss://corelance-1egb2q0f.livekit.cloud"),
            )
        )
    except KeyboardInterrupt:
        logger.info("\n👋 Agent worker shutting down gracefully...")
    except Exception as e:
        logger.error(f"❌ FATAL ERROR: {e}", exc_info=True)
        raise