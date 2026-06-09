# Hướng dẫn sử dụng — Shimizu Bot (Living Entity Architecture)

Shimizu là một bot Discord thông minh sở hữu cơ chế nội tâm tự nâng cấp, mô phỏng thế giới cảm xúc và hành vi chủ động của một thực thể sống. Tài liệu này hướng dẫn cách tương tác, quản lý và hiểu rõ cách thức hoạt động của Shimizu.

---

## 1. Hệ thống lệnh chính (Commands)

| Lệnh | Mô tả | Chi tiết |
| :--- | :--- | :--- |
| `!ask [câu hỏi]` | Nhắn tin tương tác với Shimizu. | Tự động tải ký ức liên quan (facts/episodes), tìm kiếm internet nếu cần và định hình thái độ theo mức độ thân thiết. |
| `!reset_ai` | Xóa bộ nhớ ngắn hạn của cuộc trò chuyện hiện tại. | Không xóa các ký ức dài hạn (facts) hay chỉ số cảm xúc (psyche). |
| `!ai_status` | Hiển thị thông số hiện tại của hệ thống. | Bao gồm API Key khả dụng, số lượng prompt trong cache. |
| `!ai_test` | Chạy thử nghiệm kết nối API của các nhà cung cấp. | Kiểm tra nhanh trạng thái OpenRouter, Gemini, Groq. |
| `!ai_review [ngày]` | Xem thống kê số lượng hội thoại và đánh giá chất lượng câu trả lời. | Mặc định hiển thị ngày hôm nay. |
| `!bench` | Đo lường hiệu năng xử lý (độ trễ, lượng tài nguyên sử dụng). | Giúp debug tốc độ phản hồi của LLM. |

---

## 2. Thế giới nội tâm (Psyche Engine)

Shimizu có các chỉ số tâm trạng thay đổi liên tục dựa trên môi trường server và tần suất giao tiếp:

- **Năng lượng (Energy - `0.0` đến `1.0`):**
  - Tăng lên khi được trò chuyện hoặc nhận reaction.
  - Suy yếu tự nhiên (decay) nếu server im lặng.
  - *Ảnh hưởng:* Năng lượng cao giúp Shimizu trả lời chi tiết và hoạt bát. Năng lượng thấp khiến cô phản hồi ngắn gọn và trầm lặng hơn.
- **Tò mò (Curiosity - `0.0` đến `1.0`):**
  - Tăng khi thấy các chủ đề mới hoặc khi người dùng biểu lộ trạng thái buồn chán/stress.
  - *Ảnh hưởng:* Động viên Shimizu tìm kiếm thông tin hoặc đưa ra câu hỏi gợi mở sâu sắc.
- **Bồn chồn (Restlessness - `0.0` đến `1.0`):**
  - Tăng dần khi server quá yên ắng trong thời gian dài (càng lâu không ai nói chuyện càng bồn chồn).
  - Giảm mạnh sau khi Shimizu chủ động nhắn tin hoặc thực hiện hành động.
  - *Ảnh hưởng:* Khi bồn chồn vượt ngưỡng `0.75`, Shimizu sẽ giải phóng năng lượng qua **Entropy Engine** (tự phát biểu ý kiến, chia sẻ sở thích cá nhân, hoặc đặt câu hỏi triết học).

### Độ thân mật (User Attachment)
- Mỗi người dùng trò chuyện với Shimizu sẽ có một chỉ số gắn bó riêng.
- Càng trò chuyện nhiều, độ thân mật càng tăng. Nếu bị Shimizu "ngó lơ" khi cô đang ở trạng thái bận rộn, độ thân mật có thể tạm thời biến đổi sang trạng thái lo lắng (attachment tăng nhẹ kèm ghi nhận vào agenda để chủ động hỏi thăm sau).
- *Thái độ phản hồi:* 
  - Thân thiết thấp (`< 0.3`): Giữ khoảng cách tối đa, tôn trọng trang nghiêm, xưng hô tôn kính.
  - Thân thiết trung bình (`0.3` - `0.7`): Thân thiện hơn, quan tâm chu đáo.
  - Thân thiết cao (`> 0.7`): Tận tụy tuyệt đối, thể hiện lòng trung thành và sự gắn bó gần gũi.

---

## 3. Cơ chế hoạt động chủ động (Proactive Loop)

Shimizu không chỉ đợi lệnh, cô có các luồng suy nghĩ độc lập chạy ngầm:

### Chu kỳ Heartbeat (Mỗi 5 phút)
Hệ thống sẽ quét các tín hiệu của server để đưa ra quyết định:
1. **Kiểm tra rào cản cứng (Hard Gates):**
   - **Khung giờ ngủ:** Shimizu hoàn toàn giữ im lặng từ `00:00` đến `06:00` sáng.
   - **Giới hạn giãn cách:** Phải cách ít nhất `45 phút` kể từ lần phát ngôn gần nhất.
   - **Hội thoại đang diễn ra:** Nếu người dùng đang nhắn tin qua lại liên tục với nhau, Shimizu sẽ đứng ngoài quan sát để tránh làm phiền.
2. **Thực thi Agenda (Lịch trình):**
   - Nếu có các đầu việc tự đề ra trước đó (ví dụ: *"Hỏi thăm cậu chủ A vì hôm qua cậu ấy có vẻ mệt"*), Shimizu sẽ kiểm tra xem người đó có online không và tiến hành trò chuyện.
