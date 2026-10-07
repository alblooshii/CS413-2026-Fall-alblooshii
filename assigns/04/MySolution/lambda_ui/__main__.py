"""Start the local server: ``python -m lambda_ui [--port N]``."""
import argparse

from .web import create_app

HOST = "127.0.0.1"      # loopback only; public hosting is out of scope


def main() -> None:
    parser = argparse.ArgumentParser(description="LAMBDA web front-end")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    print(f"Open http://{HOST}:{args.port}/ in your browser (Ctrl+C to stop).")
    create_app().run(host=HOST, port=args.port, threaded=True, debug=False)


if __name__ == "__main__":
    main()
