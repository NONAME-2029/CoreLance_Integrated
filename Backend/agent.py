import os
import datetime
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, RoomOutputOptions
from livekit.plugins import google, silero, deepgram, elevenlabs
import asyncio
import pymupdf
from flask import Flask, ctx, request, jsonify, session
from flask_cors import CORS
from prompts import (
    WELCOME_PROMPT, 
    ROOM_TYPES_INFO, 
    MEETING_PROMPT,
    RESERVATION_START_PROMPT,
    ADDITIONAL_SERVICES_PROMPT,
    THANK_YOU_PROMPT
)
from api import (
    search_available_rooms,
    check_room_availability,
    get_room_pricing,
    book_room,
    get_room_details,
    suggest_room_for_occasion,
    calculate_discount,
    get_booking_summary,
    convert_to_pdf,
)
from dbdriver import MeetingDatabase
import logging
import re

# --- Added for LiveKit JWT token ---
try:
    from livekit_jwt import AccessToken, VideoGrant
except ImportError:
    AccessToken = None
    VideoGrant = None

import jwt

# Google Generative AI for direct API calls
import google.generativeai as genai

app = Flask(__name__)
CORS(app)
logger = logging.getLogger("agent")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv(dotenv_path=".env")

meeting_id = "default_meeting"

# Configure Gemini API
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    logger.info(" Gemini API configured successfully")
else:
    logger.warning(" GOOGLE_API_KEY not found in .env file")

