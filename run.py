"""Entry point: starts the Rithmomachia game server."""

import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run("server.app:app", host="0.0.0.0", port=port)
