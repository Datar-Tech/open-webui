# Open WebUI Development Setup

This guide explains how to run the frontend and backend components of the Open WebUI application.

## Frontend Setup

### Prerequisites
- Node.js >= 18.13.0
- npm (Node Package Manager)

### Steps to Run Frontend
```bash
# Install dependencies
npm install

# Run development server
npm run dev
```

The frontend development server will start on http://localhost:5173 with auto-reload enabled.

## Backend Setup

### Prerequisites
- Python
- Virtual Environment tool (venv)

### Steps to Run Backend
```bash
# Navigate to backend directory
cd backend

# Create Python virtual environment
python -m venv venv

# Activate virtual environment (Windows)
.\venv\Scripts\activate

# Install requirements
pip install -r requirements.txt

### UV

# Create and activate a virtual environment
uv venv venv

# On Unix/Linux/macOS
# source venv/bin/activate

# On Windows
venv\Scripts\activate

# Installing requirements
uv pip install -r backend/requirements.txt

# Run the backend server (Windows)
.\start_windows.bat
```

The backend server will start on http://localhost:8080.

## Important Notes

- For Windows users: The backend's `start_windows.bat` script is not recommended. It's suggested to use `start.sh` with WSL instead.
- The frontend development server includes auto-reload functionality for a better development experience.
- The backend uses FastAPI with uvicorn server.
- Make sure all required dependencies are installed before running either component.


## Docker Build

- docker login
- docker build --build-arg BUILD_HASH=v1.3.8 -t tech-sense .
- docker tag tech-sense deliah/tech-sense:v1.3.8
- docker push deliah/tech-sense:v1.3.8
- docker tag tech-sense deliah/tech-sense:latest
- docker push deliah/tech-sense:latest

git tag -a v1.3.8 -m "Release v1.3.8"
git push origin v1.3.8

# Debug mode
$env:WEBUI_DEBUG=1 ; .\start_windows.bat

$env:WEBUI_DEBUG=1 ; python -m debugpy --listen 0.0.0.0:5678 --wait-for-client --log-to-stderr uvicorn open_webui.main:app --host "$env:HOST" --port "$env:PORT" --forwarded-allow-ips '*' --workers "$env:UVICORN_WORKERS" --ws auto