class HotelReceptionistAgent(Agent):
    def __init__(self) -> None:

        """
        Initializes the HotelReceptionistAgent with instructions and tools.

        The instructions are comprised of the welcome prompt, room types and pricing information, and the meeting prompt.
        The tools are comprised of the functions for searching available rooms, checking room availability, getting room pricing, booking a room, getting room details, suggesting a room for an occasion, calculating discounts, getting a booking summary, and converting to a PDF.

        If the GOOGLE_API_KEY is set, the Gemini model is initialized with the full system context and a chat session is started.
        """
        super().__init__(
            instructions=WELCOME_PROMPT + "\n\n" + ROOM_TYPES_INFO + "\n\n" + MEETING_PROMPT,
            tools=[
                search_available_rooms,
                check_room_availability,
                get_room_pricing,
                book_room,
                get_room_details,
                suggest_room_for_occasion,
                calculate_discount,
                get_booking_summary,
                convert_to_pdf,
            ]
        )
        self.meeting_db = MeetingDatabase()
        self.conversation_history = []
        
        # Initialize Gemini model with full system context
        if GOOGLE_API_KEY:
            self.system_context = (
                f"{WELCOME_PROMPT}\n\n"
                f"{ROOM_TYPES_INFO}\n\n"
                f"{MEETING_PROMPT}\n\n"
                "Additional Context:\n"
                "- Respond conversationally and warmly\n"
                "- Keep responses concise for voice (2-3 sentences max)\n"
                "- You can help with room reservations and provide detailed pricing\n"
                "- You can manage meeting files and transcripts\n"
                "- Mention special discounts when appropriate\n"
            )
            
            self.gemini_model = genai.GenerativeModel(
                'gemini-2.0-flash-exp',
                system_instruction=self.system_context
            )
            self.chat = self.gemini_model.start_chat(history=[])
            logger.info("✅ Gemini chat session initialized with full context")
        else:
            self.gemini_model = None
            self.chat = None
            
    _active_tasks = []

    async def async_handle_byte_stream(self, reader, participant_identity):
        try:
            info = reader.info
            file_bytes = bytes()
            with open(info["name"], mode="wb") as f:
                async for chunk in reader:
                    file_bytes += chunk
                f.write(file_bytes)

            doc = pymupdf.open(info["name"])
            text_accum = ""
            for page in doc:
                text = page.get_text()
                text_accum += text

            chat_ctx = self.chat_ctx.copy()
            msg_content = [
                "Here is a balance sheet in text format. Please answer questions asked based on the PDF.",
                text_accum
            ]
            chat_ctx.add_message(role="user", content=msg_content)
            await self.update_chat_ctx(chat_ctx)
        except Exception as e:
            logger.error(f"Error handling byte stream: {e}")

    def handle_byte_stream(self, reader, participant_identity):
        task = asyncio.create_task(self.async_handle_byte_stream(reader, participant_identity))
        self._active_tasks.append(task)
        task.add_done_callback(lambda t: self._active_tasks.remove(t))

    async def handle_user_message(self, message: str) -> str:
        text = message.lower().strip()
        
        logger.info(f"📨 Processing message: {message}")

        # Handle specific meeting file commands
        if "add" in text and "pdf" in text:
            match = re.search(r"(?:path|file(?:name)?|file):\s*([^\s]+\.pdf)", message, re.IGNORECASE)
            pdf_path = match.group(1) if match else None
            if not pdf_path:
                return "Please specify the PDF file path ('file: yourfile.pdf') to ingest."
            success = self.meeting_db.ingest_pdf_file(pdf_path)
            return f"PDF '{pdf_path}' ingested for retrieval." if success else f"Failed to ingest '{pdf_path}'."

        if "add" in text and "meeting file" in text:
            match_file = re.search(r"filename\s*[:=]\s*(\S+)", message, re.IGNORECASE)
            match_content = re.search(r"content\s*[:=]\s*(.+)", message, re.IGNORECASE | re.DOTALL)
            if not match_file or not match_content:
                return "Please specify your 'filename:...' and 'content:...' to add a meeting file."
            filename = match_file.group(1)
            content = match_content.group(1)
            return self.add_meeting_file(filename, content)

        if re.search(r'\b(search|find|lookup|show)\b.*\b(meeting file|meeting|transcript|notes)\b', text):
            query_match = re.search(r'(?:about|for|on|:)\s*(.*)', text)
            query = query_match.group(1) if query_match else message
            return self.search_meeting_files(query)

        if re.search(r'\b(get|show|retrieve|read)\b.*\b(meeting file|transcript|meeting)\b', text):
            filename_match = re.search(r"filename\s*[:=]\s*(\S+)", message, re.IGNORECASE)
            if not filename_match:
                return "Please specify the filename with 'filename:<filename>'."
            filename = filename_match.group(1)
            return self.retrieve_meeting_file(filename)

        if re.search(r'\b(delete|remove|truncate|clear)\b.*(meeting files|transcripts|meetings|database)\b', text):
            return self.truncate_meeting_files()

        # Use Gemini for all other conversations
        return await self.chat_with_gemini(message)

    async def chat_with_gemini(self, message: str) -> str:
        """
        Use Google Gemini API for natural conversation with full context
        """
        try:
            if not self.gemini_model or not self.chat:
                logger.error("Gemini model not initialized")
                return "Sorry, AI conversation is not available. Please check GOOGLE_API_KEY in .env file."
            
            logger.info(f" Calling Gemini API with message: {message}")
            
            # Send message to Gemini (system context already set in model initialization)
            response = await asyncio.to_thread(
                self.chat.send_message,
                message
            )
            
            ai_response = response.text
            logger.info(f" Gemini response: {ai_response[:100]}...")
            
            # Store in conversation history
            self.conversation_history.append({
                "user": message,
                "assistant": ai_response,
                "timestamp": datetime.datetime.now()
            })
            
            return ai_response
            
        except Exception as e:
            logger.error(f" Error calling Gemini API: {e}", exc_info=True)
            return (
                "Sorry, I'm having trouble generating a response right now. "
                "However, I'm still here to help! You can ask me about:\n\n"
                "• Room reservations and availability\n"
                "• Meeting file management\n"
                "• Transcript searches\n"
                "• Room pricing and special discounts\n\n"
                "What would you like to know?"
            )

    def add_meeting_file(self, filename: str, content: str) -> str:
        success = self.meeting_db.add_file(filename, content)
        return (
            f" Meeting file '{filename}' added successfully."
            if success else f" Failed to add meeting file '{filename}'."
        )

    def search_meeting_files(self, query: str, top_k: int = 5) -> str:
        results = self.meeting_db.vector_search(query, top_k)
        if not results:
            return "No meeting files found matching your query. Would you like to add a new meeting file?"
        response = "📋 Meeting files matching your query:\n\n"
        for r in results:
            snippet = r["content"][:200].replace('\n', ' ')
            response += f"• **{r['filename']}** (Similarity: {r['similarity']:.3f}, Date: {r['created_at']})\n  {snippet}...\n\n"
        return response

    def retrieve_meeting_file(self, filename: str) -> str:
        content = self.meeting_db.retrieve_file_content(filename)
        return content if content else f"❌ No meeting file found with filename '{filename}'."

    def truncate_meeting_files(self) -> str:
        self.meeting_db.truncate_files()
        return "✅ All meeting files have been deleted successfully."


