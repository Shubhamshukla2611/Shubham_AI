# Terravision
AI-powered urban sustainability platform — real-time environmental map layers, radius-based geospatial filtering, Gemini AI insights, and policy impact simulation dashboards. Built with FastAPI + React.
📌 Overview
TerraVision is an AI-powered urban sustainability platform that helps analysts, policymakers, and researchers visualize and understand environmental data at a regional level. It combines real-time geospatial data processing, Gemini AI-driven insights, and interactive dashboards to turn raw environmental data into actionable intelligence.
Built as a full-stack system with a FastAPI backend and React frontend, TerraVision makes environmental analysis accessible and intelligent.

✨ Features

🗺️ Real-time Environmental Map Layers — visualize air quality, green cover, heat zones, and more across city regions
📍 Radius-based Geospatial Filtering — query and analyze sustainability metrics for any custom region on the map
🤖 Gemini AI Insights — AI-generated environmental summaries, trend analysis, and anomaly detection for selected regions
📊 Policy Impact Simulation Dashboards — model the effect of urban policies on sustainability scores
⚡ FastAPI Microservices — modular, scalable backend powering all data pipelines and AI endpoints
🔥 Firebase Integration — real-time data sync and storage for environmental records


🛠️ Tech Stack
LayerTechnologiesFrontendReact 18, Tailwind CSSBackendFastAPI, Python 3.10+AI / LLMGoogle Gemini AIDatabaseFirebase FirestoreMaps & GeoGeospatial APIs, Radius FilteringDeploymentUvicorn, Firebase Hosting

🏗️ Architecture
User (Browser)
     │
     ▼
React Frontend (Map UI + Dashboards)
     │
     ▼
FastAPI Backend (Microservices)
     ├── /api/map-layers       → Real-time env. data layers
     ├── /api/spatial-filter   → Radius-based region queries
     ├── /api/ai-insights      → Gemini AI analysis endpoint
     └── /api/policy-sim       → Policy impact simulation
     │
     ├── Firebase Firestore (env. data storage)
     └── Google Gemini AI (insight generation)

🚀 Getting Started
Prerequisites

Python 3.10+
Node.js 18+
Firebase project with Firestore enabled
Google Gemini API key

Backend Setup
bash# Clone the repository
git clone https://github.com/Shubhamshukla2611/TerraVision.git
cd TerraVision/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Add your GEMINI_API_KEY and Firebase credentials in .env

# Run the server
uvicorn main:app --reload
Frontend Setup
bashcd ../frontend

# Install dependencies
npm install

# Start development server
npm run dev

📂 Project Structure
TerraVision/
├── backend/
│   ├── main.py                 # FastAPI app entry point
│   ├── routers/
│   │   ├── map_layers.py       # Environmental map layer APIs
│   │   ├── spatial_filter.py   # Geospatial filtering logic
│   │   ├── ai_insights.py      # Gemini AI integration
│   │   └── policy_sim.py       # Policy simulation endpoints
│   ├── services/
│   │   ├── gemini_service.py   # Gemini API wrapper
│   │   └── firebase_service.py # Firestore operations
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── MapView.jsx      # Interactive map component
│   │   │   ├── Dashboard.jsx    # Policy simulation dashboard
│   │   │   └── InsightPanel.jsx # AI insights display
│   │   └── App.jsx
│   └── package.json
│
└── README.md

🤖 AI Capabilities
TerraVision uses Google Gemini AI to:

Generate natural language summaries of regional environmental conditions
Detect anomalies in sustainability metrics (sudden spikes in pollution, heat zones, etc.)
Suggest data-driven policy recommendations based on current trends
Translate raw geospatial data into human-readable insights for non-technical stakeholders



🔮 Future Improvements

 Add historical trend analysis with time-series visualization
 Integrate satellite imagery for real-time land-use monitoring
 Add predictive ML models for sustainability forecasting
 Export reports as PDF for policymakers
 Multi-city comparison dashboard


