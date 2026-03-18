# AGENT_STANDARD.md — Chuẩn chung cho mọi Agent

> **Bắt buộc:** Mọi agent mới tạo ra đều phải tuân theo chuẩn này.

---

## Cơ chế báo cáo tự động

Server **tự động** watch file `/tmp/hub-<agent_id>.log` của từng agent.
Agent chỉ cần ghi vào file đó — server sẽ tự đẩy lên Activity Stream.

```
Agent viết vào /tmp/hub-<id>.log
        ↓  (tự động, 0.5s)
Server đọc → push Activity Stream
        ↓  (real-time)
Dashboard Đại Tướng thấy ngay
```

---

## Dành cho Script-based agents (có file .sh)

Chỉ cần **2 dòng** ở đầu script:

```bash
export AGENT_ID="ten-agent-id"
source /home/nathan-ubutu/.openclaw/workspace/agent-hub/scripts/agent_init.sh
```

**Sau đó tất cả tự động:**
- `git pull` → tự báo "⬇️ Đang pull..."
- `git commit` → tự báo "📦 Committed: abc1234"
- `git push` → tự báo "🚀 Pushed lên GitHub"
- `pytest` → tự báo "🧪 Đang chạy tests..." + kết quả
- Script kết thúc → tự báo ✅ hoặc ❌

**Muốn báo thêm thủ công:**
```bash
hlog "Đang xử lý file XYZ..." progress
hlog "Fix #001 hoàn thành" success
```

---

## Dành cho Chat-based agents (OpenClaw AI agents)

Dùng `exec` tool để ghi vào log file — server tự pick up:

```bash
# Ghi 1 dòng → server tự đẩy lên stream
echo '{"message":"Đang đọc feedback.md...","level":"progress"}' >> /tmp/hub-<agent_id>.log
```

**Các bước bắt buộc phải báo:**

| Thời điểm | Lệnh |
|-----------|------|
| Bắt đầu chạy | `echo '{"message":"Bắt đầu","level":"info"}' >> /tmp/hub-<id>.log` |
| Mỗi bước xử lý | `echo '{"message":"Đang làm X...","level":"progress"}' >> /tmp/hub-<id>.log` |
| Hoàn thành bước | `echo '{"message":"X xong","level":"success"}' >> /tmp/hub-<id>.log` |
| Có lỗi | `echo '{"message":"Lỗi: ...","level":"error"}' >> /tmp/hub-<id>.log` |
| Chờ duyệt | `echo '{"message":"Chờ phê duyệt","level":"warning"}' >> /tmp/hub-<id>.log` |

---

## Levels

| Level | Màu trên stream | Dùng khi |
|-------|----------------|---------|
| `info` | trắng | Thông tin chung, bắt đầu |
| `progress` | xanh dương | Đang thực hiện |
| `success` | xanh lá (cyan) | Hoàn thành tốt |
| `warning` | vàng | Cần chú ý, chờ duyệt |
| `error` | đỏ | Lỗi, thất bại |

---

## Đăng ký agent mới vào registry.json

```json
{
  "id": "ten-agent",
  "name": "Tên Hiển Thị",
  "emoji": "🤖",
  "rank": "Tướng lĩnh",
  "description": "Mô tả ngắn gọn",
  "workspace": "/home/nathan-ubutu/.openclaw/workspace-<ten-agent>",
  "script": "",
  "trigger": "manual",
  "status": "idle",
  "requires_approval": true,
  "tags": ["tag1", "tag2"]
}
```

Sau khi thêm vào registry.json và **restart server**, watcher sẽ tự động khởi động cho agent mới.

---

## Checklist agent mới

- [ ] Tạo workspace tại `~/.openclaw/workspace-<ten-agent>/`
- [ ] Tạo `AGENTS.md`, `SOUL.md`, `IDENTITY.md`
- [ ] Thêm vào `registry.json` → restart server
- [ ] Script-based: thêm 2 dòng `source agent_init.sh`
- [ ] Chat-based: thêm `echo` vào các bước trong AGENTS.md
- [ ] Test: kiểm tra `/tmp/hub-<id>.log` có data và stream có cập nhật
