#!/usr/bin/env python3
import asyncio
import json
import glob
import time
import os
from pathlib import Path
from sarvamai import SarvamAI
from weasyprint import HTML
import gemini_thinker
from mom_pdf_template import render_mom_html
import shutil
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
RECORDINGS_DIR = BASE_DIR / "Recordings"
ENV_PATH = BASE_DIR / "API_Key.env"
load_dotenv(ENV_PATH)
API_KEY = os.getenv("SARVAM_API_KEY")

async def save_mom_as_pdf(mom_markdown: str, filename: str, caller_id: str = None):
    def _convert():
        html_str = render_mom_html(mom_markdown, caller_id=caller_id)
        HTML(string=html_str).write_pdf(filename)
    
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _convert)

async def sarvam_generate_mom():
    """Transcribe all audio files in Recordings folder + Generate MOM PDFs"""
    
    # Find all audio files
    audio_extensions = ['*.mp3', '*.wav']
    audio_files = []
    for ext in audio_extensions:
        audio_files.extend(RECORDINGS_DIR.glob(ext))
        audio_files.extend(RECORDINGS_DIR.glob(ext.upper()))
    
    if not audio_files:
        print(f"❌ No audio files found in: {RECORDINGS_DIR}")
        return
    
    print(f"📁 Found {len(audio_files)} files in {RECORDINGS_DIR}")
    for audio_file in audio_files:
        print(f"  📄 {audio_file.name}")
    
    # Sarvam AI setup
    client = SarvamAI(api_subscription_key=API_KEY)
    
    # Process each file
    for audio_path in audio_files:
        filename = audio_path.stem  # e.g., "meeting1"
        
        print(f"\n🔊 Processing: {audio_path.name}")
        
        job = client.speech_to_text_job.create_job(
            model="saaras:v3",
            mode="transcribe",
            # language_code="en-IN",
            with_diarization=True,
            num_speakers=2
        )
        
        audio_paths = [str(audio_path)]
        job.upload_files(file_paths=audio_paths)
        job.start()
        
        job.wait_until_complete()
        file_results = job.get_file_results()
        
        if not file_results['successful']:
            print(f"❌ Failed: {audio_path.name}")
            continue
        
        output_dir = BASE_DIR / "sarvam_output"
        output_dir.mkdir(exist_ok=True)
        job.download_outputs(output_dir=str(output_dir))
        
        # Process first successful JSON
        json_files = glob.glob(str(output_dir / "*.json"))
        if not json_files:
            print(f"❌ No JSON for: {audio_path.name}")
            continue
        
        json_file = json_files[0]
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        full_transcript = data.get('transcript', '')
        
        # Convert to your gemini_thinker format
        transcript_for_mom = [{"speaker": "user", "text": full_transcript, "timestamp": time.time()}]
        
        # Add diarization if available
        diarized = data.get('diarized_transcript', {}).get('entries', [])
        if diarized:
            transcript_for_mom = []
            for entry in diarized:
                speaker = f"SPEAKER_{entry.get('speaker_id', 0)}"
                text = entry.get('transcript', '')
                timestamp = entry.get('start_time_seconds', time.time())
                transcript_for_mom.append({"speaker": speaker, "text": text, "timestamp": timestamp})
        
        # print("🤖 GENERATING MOM...")
        mom_content = await gemini_thinker.generate_mom(transcript_for_mom)
        
        # Named PDF per file
        # timestamp = time.strftime("%Y%m%d_%H%M%S")
        pdf_filename = str(BASE_DIR / f"MoM for {filename}.pdf")
        
        await save_mom_as_pdf(mom_content, pdf_filename, caller_id=filename)
        
        print(f"✅MoM saved to: {pdf_filename}")

    shutil.rmtree(output_dir) # to delete json files
    print("DONE")    

if __name__ == "__main__":
    asyncio.run(sarvam_generate_mom())
