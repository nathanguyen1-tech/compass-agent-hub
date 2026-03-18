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

---

## Phase UI/UX — Từ Dev Tool → War Room

> *"Giao diện hiện tại là dashboard của người lập trình.
> Chủ tướng cần War Room của người chỉ huy."*

---

### Nghiên cứu hành vi Chủ tướng

Trước khi design, phải hiểu Chủ tướng thực sự làm gì:

**7:30 sáng — Mở laptop**
> Chủ tướng không muốn đọc logs. Muốn biết ngay:
> *"Đêm qua có gì xảy ra? Có gì cần tôi quyết định không?"*

**10:00 — Giữa buổi làm việc**
> Nhắn lệnh cho HubKeeper. Muốn thấy nó đang làm, không cần refresh.
> Nếu có lỗi → muốn biết ngay, không phải sau 10 phút.

**14:00 — Có feedback mới từ bác sĩ**
> Thêm vào feedback.md. Bấm một nút. FeedbackBot lo phần còn lại.
> Khi xong → nhận thông báo, xem diff, approve. 30 giây.

**17:00 — Cuối ngày**
> Nhìn tổng kết: hôm nay làm được gì, còn gì tồn đọng.
> Không cần mở dashboard — nhận digest qua Telegram là đủ.

---

### Vấn đề UX hiện tại (phân tích thẳng thắn)

| Khoảnh khắc | Vấn đề | Cảm giác |
|-------------|--------|----------|
| Mở dashboard | Thấy 3 agent cards với dot màu xám | "Tôi cần biết điều gì?" → không rõ |
| Agent đang chạy | Chỉ thấy dot xanh nhấp nháy | "Nó đang làm gì?" → không biết |
| Có approval | Card nhỏ ở góc trái | "Tôi đang duyệt CÁI GÌ?" → không đủ context |
| Navigate agents | Click vào → click ra → lạc | "Tôi đang ở đâu?" |
| Mobile | Không dùng được | "Tôi không thể approve từ điện thoại" |
| Đêm hệ thống lỗi | Không biết cho đến sáng | "Tại sao không ai báo tôi?" |

---

### UI/UX Phase — 3 cấp độ

---

#### UI.1 — Morning Brief (Màn hình chào ngày mới)

Khi mở dashboard lần đầu trong ngày, thay vì hiện list agents ngay → hiện **Morning Brief**:

```
┌─────────────────────────────────────────────────────────────────┐
│  🌅  Thứ Tư, 18/03/2026 — Chào buổi sáng, Chủ tướng           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ⚠️  CẦN QUYẾT ĐỊNH (1)                                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 🩺 FeedbackBot xử lý xong — Fix #001: lỗi tính tuổi     │   │
│  │ ✅ 664 tests pass · Chờ 2 giờ                            │   │
│  │ [ Xem diff ]  [ ✅ Duyệt ]  [ ❌ Từ chối ]               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  📊  ĐÊM QUA (22:00 - 07:30)                                    │
│  ✅ Health Check · 02:00 · 5/5 pass                             │
│  ✅ FeedbackBot · 03:15 · Xử lý 1 feedback                     │
│  ─────────────────────────────────────────────────────────────  │
│  [ Vào Bản Chỉ Huy → ]                                          │
└─────────────────────────────────────────────────────────────────┘
```

**Logic:** Chỉ hiện Morning Brief nếu lần cuối mở dashboard > 4 tiếng trước.

---

#### UI.2 — War Room Layout (Redesign toàn bộ)

**Layout hiện tại:** Sidebar danh sách + main content = thụ động

**War Room layout:** Thông tin chủ động đến Chủ tướng

