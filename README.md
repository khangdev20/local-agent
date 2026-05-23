# ⚡ Local AI Coding Agent

AI Agent chạy hoàn toàn **local**, không gửi data ra ngoài. Dùng Ollama + Open Source LLM để điều khiển máy tính và hỗ trợ lập trình.

## Tính năng

- 🤖 **ReAct Loop** — suy luận + hành động lặp lại cho đến khi hoàn thành task
- 🖥️ **CLI đẹp** — terminal UI với Rich, streaming real-time
- 🌐 **Web UI** — giao diện chat với WebSocket, dark theme
- 🛠️ **18 Tools sẵn có** — shell, file ops, code runner, computer use, web search, git
- 🧠 **Memory** — short-term (context) + long-term (SQLite)
- 🔒 **Safety Gate** — xác nhận trước khi chạy lệnh nguy hiểm
- 🛡️ **Privacy Boundary** — chặn/confirm khi đụng secret, private key, `.env`, hoặc gửi query ra ngoài
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
# Orchestrator mặc định cho research/planning/điều phối
ollama pull qwen3:8b

# Tuỳ chọn cho coding nặng
ollama pull qwen2.5-coder:7b

# Model coding mạnh hơn
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

# Chạy default idle task: học system design, conventions, DevOps để áp dụng vào dự án
python main.py --default-task

# Web UI
python main.py --web
# → mở http://localhost:8000
```

## Sử dụng CLI

```bash
# Interactive mode
python main.py

# One-shot với model cụ thể
python main.py "nghiên cứu idea và lập plan MVP" --model qwen3:8b

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
| `/default` | Chạy default idle task |

Nhấn Enter ở prompt trống cũng sẽ chạy default idle task.

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
- Nút **Run Default** để agent tự nghiên cứu system design, web/app design, coding conventions, DevOps khi chưa có task cụ thể

## Cổng nhận task và confirm

Ngoài CLI/WebSocket, backend có REST API để app khác gửi task và phản hồi confirm.

### 1. Gửi yêu cầu/idea

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Nghiên cứu idea X, lên đường đến market, lập plan và triển khai MVP",
    "auto_confirm": false,
    "max_steps": 25
  }'
```

Nếu gửi `"task": ""`, backend sẽ chạy default idle task.

Response có `task_id`:

```json
{
  "task_id": "...",
  "status": "queued",
  "pending_confirmation": null,
  "events": []
}
```

### 2. Xem trạng thái task

```bash
curl http://localhost:8000/api/tasks/<task_id>
```

Khi agent cần bạn xác nhận, response sẽ có:

```json
{
  "status": "waiting_confirmation",
  "pending_confirmation": {
    "confirmation_id": "...",
    "tool": "web_search",
    "prompt": "..."
  }
}
```

### 3. Gửi confirm

```bash
curl -X POST http://localhost:8000/api/tasks/<task_id>/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "confirmation_id": "<confirmation_id>",
    "confirmed": true
  }'
