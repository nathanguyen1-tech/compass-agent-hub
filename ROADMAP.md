# ROADMAP.md — Agent Hub
## Từ Bản Chỉ Huy → Đế Chế AI

> **Triết lý:** Chủ tướng không cần biết từng tướng lĩnh đang làm gì từng giây.
> Chủ tướng cần: *nhìn thấy toàn cảnh, ra lệnh rõ ràng, tin tưởng kết quả.*

---

## Chẩn đoán hiện tại (honest assessment)

### Điểm mạnh ✅
- Dashboard real-time hoạt động được
- Auto-detect agent activity qua session watcher
- Activity stream persistent (disk)
- File watcher tự động

### Nợ kỹ thuật ❌
| Vấn đề | Rủi ro |
|--------|--------|
| `server.py` 667 dòng, monolithic | Khó maintain, dễ break |
| `index.html` 704 dòng, everything in one file | Không thể scale UI |
| Data lưu JSON files | Không query được, race condition khi concurrent |
| Không có authentication | Ai mở port 7777 đều truy cập được |
| Approval system dùng `/tmp/fb_confirm` | Hack tạm, không reliable |
| Không có scheduler | Cron jobs nằm ngoài hệ thống |
| Agent-to-agent không communicate được | Mỗi agent là đảo cô lập |

---

## Phase 0 — Dọn nợ kỹ thuật (1-2 tuần)
> *Xây nền móng trước khi xây lầu*

### 0.1 Tái cấu trúc server.py thành modules

```
agent-hub/
├── main.py              ← FastAPI app, lifespan
├── api/
│   ├── agents.py        ← /api/agents/*
│   ├── approvals.py     ← /api/approvals/*
│   └── activity.py      ← /api/activity/*
├── core/
│   ├── registry.py      ← load/save registry
│   ├── activity.py      ← push_activity, persistence
│   └── watchers.py      ← log watcher, session watcher, transcript watcher
├── models/
│   └── schemas.py       ← Pydantic models
└── static/
    └── index.html
```

### 0.2 Chuyển từ JSON → SQLite

```python
# Thay vì registry.json + activity.jsonl + approvals.json
# Dùng 1 file SQLite với 3 tables:
agents(id, name, emoji, status, config_json, created_at, updated_at)
activity(id, agent_id, message, level, ts)
approvals(id, agent_id, status, created_at, resolved_at, metadata_json)
```

**Lợi ích:** Query nhanh, không race condition, filter/sort/pagination thật sự.

### 0.3 Tách index.html thành components

```
static/
├── index.html           ← Shell only
├── js/
│   ├── app.js           ← State management
│   ├── command-center.js
│   ├── agent-detail.js
│   └── websocket.js
└── css/
    └── style.css
```

---

## Phase 1 — Tính năng cốt lõi còn thiếu (2-4 tuần)
> *Những thứ một Chủ tướng cần nhất*

### 1.1 Scheduler — Tự động hóa theo lịch

```json
// registry.json
{
  "id": "health-check",
  "schedule": "0 8 * * *",   // cron: mỗi sáng 8h
  "schedule_tz": "Asia/Saigon"
}
```

Dashboard hiện: `🕗 Chạy tiếp theo: 08:00 sáng mai`
Khi đến giờ → tự trigger → xuất hiện trên Activity Stream

### 1.2 Approval 2.0 — Xem được diff trước khi duyệt

Khi agent cần duyệt, dashboard hiện:
```
⏳ FeedbackBot — Chờ duyệt

📝 Thay đổi:
  intake_agent_v2.py  +3 -1
  ─────────────────────────
  - age = 2024 - birth_year
  + age = current_year - birth_year  # injected from system

✅ Tests: 664/664 pass
🔗 Test tại: https://...ngrok...

[ ✅ Duyệt & Commit ]  [ ❌ Từ chối ]  [ 🔍 Xem full diff ]
```

### 1.3 Notifications — Chủ tướng nhận alert

Khi agent xong việc hoặc cần duyệt:
- Push notification đến Telegram/OpenClaw chat
- Không cần ngồi nhìn dashboard

```python
# Khi push_activity với level="warning" (chờ duyệt) hoặc level="error"
# → tự động gửi message về channel của Chủ tướng
```

### 1.4 Agent Health Status

