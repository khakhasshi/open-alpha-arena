#!/bin/bash
set -e

echo "=== 1. Building Frontend ==="
cd frontend
pnpm install
pnpm build
cd ..

echo "=== 2. Preparing Backend Static Files ==="
# Clear old static files
if [ -d "backend/static" ]; then
    rm -rf backend/static
fi
mkdir -p backend/static

# Copy new build files
cp -r frontend/dist/* backend/static/
echo "Frontend built and copied to backend/static."

echo "=== 3. Deployment Instructions ==="
REMOTE_HOST="root@60.205.245.226"
# Target is ~project/LLMtrade. 
# ~project typically expands to /var/lib/project or /home/project. 
# But here we use the literal path from user request, assuming SSH handles ~project if user is not root, 
# or if it's a directory relative to root's home?
# "root@...:~project/LLMtrade" usually means user 'root', path relative to 'project' user home? 
# OR just a folder named '~project' in root's home.
# safer to treat it as a path string or ask user. 
# But assuming standard scp syntax: remote_user@host:path
REMOTE_PATH="~project/LLMtrade"

echo "The backend is now self-contained with the frontend."
echo "Configured to listen on port 7006."
echo ""
echo "To deploy, run the following command:"
echo "rsync -avz --exclude '__pycache__' --exclude '.venv' --exclude '.DS_Store' backend/ $REMOTE_HOST:$REMOTE_PATH"
echo ""
echo "After syncing:"
echo "1. SSH into the server: ssh $REMOTE_HOST"
echo "2. Navigate to directory: cd $REMOTE_PATH"
echo "3. Install dependencies: pip install -r requirements.txt"
echo "4. Run the server: python3 main.py"
echo "   (Or use nohup/systemd to keep it running: nohup python3 main.py > output.log 2>&1 &)"