```

Để từ chối, gửi `"confirmed": false`.

## Operating Workflow

Mục tiêu agent:

- Nhận idea/yêu cầu từ bạn qua CLI, WebSocket, hoặc `POST /api/tasks`.
- Nghiên cứu đường đến market trước khi triển khai: target user, pain point, kênh phân phối, rủi ro, MVP scope.
- Lập plan triển khai theo feature nhỏ, có tiêu chí hoàn thành.
- Với repo git: kiểm tra `git status`, dùng feature-based branch rõ ràng, giữ diff gọn, chạy check liên quan, sau đó tóm tắt theo kiểu PR-ready.
- Merge/delete branch chỉ làm khi bạn xác nhận rõ.
- Dừng lại hỏi confirm khi cần gửi dữ liệu ra ngoài, đụng file nhạy cảm, chạy lệnh nguy hiểm, hoặc thay đổi có rủi ro.

Vai trò tool dự kiến:

- Research: ChatGPT/Gemini/Chrome/Edge hoặc `web_search`, nhưng mọi outbound query phải qua confirm và không được chứa private data.
- Implementation: Codex/Claude/Gemini/Cursor qua adapter riêng hoặc CLI tool tương ứng.
- Repo delivery: feature branch, PR summary, review diff, test/check, merge an toàn sau confirm.

Hiện source này đã có cổng task/confirm và tool local cơ bản. Tích hợp trực tiếp ChatGPT/Gemini/Chrome/Edge/Codex/Claude/Cursor cần thêm adapter/tool cụ thể cho từng app.

## Tools

| Tool | Mô tả | Cần confirm? |
|------|-------|--------------|
| `run_shell` | Chạy bash/PowerShell | ✅ Có (nếu rm, sudo, v.v.) |
| `read_file` | Đọc file (có line numbers) | ✅ Nếu path nhạy cảm |
| `write_file` | Ghi file | ✅ Luôn |
| `patch_file` | Thay thế string trong file | ✅ Nếu path nhạy cảm |
| `list_dir` | Liệt kê thư mục | ✅ Nếu path nhạy cảm |
| `search_files` | Tìm text trong files | ✅ Nếu path nhạy cảm |
| `run_python` | Chạy Python code | ✅ Có |
| `run_nodejs` | Chạy Node.js code | ✅ Có |
| `computer_click` | Click vào tọa độ màn hình | ✅ Có |
| `computer_type` | Gõ text vào app/window đang active | ✅ Có |
| `computer_press` | Bấm một phím trong app/window đang active | ✅ Có |
| `computer_hotkey` | Bấm tổ hợp phím như `command+l`, `ctrl+c` | ✅ Có |
| `computer_screenshot` | Chụp màn hình desktop hiện tại | ❌ |
| `computer_position` | Lấy vị trí chuột hiện tại nếu backend hỗ trợ | ❌ |
| `web_search` | Tìm kiếm DuckDuckGo (gửi query ra Internet) | ✅ Luôn |
| `git_status` | Git status | ❌ |
| `git_diff` | Git diff | ❌ |
| `git_log` | Git log | ❌ |

## Privacy Boundary

Agent mặc định chạy local, nhưng một số tool vẫn có rủi ro lộ dữ liệu nếu dùng sai. Boundary hiện tại:

- Chặn đọc private key/secret store như `.ssh/id_*`, `.gnupg/`, macOS Keychains, Windows Credentials.
- Yêu cầu xác nhận khi đụng file nhạy cảm như `.env`, `.npmrc`, `.pypirc`, `.aws/`, `.azure/`, Docker config, file `secret*` hoặc `credentials*`.
- Yêu cầu xác nhận cho mọi `web_search` vì query sẽ rời khỏi máy qua DuckDuckGo.
- Yêu cầu xác nhận khi shell/code có dấu hiệu gọi mạng outbound như `curl`, `wget`, `scp`, `rsync`, `requests`, `httpx`, `fetch`, `axios`.
- Chặn gửi text giống secret/token/password/private key vào external tool.
- Nếu action cần xác nhận nhưng không có kênh xác nhận, agent sẽ từ chối chạy thay vì tự động cho qua.

Lưu ý: boundary này là lớp guardrail ứng dụng, không thay thế sandbox OS. Nếu muốn dùng cho dữ liệu nhạy cảm thật, nên chạy agent trong workspace riêng, dùng account quyền thấp, và tắt/kiểm soát các tool outbound.

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
AGENT_MODEL=qwen3:8b
OLLAMA_URL=http://localhost:11434
AGENT_DEFAULT_TASK="Học một chủ đề system design/conventions/DevOps và tổng hợp cách áp dụng vào dự án"
```

## Models được khuyến nghị

| Model | Vai trò | VRAM | Ghi chú |
|-------|--------|------|---------|
| `qwen3:8b` | Orchestrator | ~5-6GB | Research, planning, điều phối |
| `qwen2.5-coder:7b` | Coding | ~5GB | Nhanh, tốt cho code |
| `qwen2.5-coder:14b` | Coding | ~10GB | Mạnh hơn |
| `deepseek-coder-v2:16b` | Coding | ~12GB | Mạnh, chậm hơn |
| `codellama:7b` | Coding nhẹ | ~5GB | Option thay thế |

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
│       ├── computer_use.py # Typing/clicking/screenshot GUI automation
│       ├── web_search.py  # DuckDuckGo
│       └── git_ops.py   # Git commands
└── safety/
    └── confirm.py       # Human-in-the-loop gate
```

## License

MIT — dùng thoải mái, không cần credit.
