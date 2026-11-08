"""
Universal cross-platform launcher for NOVA (Windows, macOS, Linux).
Usage: python run.py [--host 127.0.0.1] [--port 46815] [--no-browser]
"""
import argparse
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def open_browser_later(url: str, delay: float = 1.8) -> None:
    def _runner():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=_runner, daemon=True).start()


def main() -> int:
    if sys.version_info < (3, 11):
        print(f"[ERROR] Python 3.11+ required (detected {sys.version.split()[0]}).")
        return 1

    root_dir = Path(__file__).resolve().parent
    os.chdir(root_dir)
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))
    os.environ["PYTHONPATH"] = str(root_dir)

    parser = argparse.ArgumentParser(description="NOVA AI Workstation Launcher")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=46815, help="Bind port (default: 46815)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    args = parser.parse_args()

    check_host = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    if is_port_in_use(check_host, args.port):
        print(f"[ERROR] Port {args.port} is already in use on {check_host}.")
        print("Stop the running instance (stop.bat / ./stop.sh) or specify --port.")
        return 1

    try:
        import uvicorn
    except ImportError:
        print("[ERROR] Required dependencies are not installed. Run: pip install -r requirements.txt")
        return 1

    url = f"http://{check_host}:{args.port}"
    print("=" * 68)
    print("  NOVA -- Autonomous Local AI Agent & Workstation")
    print(f"  Platform : {sys.platform} | Python {sys.version.split()[0]}")
    print(f"  Endpoint : {url}")
    print("=" * 68)

    if not args.no_browser:
        open_browser_later(url)

    uvicorn.run("backend.app.main:app", host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
