#!/usr/bin/env python3
import os
import asyncio
import threading
import queue
from typing import AsyncGenerator, List, Dict
from dotenv import load_dotenv
import google.generativeai as genai

# Load env variables
load_dotenv("API_Key.env")

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-2.5-flash" 
# gemini-2.0.-flah
# gemini-2.5-flash
# gemini-2.5-flash-lite

if not API_KEY:
    raise ValueError("❌ GEMINI_API_KEY not found in API_Key.env")

genai.configure(api_key=API_KEY)

# --- 1. CONVERSATIONAL MODEL ---
SYSTEM_INSTRUCTION = """
You are Sarah, a professional and friendly real estate agent for Barbie Builders.
Your goal is to qualify leads by having a natural conversation.

CRITICAL VOICE RULES:
1. Keep every response under 2 sentences. Use simple, spoken English.
2. NEVER use lists, bullet points, bold text, or markdown. Speak in full, flowing sentences.
3. Ask only ONE question at a time. Wait for the user's answer before moving on.
4. Do not make up facts. If unsure, say you will check with the team.

CONVERSATION FLOW:
1. Start by welcoming the user and asking how you can help.
2. Contextual Awareness: If the user mentions a location, immediately tailor your suggestions to that area.
3. Data Gathering: Casually collect these details over multiple turns:
   - Preferred Location
   - Property Type (3BHK, Villa, Plot)
   - Budget Range

TONE: Warm, professional, and concise. Treat this like a phone call, not an email.
"""

GEN_CONFIG = genai.GenerationConfig(
    temperature=0.7,
)

model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    system_instruction=SYSTEM_INSTRUCTION
)

chat_session = model.start_chat(history=[])
_chat_lock = threading.Lock()


async def get_ai_response_stream(user_text: str) -> AsyncGenerator[str, None]:
    """
    Yields text chunks from Gemini as they are generated.
    Uses a thread and a queue to safely bridge sync Gemini and async ARI.
    """
    chunk_queue = asyncio.Queue()
    SENTINEL = object()

    def run_gemini_sync():
        try:
            with _chat_lock:
                response = chat_session.send_message(
                    user_text, 
                    stream=True, 
                    generation_config=GEN_CONFIG
                )
                
                for chunk in response:
                    # --- FIX START: Safely handle chunks with no text ---
                    content = None
                    try:
                        content = chunk.text
                    except Exception:
                        # Ignore chunks with no text (like finish signals)
                        pass
                    
                    if content:
                        loop.call_soon_threadsafe(chunk_queue.put_nowait, content)
                    # --- FIX END ---
                        
        except Exception as e:
            print(f"❌ Gemini Sync Error: {e}")
            loop.call_soon_threadsafe(chunk_queue.put_nowait, f"Error: {e}")
        finally:
            loop.call_soon_threadsafe(chunk_queue.put_nowait, SENTINEL)

    loop = asyncio.get_running_loop()
    thread = threading.Thread(target=run_gemini_sync, daemon=True)
    thread.start()

    while True:
        item = await chunk_queue.get()
        if item is SENTINEL:
            break
        if isinstance(item, str) and item.startswith("Error:"):
            # Don't show the user the internal error, just log it above
            print(f"⚠️ suppressed stream error: {item}") 
            break
            
        yield item


# --- 2. MINUTES OF MEETING MODEL ---
mom_model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    system_instruction="""You are an expert executive assistant. 
Your task is to summarize sales calls into structured Minutes of Meeting (MoM) documents."""
)

async def generate_mom(transcript: List[Dict]) -> str:
    """
    Generates a structured MoM from the call transcript.
    """
    if not transcript:
        return "No transcript available."

    conversation_text = ""
    for entry in transcript:
        role = "Agent (Sarah)" if entry["speaker"] == "agent" else "Customer"
        conversation_text += f"{role}: {entry['text']}\n"

    prompt = f"""
    Based on the following conversation transcript, create a structured Minutes of Meeting (MoM) document.
    
    TRANSCRIPT:
    {conversation_text}
    
    OUTPUT FORMAT (Markdown):
    # Minutes of Meeting - Barbie Builders
    
    ## 1. Call Summary
    (A brief 2-3 sentence summary of the call)
    
    ## 2. Customer Details
    - **Intent:** (Buying/Selling/Inquiry)
    - **Key Interests:** (Location, Budget, Type)
    
    ## 3. Key Discussion Points
    - (Bulleted list of main topics discussed)
    
    ## 4. Action Items / Next Steps
    - [ ] (What needs to be done next)
    
    ## 5. Sentiment Analysis
    (Positive/Neutral/Negative)
    """

    try:
        loop = asyncio.get_running_loop()
        
        def _run_mom_sync():
            response = mom_model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(temperature=0.3)
            )
            return response.text

        mom_text = await loop.run_in_executor(None, _run_mom_sync)
        return mom_text

    except Exception as e:
        return f"❌ Failed to generate MoM: {e}"

if __name__ == "__main__":
    async def main():
        print("Testing...")
    asyncio.run(main())