```
┌──────────────────────────────────────────────────────────────────────┐
│ 🏯 BẢN CHỈ HUY    [⚔️ Tướng lĩnh ▾]  [📡 Stream]  [📊 Báo cáo]  │
│                                        ●━━━ Live  [K] [?]            │
├────────────────────────────┬─────────────────────────────────────────┤
│  ĐANG HOẠT ĐỘNG            │  📡 ACTIVITY STREAM                     │
│ ┌────────────────────────┐ │  ────────────────────────────────────── │
│ │ 🏗️ HubKeeper          │ │  Bây giờ                                │
│ │ ████████░░ 80%        │ │  ▶ 🏗️ Đang sửa server.py               │
│ │ ✏️ Đang sửa index.html│ │  ▶ 🏗️ Đang chạy git commit             │
│ │ ──────────────────── │ │                                          │
│ │ Step 3/5 · 2m 14s    │ │  Hôm nay                                │
│ └────────────────────────┘ │  ✅ 🏥 Health Check pass (5/5)         │
│                             │  ✅ 🩺 FeedbackBot xử lý #001         │
│  ⏳ CHỜ DUYỆT              │  ⚠️ 🩺 FeedbackBot chờ duyệt          │
│ ┌────────────────────────┐ │                                          │
│ │ 🩺 FeedbackBot        │ │  Hôm qua                                │
│ │ Fix #001 · 2h trước   │ │  ✅ 🏥 Health Check pass (5/5)          │
│ │ [Xem diff] [✅] [❌]  │ │  ─────────────────────────────────────  │
│ └────────────────────────┘ │  [ Xem tất cả · Lọc theo agent ▾ ]     │
│                             │                                          │
│  QUÂN ĐỘI (3)              │                                          │
│  🩺 FeedbackBot  ● chờ    │                                          │
│  🏗️ HubKeeper   ● chạy   │                                          │
│  🏥 Health Check ● nghỉ   │                                          │
└────────────────────────────┴─────────────────────────────────────────┘
```

**Key changes:**
- **"Đang hoạt động"** luôn ở top-left, nổi bật nhất
- **Progress bar** cho agent đang chạy (% estimate dựa trên lịch sử)
- **Activity stream** phân nhóm theo thời gian (Bây giờ / Hôm nay / Hôm qua)
- **Danh sách agents** thu nhỏ xuống dưới — không phải focus chính

---

#### UI.3 — Agent Detail: Mission Control

Khi bấm vào agent → không phải "log file viewer" mà là **Mission Control**:

```
┌─────────────────────────────────────────────────────────────────────┐
│ ← Bản Chỉ Huy   🩺 FeedbackBot   ⏳ Chờ duyệt                     │
├────────────────────────┬────────────────────────────────────────────┤
│  NHIỆM VỤ HIỆN TẠI    │  TIMELINE                                   │
│                         │                                             │
│  Fix #001              │  14:30 ──────────────────                  │
│  "Lỗi tính tuổi BN"   │         🚀 Bắt đầu                         │
│                         │  14:30 ──────────────────                  │
│  ✅ Đọc feedback        │         📖 Đọc feedback.md                 │
│  ✅ Implement fix       │         └─ 1 mục "cần xử lý ngay"         │
│  ✅ Tests pass          │  14:31 ──────────────────                  │
│  ⏳ Chờ duyệt ← now    │         ✏️ Sửa intake_agent_v2.py          │
│  ○ Commit & deploy      │         └─ inject current_year vào prompt  │
│                         │  14:32 ──────────────────                  │
│  [Xem diff đầy đủ ↓]   │         🧪 Pytest · 664/664 · 6.7s ✅      │
│                         │  14:33 ──────────────────                  │
├────────────────────────┤         ⏳ Chờ phê duyệt                   │
│  THAY ĐỔI CẦN DUYỆT   │                                             │
│                         │                                             │
│  intake_agent_v2.py    │  LỊCH SỬ CHẠY                             │
│  ─────────────────────  │  ✅ 18/03 · Fix #001 (hiện tại)           │
│  - age = 2024 - year   │  ✅ 10/03 · Fix #000 · 2m30s              │
│  + current = datetime  │  ─────────────────────────────            │
│  + age = current - yr  │  Tổng: 2 runs · 100% thành công           │
│                         │                                             │
│  [ ✅ Duyệt & Commit ] [ ❌ Từ chối ] [ 💬 Nhắn FeedbackBot ]      │
└─────────────────────────────────────────────────────────────────────┘
```

---

#### UI.4 — Keyboard & Speed

