# AGENT_STANDARD.md — Chuẩn chung cho mọi Agent

> **Bắt buộc:** Mọi agent mới tạo ra đều phải tuân theo chuẩn này.
> Copy phần liên quan vào `AGENTS.md` của workspace agent đó.

---

## 1. Báo cáo tiến trình về Hub (BẮT BUỘC)

Mọi agent phải POST tiến trình về Hub trong suốt quá trình chạy.
Dashboard **Activity Stream** phụ thuộc vào điều này để Đại Tướng theo dõi.

### Cách báo cáo (dùng exec tool):

```bash
# Script helper — dùng cho script-based agents
/home/nathan-ubutu/.openclaw/workspace/agent-hub/scripts/hub_report.sh <agent_id> "<message>" <level>
```

```bash
# Hoặc curl trực tiếp — dùng cho chat-based agents (OpenClaw AI agents)
curl -s -X POST http://localhost:7777/api/agents/<AGENT_ID>/activity \
  -H "Content-Type: application/json" \
  -d '{"message": "<nội dung>", "level": "<level>"}'
```

### Levels:
| Level | Dùng khi |
|-------|---------|
| `info` | Bắt đầu bước mới, thông tin chung |
| `progress` | Đang thực hiện (đang đọc, đang xử lý...) |
| `success` | Hoàn thành một bước thành công |
| `warning` | Cảnh báo, bất thường nhỏ |
| `error` | Lỗi, thất bại |

### Các mốc BẮT BUỘC phải báo cáo:
```
1. Khi bắt đầu chạy         → level: info
2. Khi bắt đầu từng bước    → level: progress
3. Khi hoàn thành một bước  → level: success / error
4. Khi cần approval         → level: warning
5. Khi kết thúc             → level: success / error
```

### Ví dụ flow hoàn chỉnh:
```bash
hub_report feedback-bot "Bắt đầu xử lý feedback" info
hub_report feedback-bot "Đang đọc feedback.md..." progress
hub_report feedback-bot "Tìm thấy 2 mục cần xử lý" info
hub_report feedback-bot "Đang implement fix #001: sửa lỗi tính tuổi" progress
hub_report feedback-bot "Fix #001 hoàn thành" success
hub_report feedback-bot "Đang chạy tests..." progress
hub_report feedback-bot "Tests pass (12/12)" success
hub_report feedback-bot "Chờ phê duyệt từ Chủ tướng" warning
```

---

## 2. Cập nhật status trên Hub

Ngoài activity stream, agent cũng nên cập nhật status chính thức:

```bash
# Cập nhật status của agent
curl -s -X PATCH http://localhost:7777/api/agents/<AGENT_ID>/status \
  -H "Content-Type: application/json" \
  -d '{"status": "running"}'
```

Status hợp lệ: `idle` | `running` | `pending_approval` | `done` | `error`

---

## 3. Đăng ký agent mới vào registry.json

Mọi agent mới phải có entry trong `/home/nathan-ubutu/.openclaw/workspace/agent-hub/registry.json`:

```json
{
  "id": "ten-agent",
  "name": "Tên Hiển Thị",
  "emoji": "🤖",
  "rank": "Tướng lĩnh",
  "description": "Mô tả ngắn gọn nhiệm vụ của agent",
  "workspace": "/home/nathan-ubutu/.openclaw/workspace-<ten-agent>",
  "script": "",
  "trigger": "manual",
  "status": "idle",
  "requires_approval": true,
  "tags": ["tag1", "tag2"]
}
```

---

## 4. Template AGENTS.md cho agent mới

```markdown
# AGENTS.md — <TênAgent>

## Nhiệm vụ
<Mô tả rõ nhiệm vụ>

## Hub Reporting (BẮT BUỘC)
Agent ID: `<agent-id>`
Báo cáo mọi bước về: http://localhost:7777

Dùng exec tool để báo cáo:
\`\`\`bash
curl -s -X POST http://localhost:7777/api/agents/<agent-id>/activity \
  -H "Content-Type: application/json" \
  -d '{"message": "<message>", "level": "<level>"}'
\`\`\`

## Workflow
1. Báo cáo bắt đầu
2. [các bước xử lý...]
3. Báo cáo hoàn thành / lỗi
```

---

## 5. Checklist khi tạo agent mới

- [ ] Tạo workspace tại `~/.openclaw/workspace-<ten-agent>/`
- [ ] Tạo `AGENTS.md`, `SOUL.md`, `IDENTITY.md`
- [ ] Thêm vào `registry.json` của Agent Hub
- [ ] Thêm hub reporting vào mọi bước trong AGENTS.md
- [ ] Test: chạy agent và xem Activity Stream có cập nhật không
