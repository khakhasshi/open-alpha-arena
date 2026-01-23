# Deployment Guide for NAQL Trading System

## Quick Start

### 1. Local Setup (First Time)

```bash
# Clone the repository
git clone <repo-url>
cd open-alpha-arena

# Copy the example env file and fill in your actual API keys
cp .env.example .env

# Edit .env and add your actual API keys:
# - OPENAI_API_KEY
# - DEEPSEEK_API_KEY
# - QWEN_API_KEY
nano .env
```

### 2. Deploy to Server (Automatic)

The easiest way is to use the automatic deployment script:

```bash
./auto_deploy.sh
```

This script will:
- Build the frontend
- Package all assets
- Copy your `.env` file with API keys
- Sync everything to the server (`root@60.205.245.226:project/LLMtrade`)
- Start the service on port 7006

### 3. Manual Deployment (If Needed)

If you prefer more control:

```bash
# Step 1: Build frontend locally
cd frontend
pnpm install
pnpm build
cd ..

# Step 2: Copy .env file to backend
cp .env backend/.env

# Step 3: Sync to server
rsync -avz --exclude '.venv' --exclude 'data.db' --exclude '__pycache__' \
  backend/ root@60.205.245.226:project/LLMtrade/

# Step 4: SSH to server and start manually
ssh root@60.205.245.226

# On the server:
cd project/LLMtrade
source .env  # Load API keys
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
nohup ./.venv/bin/python main.py > server.log 2>&1 &
```

## Server Management

### View Logs
```bash
ssh root@60.205.245.226
tail -f project/LLMtrade/server.log
```

### Stop the Server
```bash
ssh root@60.205.245.226
pkill -f "python.*main.py"
```

### Restart the Server
```bash
ssh root@60.205.245.226
pkill -f "python.*main.py"
cd project/LLMtrade
source .env
nohup ./.venv/bin/python main.py > server.log 2>&1 &
```

## Security Notes

⚠️ **Important**:
- **Never commit `.env` file to Git!** It contains your API keys.
- The `.env` file is in `.gitignore` for security.
- Use `.env.example` as a template for the `.env` file.
- The deployment script automatically copies `.env` to the server.

## Accessing the Application

Once deployed, access the application at:
- **URL**: `http://60.205.245.226:7006`
- **Local (dev)**: `http://localhost:5621` (frontend) and `http://localhost:5611` (backend)

## Troubleshooting

### Service won't start
```bash
# Check logs on server
tail -n 50 project/LLMtrade/server.log

# Check if port 7006 is in use
lsof -i :7006
```

### API Keys not loaded
Make sure `.env` file exists in the backend directory:
```bash
ls -la project/LLMtrade/.env
```

### Frontend not loading
Check if static files are in place:
```bash
ls -la project/LLMtrade/static/
```

## API Models Available

The system includes three AI models:

1. **GPT (OpenAI)** - `gpt-3.5-turbo`
   - Endpoint: `https://api.openai.com/v1`
   - Key: Set via `OPENAI_API_KEY`

2. **DeepSeek** - `deepseek-chat`
   - Endpoint: `https://api.deepseek.com`
   - Key: Set via `DEEPSEEK_API_KEY`

3. **Qwen (通义千问)** - `qwen-plus`
   - Endpoint: `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
   - Key: Set via `QWEN_API_KEY`

Each model gets its own trading account with $10,000 starting capital.
