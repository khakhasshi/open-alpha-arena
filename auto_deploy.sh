#!/bin/bash
set -e

# Configuration for Google Cloud Deployment
GCLOUD_ZONE="asia-east1-a"
GCLOUD_INSTANCE="instance-20260115-080017"
GCLOUD_PROJECT="festive-centaur-439907-s0"
REMOTE_PATH="~/LLMtrade"
REMOTE_PORT="80"

echo "=========================================="
echo "   NAQL Auto Deployment Script"
echo "   Target: gcloud $GCLOUD_INSTANCE"
echo "   Project: $GCLOUD_PROJECT"
echo "   Zone: $GCLOUD_ZONE"
echo "   Port: $REMOTE_PORT"
echo "=========================================="

# 1. Build Frontend
echo ""
echo "🏗️  [1/5] Building Frontend..."
cd frontend
pnpm install
pnpm build
cd ..

# 2. Prepare Static Files
echo ""
echo "📦 [2/5] Preparing Backend Assets..."
rm -rf backend/static
mkdir -p backend/static
cp -r frontend/dist/* backend/static/

# 3. Copy Environment Variables to Backend
echo ""
echo "🔐 [3/5] Preparing API Keys..."
if [ -f ".env" ]; then
    cp .env backend/.env
    echo "✅ API Keys file copied to backend"
else
    echo "⚠️ Warning: .env file not found. You must manually create it on the server."
fi

# 4. Create Remote Directory
echo ""
echo "📁 [4/5] Creating remote directory..."
gcloud compute ssh --zone "$GCLOUD_ZONE" \
    --project "$GCLOUD_PROJECT" \
    "$GCLOUD_INSTANCE" \
    --command="mkdir -p $REMOTE_PATH"

# 5. Sync to Server
echo ""
echo "🚀 [5/6] Syncing files to server via gcloud..."

# Use gcloud compute scp to upload the backend directory
gcloud compute scp --zone "$GCLOUD_ZONE" \
  --project "$GCLOUD_PROJECT" \
  --recurse \
  backend/ "$GCLOUD_INSTANCE:$REMOTE_PATH/"

# 5. Remote Restart
echo ""
echo "🔄 [6/6] Restarting Remote Service..."
gcloud compute ssh --zone "$GCLOUD_ZONE" \
    --project "$GCLOUD_PROJECT" \
    "$GCLOUD_INSTANCE" \
    --command="bash -s" <<'EOF'
    REMOTE_PATH="~/LLMtrade"
    REMOTE_PORT="80"
    
    # Ensure target directory exists
    mkdir -p $REMOTE_PATH
    cd $REMOTE_PATH || { echo "❌ Directory not found: $REMOTE_PATH"; exit 1; }
    
    echo "📂 Working directory: $(pwd)"
    
    # Load environment variables
    echo "🔐 Loading API Keys..."
    if [ -f ".env" ]; then
        set -a
        source .env
        set +a
        echo "✅ API Keys loaded from .env"
    else
        echo "⚠️ Warning: .env file not found. Backend will use placeholder keys."
    fi
    
    # Install dependencies
    echo "📦 Setting up Python environment..."
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi

    echo "📦 Installing Python dependencies into venv..."
    ./.venv/bin/pip install -r requirements.txt -q
    
    # Kill old process
    echo "🛑 Stopping existing service..."
    pkill -f "main.py" || true
    sleep 2
    
    # Start new process using sudo for port 80
    echo "▶️  Starting new service on port $REMOTE_PORT..."
    nohup sudo ./.venv/bin/python main.py > server.log 2>&1 &
    
    echo "⏳ Waiting for service initialization (15s)..."
    sleep 15
    
    # Check status and logs
    if pgrep -f "main.py" > /dev/null; then
        echo "✅ Service is RUNNING"
        echo "📝 Recent Server Logs (last 30 lines):"
        echo "----------------------------------------"
        tail -n 30 server.log
        echo "----------------------------------------"
    else
        echo "❌ Service failed to start. Check server.log:"
        tail -n 30 server.log
    fi
EOF

echo ""
echo "🎉 Deployment Process Finished!"
echo "👉 Access url: http://<instance-public-ip>/"
echo ""
echo "📝 Important Notes:"
echo "  - The server is running in the background (nohup)"
echo "  - Logs are stored in: $REMOTE_PATH/server.log"
echo "  - To stop the server: gcloud compute ssh --zone \"$GCLOUD_ZONE\" --project \"$GCLOUD_PROJECT\" \"$GCLOUD_INSTANCE\" --command=\"pkill -f 'python.*main.py'\""
echo "  - To view logs: gcloud compute ssh --zone \"$GCLOUD_ZONE\" --project \"$GCLOUD_PROJECT\" \"$GCLOUD_INSTANCE\" --command=\"tail -f $REMOTE_PATH/server.log\""
echo ""