print("=" * 70)
print("Initializing HotelReceptionistAgent...")
print("=" * 70)
agent_instance = HotelReceptionistAgent()
print(" Agent initialized successfully with full Gemini integration!")
print("=" * 70)

@app.route('/api/agent', methods=['POST'])
def agent_endpoint():
    data = request.json
    user_message = data.get('message', '')
    logger.info(f"📨 Received message: {user_message}")
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        response = loop.run_until_complete(agent_instance.handle_user_message(user_message))
        loop.close()
        logger.info(f" Generated response: {response[:100]}...")
    except Exception as e:
        logger.error(f"❌ Error in agent endpoint: {e}", exc_info=True)
        response = "Sorry, there was an internal error with the agent. Please try again."
    
    return jsonify({'response': response})

@app.route('/api/livekit-token', methods=['POST'])
def generate_livekit_token():
    data = request.json
    identity = data.get("identity", "anonymous")
    room = data.get("room", "default-room")

    api_key = os.environ.get('LIVEKIT_API_KEY')
    api_secret = os.environ.get('LIVEKIT_API_SECRET')
    
    if not api_key or not api_secret:
        logger.error("LiveKit credentials not configured")
        return jsonify({"error": "LiveKit credentials not configured"}), 500

    token = None

    try:
        if AccessToken is not None:
            at = AccessToken(api_key, api_secret, identity=identity)
            grant = VideoGrant(room=room)
            at.add_grant(grant)
            token = at.to_jwt()
        else:
            payload = {
                "iss": api_key,
                "sub": identity,
                "room": room,
                "exp": int((datetime.datetime.utcnow() + datetime.timedelta(hours=1)).timestamp()),
                "video": {"roomJoin": True, "room": room}
            }
            token = jwt.encode(payload, api_secret, algorithm='HS256')
        
        return jsonify({"token": token})
    except Exception as e:
        logger.error(f"Error generating token: {e}")
        return jsonify({"error": str(e)}), 500

# Replace your entrypoint function in agent.py with this:

