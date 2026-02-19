# AI Voice Agent (CPaaS)
### Team: Barbie
### Event: UDYAM'26 - DevBits

> A contextual, low-latency AI receptionist and sales agent for Real Estate, capable of handling interruptions and generating Minutes of Meeting (MoM).

---

## 📖 Overview
This project is an **AI-Powered Customer Engagement Platform** designed to automate Inbound and Outbound calls for a real estate company ("Barbie Builders"). The system acts as a Smart Receptionist that qualifies leads, answers queries about properties (Apartments, Villas, Plots), and automatically generates a PDF summary of the conversation.

### ✨ Key Features
* [cite_start]**Contextual Intelligence:** Powered by **Gemini 2.5 Flash**, the agent understands location context (Noida/Gurgaon) and user intent[cite: 31, 43].
* [cite_start]**Low Latency:** Uses streaming responses (Piper TTS + Gemini Streaming) to achieve conversational speeds < 2 seconds[cite: 121].
* [cite_start]**Barge-In Support:** The agent stops speaking immediately if the user interrupts, mimicking natural human conversation.
* [cite_start]**Automated MoM:** Generates a structured **Minutes of Meeting PDF** containing customer details, budget, and action items immediately after the call[cite: 50, 131].
* **Full Duplex Audio:** Utilizes Asterisk External Media (RTP) for raw audio processing.

---

## 🏗️ Architecture

**Data Flow:**
1.  **Telephony:** Asterisk handles the SIP call.
2.  **Audio Stream:** Audio is piped via RTP (External Media) to `whisper_listener.py`.
3.  **STT:** **Faster-Whisper** with **Silero VAD** transcribes speech and detects interruptions.
4.  **Brain:** The transcript is sent to **Gemini 2.5 Flash**, which streams a text response.
5.  **TTS:** **Piper** (running locally) converts the text stream to audio and sends RTP packets back to Asterisk.
6.  **Orchestrator:** `ari.py` manages the call state via WebSocket.

---

## 🛠️ Tech Stack
| Component | Technology | Description |
| :--- | :--- | :--- |
| **LLM** | Google Gemini 2.5 Flash | Logic, conversation, and MoM generation |
| **Telephony** | Asterisk (v18+) | SIP Server & ARI (Asterisk REST Interface) |
| **STT** | Faster-Whisper | Low-latency speech-to-text |
| **TTS** | Piper | Neural text-to-speech (running specifically `en_US-amy-medium`) |
| **VAD** | Silero VAD | Voice Activity Detection for Barge-in |
| **PDF Engine** | WeasyPrint | HTML to PDF conversion for MoM |
| **Language** | Python 3.10+ | Core application logic |

---

## 🚀 Setup Instructions

### 1. Prerequisites
* Python 3.10+ installed.
* **Asterisk** installed and running.
* **Piper** binary downloaded and placed in `./piper/piper`.
* Piper Model (`en_US-amy-medium.onnx`) placed in `./models/`.

### 2. Installation
Clone the repository and install dependencies:
```bash
git clone <your-repo-url>
cd <your-repo-folder>
pip install -r requirements.txt
