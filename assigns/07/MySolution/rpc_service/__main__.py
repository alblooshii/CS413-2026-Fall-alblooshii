"""Start the service: python -m rpc_service  (127.0.0.1:8000, PORT overrides)."""

import logging
import os

from .app import create_app

# The guard matters: spawned worker processes re-import this module.
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    create_app().run(host="127.0.0.1", port=int(os.environ.get("PORT", "8000")), threaded=True)
