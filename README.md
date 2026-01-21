# Open Alpha Arena

<img width="3840" height="1498" alt="image" src="https://github.com/user-attachments/assets/dac4b5d1-3da7-4b54-97e5-cef226d99547" />

<img width="2882" height="1792" alt="image" src="https://github.com/user-attachments/assets/66a5283b-3761-4992-82d1-8cd01f4d518d" />

This is a project inspired by [nof1 Alpha Arena](https://nof1.ai), you can setup AI trading bot on crypto market.

DONE:
- Paper Trading
- OpenAI compatible API
- LEVERAGE
- ccxt for quotation

TODO:
- real trading (actually you can implement it with ccxt by the help of AI coding tools easily)

## Star History

<a href="https://www.star-history.com/#etrobot/open-alpha-arena&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=etrobot/open-alpha-arena&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=etrobot/open-alpha-arena&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=etrobot/open-alpha-arena&type=date&legend=top-left" />
 </picture>
</a>

## Getting Started

### Prerequisites
- Node.js 18+
- pnpm (Global install: `npm install -g pnpm`)
- Python 3.10+
- uv (Global install: `pip install uv`)

### Install
```bash
# install JS deps and sync Python env
pnpm run install:all
```

### Configuration (Deepseek & AI Models)
The project is pre-configured to use **Deepseek** as the default LLM provider.

1. **New Accounts**: By default, new accounts created in the UI will use the Deepseek configuration (`https://api.deepseek.com`).
2. **Existing Accounts**: Update your model settings via the UI: `Settings` -> `Model Configuration`.
3. **API Key**: Ensure you have a valid API Key. You can set a default key in the source code (`backend/services/ai_decision_service.py` top constant `DEMO_API_KEYS`) or input it when creating an account.

### Development
By default, the workspace scripts launch:
- Backend on port 5611
- Frontend on port 5621

Start both dev servers:
```bash
pnpm run dev
```

> **Note on Startup**: You might see connection errors (ECONNREFUSED) in the terminal immediately after starting. This is normal as the frontend starts faster than the backend. Wait for the "WebSocket connected" message in the browser console.

Open:
- Frontend: http://localhost:5621
- Backend API Docs: http://localhost:5611/docs

### Troubleshooting
- **Frontend 500 / Connection Failed**: The backend is not fully ready. Wait a few seconds and refresh the page.
- **WebSocket Error**: If the connection drops, the frontend will attempt to reconnect automatically.

### Build
```bash
# build frontend; backend has no dedicated build step
pnpm run build
```
Static assets for the frontend are produced by Vite. The backend is a standard FastAPI app that can be run with Uvicorn or any ASGI server.

## License
MIT


[![Powered by DartNode](https://dartnode.com/branding/DN-Open-Source-sm.png)](https://dartnode.com "Powered by DartNode - Free VPS for Open Source")