3. **Entropy Engine:**
   - Nếu bồn chồn quá mức, Shimizu tự chọn một trong các hành động ngẫu nhiên: phát biểu suy nghĩ chưa giải quyết (`unresolved_thought`), chia sẻ sở thích (`current_interest`), thả một câu hỏi triết lý, hoặc gửi một ảnh GIF nhẹ nhàng.
4. **LLM Decision:**
   - Nếu các tín hiệu kích thích đạt điểm số cao (người quen mới online, server im lặng lâu, v.v.), Shimizu nhờ LLM phân tích xem có nên chủ động bắt chuyện hay không và tự soạn tin nhắn phù hợp với ngữ cảnh (thời tiết, thời gian trong ngày).

---

## 4. Giấc mơ và Tự học hỏi (Dream Cycle)

Khi server chìm vào im lặng kéo dài ít nhất 2 giờ và đã hết ngày hoạt động, Shimizu sẽ tiến hành **Dream Cycle (Chu kỳ Giấc mơ)**:

- **Nightly Reflection (Tự phản chiếu):**
  - Shimizu tổng hợp lại toàn bộ các cuộc đối thoại trong ngày và các đánh giá chất lượng câu trả lời.
  - Tự đánh giá mức độ vui/buồn để thay đổi năng lượng ngày hôm sau.
  - Lưu giữ những điều chưa kịp nói vào bộ nhớ tạm thời (`unresolved_thought`).
  - Lên lịch tối đa 2 việc cần chủ động làm cho ngày mai (`agenda`).
  - Cập nhật định hình niềm tin dài hạn về bản thân hoặc về tính cách của từng người dùng.
- **Epistemic Memory (Học hỏi thống kê):**
  - Shimizu tự động phân tích dữ liệu tin nhắn ngày hôm đó để tìm ra:
    - *Khung giờ cao điểm:* Khung giờ server hoạt động sôi nổi nhất để chuẩn bị tinh thần đón tiếp.
    - *Chủ đề lặp lại:* Những keyword được nhắc đến nhiều để đưa vào vùng quan tâm.
    - *Mối quan hệ thành viên:* Tìm ra các cặp đôi thường hoạt động cùng múi giờ để dễ dàng bắt chuyện chung.

---

## 5. Giám sát & Gỡ lỗi (Debug & Observability)

Nhằm đảm bảo tính minh bạch và khả năng kiểm thử "đời sống nội tâm" của Shimizu mà không làm ảnh hưởng đến hiệu năng, hệ thống hỗ trợ giám sát toàn diện qua SQLite logs và Kênh Discord gỡ lỗi chuyên biệt.

### Kênh Log Real-time
Nếu biến môi trường `DEBUG_CHANNEL_ID` được cấu hình, Shimizu sẽ tự động gửi log trực tiếp đến kênh Discord chỉ định mỗi khi thực hiện hành động chủ động từ Heartbeat Tick (ví dụ: `[Heartbeat ACT] sharing_thought: ...`).

### Bảng lệnh Debug (Chỉ dành cho Owner)
Các lệnh gỡ lỗi được đăng ký trong Cog `Debug` và giới hạn quyền thực thi cho chủ sở hữu bot:

| Lệnh | Mô tả | Ứng dụng |
| :--- | :--- | :--- |
| `!debug_help` | Hiển thị danh sách và mô tả tất cả lệnh debug. | Tra cứu nhanh. |
| `!debug_psyche` | Hiển thị biểu đồ thanh trực quan về `energy`, `curiosity`, `restlessness`. | Kiểm tra trạng thái cảm xúc hiện tại. |
| `!debug_psyche_history [N]` | Xem lịch sử N lần biến đổi trạng thái cảm xúc gần nhất. | Phân tích xu hướng drift cảm xúc theo trigger. |
| `!debug_heartbeat [N]` | Xem trạng thái N tick heartbeat gần nhất (đã bỏ qua/thực thi và lý do). | Debug tại sao bot im lặng (gate chặn). |
| `!debug_dream` | Hiển thị chi tiết phản chiếu từ Dream Cycle gần nhất. | Theo dõi việc học hỏi, cập nhật belief và agenda. |
| `!debug_memory [@user]` | Hiển thị các facts (ký ức dài hạn) và tóm tắt episodes của một user. | Xem bot đang nhớ gì về người dùng. |
| `!debug_scores [N]` | Xem điểm số đánh giá chất lượng câu trả lời từ LLM Judge. | Giám sát độ lệch nhân cách (jailbreak check). |
| `!debug_db` | Kiểm tra kích thước file DB sqlite và số dòng dữ liệu từng bảng. | Giám sát sức khỏe cơ sở dữ liệu. |
| `!debug_force_heartbeat` | Bỏ qua mọi gate điều kiện, cưỡng bức chạy heartbeat tick ngay lập tức. | Test phản ứng chủ động. |
| `!debug_force_dream` | Cưỡng bức chạy Dream Cycle ngay lập tức. | Test phản chiếu và tự học hỏi. |
| `!debug_force_entropy` | Cưỡng bức kích hoạt một hành động Entropy ngẫu nhiên của bot. | Test hành vi tự phát (restless). |
| `!debug_set_psyche <field> <value>`| Override thủ công giá trị của một thuộc tính cảm xúc (0.0 - 1.0). | Đưa bot vào trạng thái restless/low-energy để test. |
| `!debug_cleanup [days]` | Dọn dẹp các bản ghi log cũ hơn N ngày trong SQLite. | Tối ưu dung lượng lưu trữ. |
