# AIChatbotInterface
# Travel Plan Agent - AI Chatbot Interface

An AI-powered travel planning agent built with FastAPI and Ollama.

## Features

- FastAPI-based REST API
- Integration with Ollama LLM
- Travel planning crew agents
- Dockerized for easy deployment

## Prerequisites

- Python 3.12+
- Ollama installed and running
- Docker (for containerization)

## Installation

### 1. Clone the repository

\`\`\`bash
git clone https://github.com/YOUR_USERNAME/TravelPlanAgent.git
cd TravelPlanAgent/AIChatbotInterface
\`\`\`

### 2. Create virtual environment

\`\`\`bash
python -m venv .venv312
.venv312\Scripts\activate  # Windows
# source .venv312/bin/activate  # Linux/Mac
\`\`\`

### 3. Install dependencies

\`\`\`bash
pip install -r requirements.txt
\`\`\`

### 4. Configure environment variables

\`\`\`bash
cp .env.example .env
# Edit .env with your actual configuration
\`\`\`

### 5. Start Ollama

Make sure Ollama is running on your system:
\`\`\`bash
ollama serve
\`\`\`

### 6. Run the application

\`\`\`bash
python APIAgent.py
# Or
uvicorn APIAgent:app --reload
\`\`\`

The API will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Docker Deployment

### Build the image

\`\`\`bash
docker build -t travel-plan-agent .
\`\`\`

### Run the container

\`\`\`bash
docker run -d -p 8000:8000 \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  --name travel-agent \
  travel-plan-agent
\`\`\`

### Using Docker Compose

\`\`\`bash
docker-compose up -d
\`\`\`

## Project Structure

\`\`\`
AIChatbotInterface/
├── agents/
│   └── travel_crew_planner.py
├── models/
│   └── ollamaLLM.py
├── APIAgent.py
├── TravelPlanAgent.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
\`\`\`
