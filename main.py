#!/usr/bin/env python3
"""
Main entrypoint — chạy CLI hoặc Web server.

Usage:
  python main.py                     # CLI interactive mode
  python main.py "fix bug in main.py" # one-shot task
  python main.py --web               # start Web UI
  python main.py --web --port 8080   # web on custom port
"""
import sys
import argparse
import asyncio


def main():
    parser = argparse.ArgumentParser(
        description="Local AI Coding Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                          # interactive CLI
  python main.py "đọc file main.py"       # one-shot
  python main.py --web                    # Web UI at http://localhost:8000
  python main.py --model qwen2.5:14b     # dùng model khác
  python main.py --yes "xóa cache"       # auto-confirm nguy hiểm
        """
    )
    parser.add_argument("task", nargs="?", help="Task (one-shot mode)")
    parser.add_argument("--web", action="store_true", help="Start Web UI server")
    parser.add_argument("--port", type=int, default=8000, help="Web server port")
    parser.add_argument("--host", default="0.0.0.0", help="Web server host")
    parser.add_argument("--model", default="qwen2.5-coder:7b", help="Ollama model")
    parser.add_argument("--url", default="http://localhost:11434", help="Ollama URL")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm actions")
    parser.add_argument("--max-steps", type=int, default=15, help="Max agent steps")

    args = parser.parse_args()

    if args.web:
        # Web UI mode
        import os
        os.environ["AGENT_MODEL"] = args.model
        os.environ["OLLAMA_URL"] = args.url

        import uvicorn
        print(f"\n🌐 Starting Web UI at http://{args.host}:{args.port}")
        print(f"   Model: {args.model}")
        print(f"   Press Ctrl+C to stop\n")
        uvicorn.run(
            "interfaces.web.api:app",
            host=args.host,
            port=args.port,
            reload=False,
        )
    else:
        # CLI mode
        import sys
        sys.argv = [sys.argv[0]]
        if args.task:
            sys.argv.append(args.task)
        if args.model != "qwen2.5-coder:7b":
            sys.argv.extend(["--model", args.model])
        if args.url != "http://localhost:11434":
            sys.argv.extend(["--url", args.url])
        if args.yes:
            sys.argv.append("--yes")
        if args.max_steps != 15:
            sys.argv.extend(["--max-steps", str(args.max_steps)])

        from interfaces.cli import app
        app()


if __name__ == "__main__":
    main()
