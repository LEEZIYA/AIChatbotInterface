# 🐳 Docker Setup Guide for Rescue Agent MCP

This guide will help you run your Rescue Agent in a Docker container.

---

## 📋 Prerequisites

### **Install Docker Desktop:**

1. Download from: https://www.docker.com/products/docker-desktop
2. Install Docker Desktop for Windows
3. Start Docker Desktop
4. Wait for Docker to fully start (check system tray)

### **Verify Docker is running:**

```cmd
docker --version
docker-compose --version
```

You should see version numbers like:
```
Docker version 24.x.x
Docker Compose version 2.x.x
```

---

## 🚀 Quick Start (3 Steps)

### **Step 1: Add Docker Files**

Copy these 3 files to your project folder:
```
rescue_agent_mcp/
├── Dockerfile              ← Download this
├── docker-compose.yml      ← Download this
└── .dockerignore           ← Download this
```

### **Step 2: Make Sure .env Exists**

```cmd
cd C:\Users\Owner\Downloads\rescue_agent_mcp\rescue_agent_mcp
type .env
```

Should show your API key. If not:
```cmd
copy .env.example .env
notepad .env
```

Add your OpenAI key:
```
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxx
USE_MCP=true
USE_MOCK_APIS=true
```

### **Step 3: Run with Docker Compose**

```cmd
docker-compose up
```

**That's it!** 🎉

Open browser: http://localhost:8501

---

## 📚 Docker Commands

### **Start the agent:**
```cmd
docker-compose up
```

### **Start in background (detached):**
```cmd
docker-compose up -d
```

### **Stop the agent:**
```cmd
docker-compose down
```

### **View logs:**
```cmd
docker-compose logs -f
```

### **Rebuild after code changes:**
```cmd
docker-compose up --build
```

### **Check if container is running:**
```cmd
docker ps
```

---

## 🔧 Manual Docker Build (Alternative)

If you don't want to use docker-compose:

### **Build the image:**
```cmd
docker build -t rescue-agent-mcp .
```

### **Run the container:**
```cmd
docker run -p 8501:8501 --env-file .env rescue-agent-mcp
```

### **Run with environment variables:**
```cmd
docker run -p 8501:8501 ^
  -e OPENAI_API_KEY=sk-proj-xxxxx ^
  -e USE_MCP=true ^
  -e USE_MOCK_APIS=true ^
  rescue-agent-mcp
```

---

## 🐛 Troubleshooting

### **Problem: "Docker daemon is not running"**

**Solution:**
1. Open Docker Desktop
2. Wait for it to start fully
3. Look for green "running" indicator in system tray
4. Try command again

### **Problem: "Port 8501 already in use"**

**Solution:**

Stop your non-Docker Streamlit:
```cmd
# Find the process
netstat -ano | findstr :8501

# Kill it (replace PID with actual number)
taskkill /PID <PID> /F
```

Or change the port in `docker-compose.yml`:
```yaml
ports:
  - "8502:8501"  # Use port 8502 instead
```

Then go to: http://localhost:8502

### **Problem: "OPENAI_API_KEY not configured"**

**Solution:**

Make sure `.env` file exists and has your real key:
```cmd
type .env
```

Should show:
```
OPENAI_API_KEY=sk-proj-xxxxx...
```

### **Problem: Build fails with "requirements not found"**

**Solution:**

Make sure you're in the right directory:
```cmd
cd C:\Users\Owner\Downloads\rescue_agent_mcp\rescue_agent_mcp
dir
```

You should see:
- requirements.txt
- Dockerfile
- src/
- chat_interface.py

---

## 📊 What's Different with Docker?

| Without Docker (venv) | With Docker |
|----------------------|-------------|
| `venv\Scripts\activate` | `docker-compose up` |
| Python on your PC | Python in container |
| Files on C: drive | Files in container |
| Faster startup | Slower startup |
| Easy to debug | More isolated |
| Manual setup | Reproducible |

---

## 🎯 When to Use Docker

### **Use Docker when:**
- ✅ Deploying to production
- ✅ Sharing with team (ensures same environment)
- ✅ Running on a server
- ✅ Want consistent setup

### **Use venv when:**
- ✅ Development & debugging
- ✅ Quick testing
- ✅ Learning & experimenting
- ✅ Your school project demos

---

## 🚀 Production Deployment

### **For cloud deployment (AWS, Azure, GCP):**

1. Build and push to container registry:
```cmd
docker build -t your-registry/rescue-agent:latest .
docker push your-registry/rescue-agent:latest
```

2. Deploy to cloud service
3. Set environment variables in cloud console
4. Configure domain and SSL

### **For local server:**

```cmd
# Run in background
docker-compose up -d

# Check logs
docker-compose logs -f

# Auto-restart on system reboot (already configured in docker-compose.yml)
```

---

## 📝 Docker vs Python Comparison

### **What you've been doing (Python venv):**
```cmd
venv\Scripts\activate
streamlit run chat_interface.py
```

### **With Docker (new way):**
```cmd
docker-compose up
```

**Both work! Docker is just more "professional" and easier to deploy.** 🎉

---

## 🎊 Summary

**To run with Docker:**

1. Install Docker Desktop
2. Copy 3 files (Dockerfile, docker-compose.yml, .dockerignore)
3. Make sure .env has your API key
4. Run: `docker-compose up`
5. Open: http://localhost:8501

**That's it!** Your rescue agent is now running in a Docker container! 🐳

---

## 💡 Pro Tip

Keep both setups:
- **Use venv for development** (faster, easier to debug)
- **Use Docker for demos/deployment** (more professional, consistent)

You can switch between them anytime! 🔄