Mỗi agent có indicator:
- 🟢 **Healthy** — chạy tốt, last run thành công
- 🟡 **Warning** — last run có warning
- 🔴 **Unhealthy** — last run failed, hoặc script không tồn tại
- ⚫ **Unknown** — chưa bao giờ chạy

---

## Phase 2 — Intelligence Layer (1-2 tháng)
> *Từ giám sát → điều phối thông minh*

### 2.1 Agent Tracing (inspired by Langfuse)

Mỗi "run" của agent có một **trace** với nested steps:
```
Run #42 — FeedbackBot (2026-03-18 14:30)
├── Step 1: Đọc feedback.md         [12ms]
├── Step 2: Implement fix #001      [45s]
│   ├── Edit: intake_agent_v2.py
│   └── Edit: tests/test_intake.py
├── Step 3: Run tests               [6.7s] ✅ 664/664
└── Step 4: Await approval          [pending]
```

Bấm vào bất kỳ step → xem input/output đầy đủ.

### 2.2 Agent Memory — Context xuyên suốt

Agents có thể chia sẻ thông tin với nhau:
```python
# FeedbackBot sau khi xử lý:
hub.memory.set("last_fix", {"id": "001", "file": "intake_agent.py", "ts": "..."})

# HubKeeper có thể đọc:
hub.memory.get("feedback-bot/last_fix")
```

Dashboard: tab **"Shared Memory"** — xem các agents đang share gì.

### 2.3 Agent-to-Agent Messaging

```python
# FeedbackBot gọi HubKeeper deploy sau khi fix
hub.send("hub-keeper", "Deploy sau khi FeedbackBot commit xong")
```

Dashboard hiện luồng message giữa agents như một conversation thread.

### 2.4 Run Analytics

```
📊 Thống kê 30 ngày:
  FeedbackBot: 12 runs, 11 thành công, avg 2m30s
  Health Check: 30 runs, 28 thành công, 2 cảnh báo disk
  HubKeeper: 8 runs, 8 thành công, avg 5m
```

---

## Phase 3 — Empire Vision (3-6 tháng)
> *Bản Chỉ Huy trở thành Đế Chế*

### 3.1 Agent Templates Marketplace

```
+ Thêm Agent
┌─────────────────────────────────┐
│  📦 Từ Template                  │
│  ─────────────────────────────  │
│  🏥 Health Check     [Install]  │
│  📊 Daily Report     [Install]  │
│  🔄 Auto Deploy      [Install]  │
│  📧 Email Digest     [Install]  │
│  ─────────────────────────────  │
│  ✍️  Tạo từ đầu                  │
└─────────────────────────────────┘
```

### 3.2 Visual Pipeline Builder

Kéo thả để tạo workflow:
```
[FeedbackBot] → (on success) → [HubKeeper: deploy]
                              → (on failure) → [Notify: alert Chủ tướng]
```

### 3.3 Multi-Environment

```
Production  |  Staging  |  Development
   🟢 3/3  |   🟡 2/3  |    ⚫ 0/3
```

Mỗi môi trường có agents riêng, deploy riêng.

### 3.4 Secrets Manager

```
🔐 Secrets
  NGROK_URL     ••••••••••
  DB_PASSWORD   ••••••••••
  GITHUB_TOKEN  ••••••••••
```

Agents inject secrets qua env vars — không hardcode trong scripts.

---

## Thứ tự ưu tiên thực tế

```
Tuần 1-2:  Phase 0 — Tái cấu trúc (nền móng)
Tuần 3-4:  Phase 1.1 — Scheduler
Tuần 4-5:  Phase 1.2 — Approval 2.0 với diff
Tuần 5-6:  Phase 1.3 — Notifications
Tháng 2:   Phase 2.1 — Tracing
Tháng 2-3: Phase 2.3 — Agent messaging
Tháng 4+:  Phase 3
```

## Nguyên tắc thiết kế (không được phép vi phạm)

1. **Performance first** — Dashboard load < 1s, API response < 100ms
2. **Zero restart** — Mọi thay đổi config không cần restart server
3. **Fail gracefully** — Agent crash không làm chết server
4. **Audit trail** — Mọi action đều có log, không gì bị mất
5. **Convention over configuration** — Agent mới tốn < 5 phút setup
6. **Chủ tướng không bị làm phiền** — Chỉ notify khi thực sự cần

---

*Viết bởi HubKeeper — 2026-03-18*