Chủ tướng không dùng chuột khi bận:

| Phím | Hành động |
|------|-----------|
| `G` `H` | Go Home — về Command Center |
| `G` `A` | Go Agents — mở danh sách |
| `1` `2` `3` | Chọn agent thứ 1, 2, 3 |
| `R` | Run agent đang chọn |
| `A` | Approve item đang pending |
| `X` | Reject item đang pending |
| `?` | Hiện keyboard shortcuts |
| `Esc` | Đóng panel, về trang trước |

---

#### UI.5 — Mobile War Room

Chủ tướng dùng điện thoại để:
- Xem tình hình khi không ở bàn
- Approve/Reject nhanh

**Mobile layout (375px):**

```
┌────────────────────────┐
│ 🏯 Bản Chỉ Huy    🔔1 │
├────────────────────────┤
│ ⏳ CẦN DUYỆT           │
│ 🩺 FeedbackBot         │
│ Fix #001 · 2h trước    │
│ [✅ Duyệt] [❌ Từ chối]│
├────────────────────────┤
│ 🔵 ĐANG CHẠY           │
│ 🏗️ HubKeeper · 2m      │
│ ✏️ Đang sửa server.py  │
├────────────────────────┤
│ 📡 STREAM              │
│ 14:30 🏗️ git commit ✅ │
│ 14:29 🏗️ Sửa file      │
│ 14:20 🏥 Health 5/5 ✅ │
├────────────────────────┤
│ [🏯][📡][⚔️][⚙️]       │
└────────────────────────┘
```

**Swipe gestures:**
- Swipe phải trên approval card → Approve
- Swipe trái → Reject

---

#### UI.6 — Visual Language (Design System)

**Vấn đề hiện tại:** Không có design system → mỗi component trông khác nhau

**Chuẩn hoá:**

```css
/* Status Colors — consistent everywhere */
--status-running:  #3b82f6  /* blue */
--status-success:  #10b981  /* emerald */
--status-warning:  #f59e0b  /* amber */
--status-error:    #ef4444  /* red */
--status-idle:     #6b7280  /* gray */
--status-pending:  #8b5cf6  /* violet */

/* Typography Scale */
--text-hero:    28px  /* Agent name in detail view */
--text-title:   18px  /* Section headers */
--text-body:    14px  /* Content */
--text-caption: 12px  /* Timestamps, metadata */
--text-micro:   11px  /* Tags, badges */

/* Spacing System — 4px base */
--space-1: 4px   --space-2: 8px
--space-3: 12px  --space-4: 16px
--space-6: 24px  --space-8: 32px
```

**Thống nhất animations:**
- Agent running: pulse nhẹ 2s (không annoying)
- New activity: slide-in từ phải
- Approval appeared: highlight vàng 1s rồi fade
- Success: checkmark animation 0.3s

---

### Thứ tự implement UI phases

```
UI.6 Design System    ← TRƯỚC TIÊN (nền tảng cho mọi thứ)
UI.2 War Room Layout  ← Impact cao nhất, làm ngay sau
UI.3 Mission Control  ← Approval UX — Chủ tướng cần nhất
UI.4 Keyboard         ← Power user, nhanh
UI.1 Morning Brief    ← Nice to have
UI.5 Mobile           ← Sau khi desktop hoàn thiện
```

### Nguyên tắc UX không được phá vỡ

1. **Thông tin quan trọng nhất → to nhất, đầu tiên**
   Approval > Running > Error > Idle. Không bao giờ ngược lại.

2. **Không bao giờ để Chủ tướng đoán mò**
   Mọi action phải có confirmation rõ ràng. Mọi status phải tự giải thích.

3. **Speed is a feature**
   Dashboard mở < 500ms. Transition < 200ms. Không có loading spinner nếu không cần.

4. **Progressive disclosure**
   Nhìn lướt → thấy tổng quan. Click → thấy chi tiết. Không dump tất cả ra một lúc.

5. **Mobile = first class citizen**
   Không phải "responsive" kiểu thu nhỏ. Phải thiết kế riêng cho mobile.

---

*Updated by HubKeeper — 2026-03-18*
