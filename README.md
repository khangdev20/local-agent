# ⚡ Local AI Coding Agent

AI Agent chạy hoàn toàn **local**, không gửi data ra ngoài. Dùng Ollama + Open Source LLM để điều khiển máy tính và hỗ trợ lập trình.

## Tính năng

- 🤖 **ReAct Loop** — suy luận + hành động lặp lại cho đến khi hoàn thành task
- 🖥️ **CLI đẹp** — terminal UI với Rich, streaming real-time
- 🌐 **Web UI** — giao diện chat với WebSocket, dark theme
- 🛠️ **12 Tools sẵn có** — shell, file ops, code runner, web search, git
- 🧠 **Memory** — short-term (context) + long-term (SQLite)
- 🔒 **Safety Gate** — xác nhận trước khi chạy lệnh nguy hiểm
- 🪟 **Cross-platform** — Windows (PowerShell) + Linux/Mac (bash)

## Cài đặt nhanh

### 1. Cài Ollama

**Linux/Mac:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:** Tải từ https://ollama.com → cài đặt như ứng dụng thông thường

### 2. Pull model

```bash
# Khuyến nghị cho coding (cần ~5GB disk)
ollama pull qwen2.5-coder:7b

# Hoặc model nhẹ hơn (cần ~4GB)
ollama pull codellama:7b

# Model mạnh hơn (cần ~9GB)
ollama pull qwen2.5-coder:14b
```

### 3. Clone & cài dependencies

```bash
git clone <repo-url>
cd local-agent
python setup.py          # kiểm tra môi trường + cài deps

# Hoặc thủ công:
pip install -r requirements.txt
```

### 4. Chạy

```bash
# Start Ollama (nếu chưa chạy)
ollama serve

# CLI interactive
python main.py

# One-shot task
python main.py "đọc file main.py và giải thích"

# Web UI
python main.py --web
# → mở http://localhost:8000
```

## Sử dụng CLI

```bash
# Interactive mode
python main.py

# One-shot với model cụ thể
python main.py "viết unit test cho auth.py" --model qwen2.5-coder:14b

# Bỏ qua xác nhận (dùng cẩn thận)
python main.py --yes "clean cache và build lại"

# Xem lịch sử chat
python main.py history

# Liệt kê models đã cài
python main.py models
```

### Lệnh trong interactive mode

| Lệnh | Mô tả |
|------|-------|
| `/exit` | Thoát |
| `/history` | Xem lịch sử gần đây |
| `/clear` | Xóa memory context |
| `/models` | Danh sách models |

## Web UI

```bash
python main.py --web --port 8000
```

Mở http://localhost:8000

**Tính năng Web UI:**
- Chat interface với WebSocket streaming
- Xem từng step của agent (click để expand)
- Toggle auto-confirm cho actions
- Đổi model realtime
- Xóa memory

## Tools

| Tool | Mô tả | Cần confirm? |
|------|-------|--------------|
| `run_shell` | Chạy bash/PowerShell | ✅ Có (nếu rm, sudo, v.v.) |
| `read_file` | Đọc file (có line numbers) | ❌ |
| `write_file` | Ghi file | ✅ Luôn |
| `patch_file` | Thay thế string trong file | ❌ |
| `list_dir` | Liệt kê thư mục | ❌ |
| `search_files` | Tìm text trong files | ❌ |
| `run_python` | Chạy Python code | ✅ Có |
| `run_nodejs` | Chạy Node.js code | ✅ Có |
| `web_search` | Tìm kiếm DuckDuckGo | ❌ |
| `git_status` | Git status | ❌ |
| `git_diff` | Git diff | ❌ |
| `git_log` | Git log | ❌ |

## Thêm tool mới

1. Tạo file `agent/tools/my_tool.py`:

```python
async def my_tool(arg1: str, arg2: int = 5) -> str:
    # logic của bạn
    return "result"
```

2. Đăng ký trong `agent/tools/registry.py`:

```python
from agent.tools.my_tool import my_tool

TOOLS["my_tool"] = {
    "fn": my_tool,
    "description": "Mô tả ngắn gọn cho LLM hiểu",
    "args": {"arg1": "string", "arg2": "int (optional)"},
    "dangerous": False,
}
```

Vậy là xong — agent tự động biết dùng tool mới.

## Cấu hình

Chỉnh `config/default.yaml` hoặc dùng biến môi trường:

```bash
AGENT_MODEL=qwen2.5-coder:14b
OLLAMA_URL=http://localhost:11434
```

## Models được khuyến nghị

| Model | VRAM | Tốc độ | Chất lượng code |
|-------|------|--------|-----------------|
| `qwen2.5-coder:7b` | ~5GB | Nhanh | ⭐⭐⭐⭐ |
| `qwen2.5-coder:14b` | ~10GB | Vừa | ⭐⭐⭐⭐⭐ |
| `deepseek-coder-v2:16b` | ~12GB | Chậm | ⭐⭐⭐⭐⭐ |
| `codellama:7b` | ~5GB | Nhanh | ⭐⭐⭐ |

**Không có GPU?** Chạy CPU-only (chậm hơn ~5-10x):
```bash
ollama pull qwen2.5-coder:3b  # model 3B nhẹ hơn cho CPU
```

## Kiến trúc

```
main.py
├── interfaces/
│   ├── cli.py           # Rich terminal UI
│   └── web/
│       ├── api.py       # FastAPI + WebSocket
│       └── static/      # HTML/CSS/JS frontend
├── agent/
│   ├── core.py          # ReAct orchestrator
│   ├── memory.py        # Short + long-term memory
│   └── tools/
│       ├── registry.py  # Tool registry
│       ├── shell.py     # bash/PowerShell
│       ├── file_ops.py  # File read/write/search
│       ├── code_runner.py # Python/Node.js
│       ├── web_search.py  # DuckDuckGo
│       └── git_ops.py   # Git commands
└── safety/
    └── confirm.py       # Human-in-the-loop gate
```

## License

MIT — dùng thoải mái, không cần credit.