async def entrypoint(ctx: agents.JobContext):
    """Main entry point for the agent"""
    global meeting_id

    logger.info("=" * 70)
    logger.info(f"🚪 AGENT JOINING ROOM: {ctx.room.name}")
    logger.info(f"   Local Participant will be: AI-Agent")
    logger.info("=" * 70)

    # CRITICAL: Connect to room FIRST before creating session
    logger.info("🔌 Step 1: Connecting to LiveKit room...")
    await ctx.connect(auto_subscribe=agents.AutoSubscribe.AUDIO_ONLY)
    logger.info(f"✅ Connected to room: {ctx.room.name}")
    
    # Wait a moment for connection to stabilize
    await asyncio.sleep(0.5)
    
    # List current participants
    logger.info(f"👥 Current participants in room:")
    logger.info(f"   Local: {ctx.room.local_participant.identity}")
    for participant in ctx.room.remote_participants.values():
        logger.info(f"   Remote: {participant.identity}")

    # Create agent session with proper audio configuration
    logger.info("🎤 Step 2: Creating agent session...")
    session = AgentSession(
        stt=deepgram.STT(api_key=os.getenv("DEEPGRAM_API_KEY")),
        llm=google.LLM(model="gemini-2.0-flash", api_key=os.getenv("GOOGLE_API_KEY")),
        tts=deepgram.TTS(api_key=os.getenv("DEEPGRAM_API_KEY")),
        vad=silero.VAD.load()
    )

    # Create log file
    try:
        with open(f"user_speech_log_{meeting_id}.txt", "x") as file:
            pass
        logger.info(f"✅ Created log file: user_speech_log_{meeting_id}.txt")
    except FileExistsError:
        logger.info(f"ℹ️ Log file already exists")

    # Event handlers with detailed logging
    @session.on("user_input_transcribed")
    def on_transcript(transcript):
        if transcript.is_final:
            logger.info("=" * 70)
            logger.info(f"📝 USER TRANSCRIPTION: '{transcript.transcript}'")
            logger.info("=" * 70)
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(f"user_speech_log_{meeting_id}.txt", "a") as f:
                f.write(f"[{timestamp}] {transcript.transcript}\n")

    @session.on("agent_started_speaking")
    def on_agent_start():
        logger.info("🔊 ===== AGENT STARTED SPEAKING =====")

    @session.on("agent_stopped_speaking")
    def on_agent_stop():
        logger.info("🔊 ===== AGENT STOPPED SPEAKING =====")

    @session.on("user_started_speaking")
    def on_user_start():
        logger.info("🎤 ===== USER STARTED SPEAKING =====")

    @session.on("user_stopped_speaking")
    def on_user_stop():
        logger.info("🎤 ===== USER STOPPED SPEAKING =====")
    
    @session.on("agent_speech_committed")
    def on_speech_committed(message):
        logger.info(f"💬 Agent said: {message.content[:100]}...")

    agent = agent_instance

    # Register byte stream handler
    ctx.room.register_byte_stream_handler(
        topic="pdf_upload",
        handler=agent.handle_byte_stream
    )

    # CRITICAL: Start session with proper audio output options
    logger.info("🎤 Step 3: Starting agent session with audio enabled...")
    await session.start(
        room=ctx.room,
        agent=agent,
        room_output_options=RoomOutputOptions(
            transcription_enabled=True,
            audio_enabled=True  # CRITICAL: Enable audio output
        ),
    )
    logger.info("✅ Session started successfully with audio enabled!")

    # Wait for tracks to be published
    await asyncio.sleep(1)

    # Verify audio track is published
    logger.info("🔍 Checking published tracks...")
    for track_sid, publication in ctx.room.local_participant.track_publications.items():
        logger.info(f"   📢 Published: {publication.kind} - {publication.source}")

    # Send greeting message
    logger.info("🗣️ Step 4: Sending greeting...")
    try:
        await session.generate_reply(
            instructions=(
                "Greet the user warmly and naturally. Say: "
                "'Hello! Welcome to Grand Plaza Hotel. I'm your AI assistant. "
                "How can I help you today?' "
                "Use a friendly, conversational tone."
            )
        )
        logger.info("✅ Greeting sent successfully!")
    except Exception as e:
        logger.error(f"❌ Error sending greeting: {e}", exc_info=True)

    logger.info("=" * 70)
    logger.info("♾️ AGENT IS NOW ACTIVE AND LISTENING")
    logger.info("💡 Speak into your microphone to interact with the agent")
    logger.info("=" * 70)

    # Keep the agent running
    await asyncio.Event().wait()
if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
