# Navdristi
Real-time edge AI navigation assistant for visually impaired users — YOLOv8-based multi-task CV pipeline (obstacle, road-crossing, currency, pothole detection) with distributed ZeroMQ inference and TTS audio feedback, running fully offline on Raspberry Pi 4.

📌 Overview
NavDrishti is a real-time edge AI system built on Raspberry Pi 4 that transforms a traditional white cane into an intelligent navigation assistant for visually impaired users. It runs multiple specialized computer vision models in parallel — detecting obstacles, reading currency, identifying road-crossing opportunities, and flagging potholes — all while delivering instant audio feedback through a text-to-speech (TTS) interface.
The system is designed to run entirely on-device with no internet dependency, making it reliable in real-world environments where connectivity is inconsistent.

✨ Features

👁️ Real-time Object Detection — YOLOv8-based obstacle detection with sub-second inference latency on CPU hardware
🛣️ Multi-task CV Pipeline — parallel specialized models for:

General navigation & obstacle avoidance
Road-crossing safety detection
Indian currency note recognition
Pothole & uneven surface detection


🔊 Instant TTS Audio Feedback — context-aware voice alerts describing the environment in real time
⚡ Distributed Inference Architecture — ZeroMQ + FastAPI + WebSockets for parallel multi-worker processing
📡 React Dashboard — companion web interface for caretakers to monitor device status and session logs
🔌 Fully Offline — runs end-to-end on Raspberry Pi 4 with no cloud dependency


🛠️ Tech Stack
LayerTechnologiesHardwareRaspberry Pi 4B, Camera Module, SpeakerObject DetectionYOLOv8 (custom-trained models)Inference BackendPython, FastAPIMessagingZeroMQ (multi-worker task queue)Real-time CommWebSocketsTTSpyttsx3 / gTTSCompanion UIReactLanguagePython 3.10+

🏗️ Architecture
Camera Input (Raspberry Pi)
        │
        ▼
  Frame Capture & Preprocessing
        │
        ▼
  ZeroMQ Task Distributor
  ┌─────┼─────┬──────┐
  ▼     ▼     ▼      ▼
YOLO  Road  Currency Pothole
Nav   Cross  Model   Model
Worker Worker Worker Worker
  └─────┼─────┴──────┘
        │
        ▼
  Result Aggregator (FastAPI)
        │
        ▼
  Context Engine
  (Priority + Deduplication)
        │
        ▼
  TTS Audio Output ──► User (via Speaker)
        │
        ▼
  WebSocket Stream ──► React Dashboard (Caretaker)

🚀 Getting Started
Hardware Requirements

Raspberry Pi 4B (4GB RAM recommended)
Raspberry Pi Camera Module v2 or USB webcam
Speaker or 3.5mm audio output
Power bank (for portable use)

Software Setup
bash# Clone the repository
git clone https://github.com/Shubhamshukla2611/NavDrishti.git
cd NavDrishti

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the main pipeline
python main.py
Companion Dashboard Setup
bashcd dashboard

# Install dependencies
npm install

# Start React dashboard
npm run dev

📂 Project Structure
NavDrishti/
├── models/
│   ├── nav_model.pt          # General navigation YOLO model
│   ├── road_cross_model.pt   # Road-crossing detection model
│   ├── currency_model.pt     # Indian currency recognition model
│   └── pothole_model.pt      # Pothole detection model
│
├── workers/
│   ├── nav_worker.py         # Navigation inference worker
│   ├── road_worker.py        # Road-crossing worker
│   ├── currency_worker.py    # Currency detection worker
│   └── pothole_worker.py     # Pothole detection worker
│
├── core/
│   ├── frame_capture.py      # Camera input & preprocessing
│   ├── task_distributor.py   # ZeroMQ task queue
│   ├── result_aggregator.py  # Merge + prioritize worker outputs
│   ├── context_engine.py     # Deduplication & alert logic
│   └── tts_engine.py         # Text-to-speech output
│
├── api/
│   ├── main.py               # FastAPI app
│   └── websocket.py          # WebSocket stream for dashboard
│
├── dashboard/                # React companion UI
│   └── src/
│       ├── App.jsx
│       └── components/
│
├── main.py                   # Entry point
└── requirements.txt

🤖 CV Models
ModelTaskTraining DataNavigation ModelGeneral obstacle detection & path clearanceCustom + COCO subsetRoad Crossing ModelVehicle detection, pedestrian signal recognitionCustom annotated datasetCurrency ModelIndian currency note classification (₹10 to ₹2000)Custom collected datasetPothole ModelUneven surface & pothole detectionCustom annotated street data
All models are fine-tuned YOLOv8 variants optimized for inference on Raspberry Pi 4 CPU.

⚡ Performance
MetricValueEnd-to-end latency< 1 second per frameParallel inference workers4 (one per task)HardwareRaspberry Pi 4B (CPU only)Connectivity requiredNone (fully offline)


🔮 Future Improvements

 GPS integration for outdoor route guidance
 Indoor navigation using depth estimation
 Multilingual TTS support (Hindi, Tamil, Bengali, etc.)
 Vibration haptic feedback module
 Mobile companion app for caretakers
 Cloud sync for session logs and analytics


💡 Motivation
Over 12 million people in India are visually impaired. Most assistive technology is either too expensive or too dependent on internet connectivity to be practical in day-to-day Indian environments. NavDrishti was built to be affordable, offline-first, and genuinely useful — running on a ₹4000 Raspberry Pi with no recurring cloud costs.
