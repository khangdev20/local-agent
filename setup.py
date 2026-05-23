#!/usr/bin/env python3
"""
Setup script — cài đặt dependencies và kiểm tra môi trường.
Chạy: python setup.py
"""
import subprocess
import sys
import platform
import shutil


IS_WIN = platform.system() == "Windows"
GREEN = "\033[92m" if not IS_WIN else ""
RED   = "\033[91m" if not IS_WIN else ""
YELLOW = "\033[93m" if not IS_WIN else ""
RESET = "\033[0m"  if not IS_WIN else ""


def ok(msg): print(f"{GREEN}✓{RESET} {msg}")
def err(msg): print(f"{RED}✗{RESET} {msg}")
def warn(msg): print(f"{YELLOW}!{RESET} {msg}")


def check_python():
    v = sys.version_info
    if v >= (3, 10):
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        err(f"Python {v.major}.{v.minor} — cần 3.10+")
        sys.exit(1)


def check_ollama():
    if shutil.which("ollama"):
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        ok("Ollama installed")
        models = [l.split()[0] for l in result.stdout.strip().splitlines()[1:] if l.strip()]
        if models:
            ok(f"Models available: {', '.join(models)}")
        else:
            warn("No models installed. Run: ollama pull qwen3:8b")
    else:
        err("Ollama not found")
        print(f"\n  Install from: https://ollama.com\n")
        print("  Then run:")
        print("    ollama pull qwen3:8b\n")


def install_deps():
    print("\nInstalling Python dependencies...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        ok("Dependencies installed")
    else:
        err("Failed to install dependencies")
        print(result.stderr)
        sys.exit(1)


def check_node():
    if shutil.which("node"):
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        ok(f"Node.js {result.stdout.strip()} (for run_nodejs tool)")
    else:
        warn("Node.js not found — run_nodejs tool disabled")


def main():
    print(f"\n{'='*50}")
    print(f"  Local AI Coding Agent — Setup")
    print(f"  Platform: {platform.system()} {platform.machine()}")
    print(f"{'='*50}\n")

    check_python()
    check_ollama()
    check_node()
    install_deps()

    print(f"\n{'='*50}")
    print(f"{GREEN}Setup complete!{RESET}\n")
    print("Next steps:")
    print("  1. Start Ollama:     ollama serve")
    print("  2. Pull a model:     ollama pull qwen3:8b")
    print("  3. Run CLI:          python main.py")
    print("  4. Run Web UI:       python main.py --web")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
