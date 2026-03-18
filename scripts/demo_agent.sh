#!/bin/bash
# Demo agent — giả lập công việc thực tế
echo "🚀 Agent bắt đầu lúc $(date '+%H:%M:%S')"
sleep 1

echo "📋 Bước 1: Đọc dữ liệu đầu vào..."
sleep 1
echo "   ✅ Tìm thấy 3 feedback từ MD Minh"
sleep 1

echo "📋 Bước 2: Phân tích feedback..."
sleep 1
echo "   🔍 Feedback 1: Agent hỏi ngày sinh 2 lần → cần fix"
sleep 1
echo "   🔍 Feedback 2: Màu header chưa đồng nhất → cần fix"
sleep 1
echo "   🔍 Feedback 3: Câu hỏi quá dài → cần rút ngắn"
sleep 1

echo "📋 Bước 3: Gọi Claude Code để sửa..."
sleep 1
echo "   ⚙️ Đang sửa intake_agent_v2.py..."
sleep 2
echo "   ⚙️ Đang sửa intake_prompt_v2.py..."
sleep 2
echo "   💬 Claude: Đã patch logic hỏi ngày sinh"
sleep 1

echo "📋 Bước 4: Chạy unit tests..."
sleep 1
echo "   ✅ 664 tests passed (0 failed)"
sleep 1

echo ""
echo "✅ Hoàn thành! Chờ phê duyệt để commit..."
exit 0
