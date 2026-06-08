# 🌸 Nhật Ký Phát Triển Bot Nhạc Shimizu

Cuốn nhật ký ghi lại hành trình từ một con bot cơ bản đến khi trở thành một "chiến binh" âm nhạc thực thụ trên AWS.

## 📅 Giai đoạn 1: Khởi Tạo & Di Cư Lên Mây
- **Mục tiêu:** Đưa bot từ máy nhà lên chạy 24/7 trên AWS EC2 (Ubuntu 24.04).
- **Thách thức:** Cấu hình môi trường Linux, cài đặt FFmpeg và quản lý tiến trình chạy ngầm.
- **Kết quả:** Shimizu chính thức "trú ngụ" trên AWS, chạy bằng `nohup` để hát xuyên màn đêm.

## 🎨 Giai đoạn 2: Cuộc Cách Mạng Giao Diện (UI/UX)
- **Nâng cấp:** Thay thế các lệnh văn bản khô khan bằng hệ thống **Buttons** tương tác (Pause, Skip, Stop, Shuffle, Repeat).
- **Tính năng mới:** Thêm menu Dropdown để chọn 1 trong 5 kết quả tìm kiếm, giúp người dùng không phải copy-paste link.
- **Âm thanh:** Tích hợp bộ lọc Bass Boost (cho nhạc quẩy) và Nightcore (cho nhạc chill).

## ⚔️ Giai đoạn 3: Cuộc Đại Chiến YouTube (The Great War)
Đây là giai đoạn cam go nhất, khi YouTube tung ra "thiết quân luật" đối với các IP từ trung tâm dữ liệu (AWS). 

### 1. Sự cố khởi nguồn
- **Lỗi:** `Sign in to confirm you're not a bot`.
- **Nguyên nhân:** YouTube phát hiện IP của AWS và chặn đứng mọi yêu cầu tải nhạc.

### 2. Các "chiến dịch" đã triển khai:
- **Chiến dịch Cookies:** Trích xuất `cookies.txt` từ trình duyệt cá nhân để giả mạo phiên đăng nhập thật. 
    - *Kết quả:* Thất bại do YouTube nhận diện IP thay đổi và vô hiệu hóa cookies ngay lập tức.
- **Chiến dịch "Cải trang" (Extractor Args):** Thử nghiệm hàng loạt client khác nhau để đánh lừa YouTube.
    - Đã thử: `android`, `ios`, `mweb`, `tv`, `web_embedded`, `tv_embedded`.
    - *Kết quả:* Vẫn bị "soi" ra gốc gác AWS.
- **Chiến dịch "Ngoại giao" (OAuth2):** Dùng cơ chế Device Code (nhập mã trên điện thoại).
    - *Kết quả:* Gặp lỗi `HTTP 400: Bad Request` do IP AWS bị chặn cả đường xác thực.
- **Chiến dịch "Mạo danh" (Impersonate):** Cài đặt `curl_cffi` để giả lập TLS Fingerprint của Chrome và Firefox.
    - *Kết quả:* Vượt qua được bước kiểm tra thư viện nhưng vẫn bị YouTube từ chối ở lớp IP.
- **Chiến dịch "Cầu cứu" (Invidious API):** Thử dùng các server trung gian như `yewtu.be`.
    - *Kết quả:* `yt-dlp` quá thông minh, nó tự động chuyển hướng về YouTube gốc và lại bị chặn.
- **Chiến dịch "Thẻ bài hộ mệnh" (PO Token):** 
    - Lấy PO Token từ máy nhà dán vào server. *Kết quả:* Thất bại do Token bị khóa theo IP.
    - Cài đặt Node.js và chạy `npx youtube-po-token-generator` ngay trên AWS để tạo Token chính chủ cho server.

### 3. Sự hy sinh của Server
- Trong nỗ lực cuối cùng để tạo PO Token trên AWS, lệnh `npx` đã khởi chạy một trình duyệt ngầm quá nặng so với sức chịu đựng của con máy `t2.micro` (chỉ 1GB RAM).
- **Kết quả:** Server bị tràn RAM (OOM), đóng băng hoàn toàn và sụp đổ (Crash). Đây là giọt nước tràn ly đưa chúng ta đến quyết định thay đổi chiến thuật.

## 🚀 Giai đoạn 4: Bước Ngoặt SoundCloud - "Về Bờ" An Toàn
- **Quyết định:** Từ bỏ YouTube để bảo vệ sự ổn định của server. Chuyển toàn bộ "động cơ" tìm kiếm sang **SoundCloud**.
- **Kết quả:** 
    - Bot chạy cực nhẹ, không bao giờ bị chặn.
    - Tốc độ phản hồi nhanh gấp 2 lần.
    - Server không còn bị treo hay sập nguồn.
    - Âm thanh chất lượng cao và kho nhạc vô tận.

## 🏆 Kết Luận
Hành trình phát triển Shimizu không chỉ là lập trình, mà là một cuộc đấu trí với các rào cản kỹ thuật. Cuối cùng, chúng ta đã chọn sự ổn định và hiệu quả thay vì cố chấp với một nguồn duy nhất.

**Shimizu giờ đây là một con bot nhạc hiện đại, bền bỉ và sẵn sàng phục vụ bồ 24/7!** 🎶✨

## 🧠 Giai đoạn 5: Nâng Cấp Thông Minh & Tự Động Hóa
Sau khi đã ổn định với SoundCloud, chúng ta tập trung vào việc tối ưu trải nghiệm người dùng bằng AI và các tính năng tự động.

- **Hệ thống Autoplay "Real-deal":** 
    - Thay vì search bừa bãi, bot tích hợp trực tiếp với **SoundCloud Stations**.
    - Tự động lấy danh sách bài hát "liên quan nhất" giống hệt như tính năng trên web của SoundCloud.
    - Đảm bảo nhạc luôn chảy mà không cần người dùng phải nhúng tay.
- **Tối ưu hóa sự hiện diện (Voice Presence):**
    - **Auto-Pause:** Nhạc tự dừng khi mọi người rời phòng để tiết kiệm băng thông.
    - **Auto-Resume:** Tự động quẩy tiếp ngay khi có người quay lại.
    - **Smart Timeout:** Tự động thoát voice sau 15 phút phòng trống để giải phóng tài nguyên server.
- **Kết quả:** Shimizu không chỉ hát hay mà còn cực kỳ "tinh tế" và tiết kiệm tài nguyên.

## 💎 Giai đoạn 6: Cá Nhân Hóa & Quản Trị Chuyên Nghiệp
Giai đoạn này đưa Shimizu lên một tầm cao mới, biến nó từ một trình phát nhạc đơn thuần thành một hệ thống quản lý âm nhạc cá nhân chuyên nghiệp.

- **Nâng cấp Trải nghiệm Thị giác (Visuals):**
    - **Thanh tiến trình (Progress Bar):** Thêm thanh trạng thái trực quan trong embed `!np`, giúp người dùng biết chính xác bài hát đang ở phút thứ mấy.
    - **Nút điều chỉnh Volume:** Thêm nút bấm 🔉/🔊 trực tiếp vào giao diện để chỉnh âm lượng nhanh mà không cần gõ lệnh.
- **Tính năng Điều khiển Nâng cao:**
    - **Seek/Jump:** Cho phép người dùng nhảy đến bất kỳ đoạn nào trong bài hát (ví dụ: `!seek 1:30`).
    - **Quản lý Hàng đợi:** Thêm lệnh `!move` và `!swap` để sắp xếp bài hát linh hoạt.
    - **Lịch sử (History):** Lưu lại 10 bài vừa phát gần nhất để người dùng dễ dàng tìm lại bài hát yêu thích.
- **Hệ thống Playlist Cá nhân:**
    - Cho phép người dùng lưu toàn bộ hàng đợi thành một Playlist riêng (ví dụ: `!sp MyFav`) và tải lại bất cứ lúc nào (`!lp MyFav`).
    - Dữ liệu được lưu trữ bền vững trong `playlists.json`.
- **Quản trị & Bảo mật:**
    - **DJ Role System:** Phân quyền quản trị. Chỉ những người có role "DJ", quyền Admin hoặc chủ Bot mới có thể dùng các lệnh tác động mạnh như `!stop`, `!skip`, `!volume`, `!clear`.
    - **Hệ thống Reset:** Lệnh `!reset` giúp "làm mới" bot ngay lập tức, reload tất cả code mà không cần khởi động lại server.

**Kết quả:** Shimizu giờ đây sở hữu đầy đủ các tính năng của một bot nhạc trả phí, mang lại trải nghiệm nghe nhạc mượt mà và cá nhân hóa tối đa cho bồ.

## ⚡ Giai đoạn 7: Kỷ Nguyên Slash Command & Tối Ưu Chuyển Bài
Bước vào giai đoạn hiện đại hóa toàn diện bot theo tiêu chuẩn mới nhất của Discord.

- **Chuyển đổi Slash Command:** 
    - Toàn bộ hệ thống lệnh (hơn 28 lệnh) được chuyển sang **Hybrid Commands** hỗ trợ cả `/` và `!`.
    - Tích hợp **Autocomplete** và mô tả chi tiết cho từng tham số, mang lại trải nghiệm chuyên nghiệp như các "ông lớn" (Rythm, Groovy cũ).
    - Đồng bộ hóa theo server (Guild Sync) giúp cập nhật lệnh ngay lập tức khi phát triển.
- **Gapless Transition (Pre-fetching):**
    - Cơ chế tải trước bài hát: Tự động fetch dữ liệu và chuẩn bị bài tiếp theo đúng **10 giây** trước khi bài hiện tại kết thúc.
    - Kết quả: Nhạc chuyển tiếp mượt mà, gần như không có khoảng lặng, đặc biệt hiệu quả khi dùng Autoplay.

## 🌦️ Giai đoạn 8: Hoàn Thiện Tiện Ích & Độ Ổn Định Tuyệt Đối
Tập trung vào các tính năng "phi âm nhạc" và củng cố nền tảng hệ thống.

- **Dự báo thời tiết "Pro":**
    - Nâng cấp dịch vụ lấy dữ liệu JSON từ `wttr.in`.
    - Hiển thị chi tiết nhiệt độ theo 4 mốc: **Sáng, Trưa, Chiều, Tối** và dự báo cho ngày mai.
- **Tính năng Meng (Kỷ niệm):** Hệ thống lưu trữ tin nhắn/kỷ niệm riêng tư sử dụng mã hóa XOR để bảo mật thông tin cá nhân khi đẩy code lên GitHub.
- **Chuẩn hóa Hệ thống (Refactoring):**
    - **Logging chuẩn:** Thay thế toàn bộ `print()` bằng `log` chuyên nghiệp, hỗ trợ ghi log file trên AWS để debug từ xa.
    - **Vá lỗi URL hết hạn:** Tự động re-fetch bài hát khi tải Playlist cũ để đảm bảo link stream luôn tươi mới.
    - **Dọn dẹp tài nguyên:** Tối ưu cơ chế hủy Task pre-fetch khi skip hoặc stop bài, tránh rò rỉ tài nguyên server.
- **README Chuyên nghiệp:** Cập nhật tài liệu hướng dẫn chuẩn chỉnh với đầy đủ badge, hướng dẫn cài đặt và cấu trúc thư mục mới.

**Kết quả:** Shimizu không chỉ là một bot nhạc, mà là một "trợ lý ảo" đa năng, ổn định và cực kỳ tinh tế dành riêng cho server của bạn. 🌸🚀

## 🎮 Giai đoạn 9: Trải Nghiệm Thấu Hiểu & Tối Ưu Hiện Diện
Tiếp tục hành trình "Fancy hóa" và cá nhân hóa trải nghiệm cho cặp đôi.

- **Hệ thống Couple Trivia (Thử thách thấu hiểu):** 
    - Xây dựng trò chơi trắc nghiệm thấu hiểu với data pool lên đến **100 câu hỏi** đa dạng chủ đề.
    - **Cơ chế chơi riêng tư:** Sử dụng tin nhắn ẩn (Ephemeral) để mỗi người trả lời mà không bị đối phương nhìn lén.
    - **Bảo mật dữ liệu:** Toàn bộ bộ câu hỏi được mã hóa XOR và lưu dưới định dạng `.ann`, an toàn tuyệt đối khi lưu trữ công khai.
    - **Tính toán % thấu hiểu:** Bot tự động so sánh đáp án và đưa ra đánh giá "xéo sắc" về mức độ tâm đầu ý hợp của hai bạn.
- **Dynamic Presence 2.0 (Trạng thái sống động):**
    - **Smart Tracking:** Bot tự động hiển thị `🎵 [Tên bài hát]` khi đang phát và chuyển sang `Watching [Tâm trạng]` khi rảnh.
    - **Tiết kiệm tài nguyên:** Áp dụng thuật toán so sánh trạng thái (State-tracking), chỉ gọi API Discord khi thực sự có thay đổi, giúp tiết kiệm băng thông và tránh bị rate-limit.
    - **Tâm trạng đa dạng:** Danh sách mood được cập nhật liên tục giúp bot trông giống một "thực thể" đang sống trong server.
- **Tái thiết kế Weather UI (Fancy Style):**
    - Loại bỏ thumbnail rườm rà, chuyển sang giao diện **Blockquote Card** hiện đại, tinh giản.
    - Căn lề thẳng hàng tuyệt đối cho các mốc thời gian, mang lại cảm giác cao cấp và chuyên nghiệp.

**Kết quả:** Shimizu giờ đây không chỉ làm tốt phần "nghe" mà còn cực kỳ thú vị ở phần "chơi" và "nhìn", trở thành một người bạn thực thụ trong server của hai bạn. 🌸🎮✨

## 🔮 Giai đoạn 10: Hệ Thống Tarot Huyền Bí & Cá Nhân Hóa UX
Mở rộng chiều sâu nội dung và nâng cấp toàn diện trải nghiệm "xem quẻ" cho người dùng.

- **Hệ thống Tarot chuyên sâu (V2.0):**
    - **Database khổng lồ:** Mở rộng bộ bài lên **34 lá** (22 Ẩn chính + 12 Ẩn phụ quan trọng), mỗi lá bài được biên soạn cực kỳ chi tiết với các mục: *Thông điệp chung, Tình duyên, Sự nghiệp và Lời khuyên hành động*.
    - **Cơ chế lật bài ngược (Reversed):** Thiết kế lại hoàn toàn nội dung cho bài ngược theo hướng cảnh báo và tháo gỡ tắc nghẽn, thay vì chỉ đổi màu giao diện.
- **Nâng cấp trải nghiệm người dùng (UX):**
    - **Kết quả ẩn danh (Privacy first):** Áp dụng `ephemeral=True` cho tất cả các lệnh Tarot. Người dùng có thể yên tâm "xin quẻ" mà không sợ bị lộ kết quả riêng tư trước khi sẵn sàng chia sẻ.
    - **Hiệu ứng kịch tính (Animation):** Tích hợp GIF xào bài mờ ảo, trì hoãn 2.5s trước khi lật bài để tạo cảm giác hồi hộp như đời thực.
    - **Nút bấm Chia sẻ (Social Share):** Thêm Button "Khoe Nhân Phẩm", cho phép người dùng công khai quẻ bài đẹp của mình vào server chỉ bằng một cú click.
- **Cá nhân hóa & Tính tương tác:**
    - **Hệ thống Cooldown thông minh:** Giới hạn rút bài (12h/lần) để đảm bảo tính "linh ứng".
    - **Ghi chép lịch sử (Journaling):** Bot tự động ghi nhớ các lá bài đã rút. Nếu người dùng rút trúng lá bài cũ, bot sẽ đưa ra những lời nhắc nhở cá nhân hóa đầy thú vị.
    - **Chỉ số Nhân phẩm (Affinity):** Thêm cơ chế ngẫu nhiên tính toán độ may mắn/năng lượng trong ngày, tăng tính giải trí và "game hóa" cho tính năng bói toán.

**Kết quả:** Shimizu Tarot không chỉ là một lệnh bot đơn thuần mà là một hệ thống bói toán có chiều sâu, bảo mật và cực kỳ thu hút người dùng trong server. 🔮✨📖

## 🤖 Giai đoạn 11: Trí Tuệ Nhân Tạo & Tìm Kiếm Web (Web Search Integration)
Nâng cấp Shimizu thành một trợ lý ảo thông minh với khả năng truy cập internet thời gian thực.

- **Tích hợp LLM (Qwen via Ollama):**
    - Kết nối bot với mô hình AI Qwen chạy local qua tunnel ngrok.
    - Xây dựng hệ thống Persona đa dạng: Hầu gái sắc sảo/kiêu ngạo phục vụ Cậu chủ Hoeng và Hầu gái trung thành/thanh tao phục vụ Cô chủ Meng.
- **Hệ thống Bộ nhớ Thông minh (Memory & Summarization):**
    - Lưu trữ lịch sử trò chuyện theo từng người dùng.
    - Tự động tóm tắt (Summarization) hội thoại khi quá dài để chắt lọc những "sự thật" quan trọng vào bộ nhớ chung, giúp AI luôn ghi nhớ sở thích và kỷ niệm của các chủ nhân.
- **Công cụ Tìm kiếm Web (DuckDuckGo Search):**
    - Triển khai cơ chế **Autonomous Search (ReAct style)**: AI có quyền tự quyết định khi nào cần tìm kiếm thông tin mới bằng cách sử dụng tag `[SEARCH: query]`.
    - Tích hợp thư viện `ddgs` với cơ chế xử lý bất đồng bộ (`asyncio.to_thread`), giúp bot vừa search web vừa không làm gián đoạn các tiến trình khác.
    - **Giảm Hallucination:** AI giờ đây có thể kiểm chứng thông tin về thời tiết, tin tức, hoặc sự kiện thực tế thay vì trả lời dựa trên dữ liệu cũ.
- **Lệnh Tiện ích AI:**
    - `!ask`: Trò chuyện trực tiếp với AI có trí nhớ và khả năng search web.
    - `!search`: Tra cứu nhanh thông tin từ DuckDuckGo dưới dạng kết quả thô.
    - `!reset_ai`: Xóa sạch ký ức trò chuyện để bắt đầu một "vòng lặp" mới.

**Kết quả:** Shimizu giờ đây không chỉ hát hay mà còn là một bộ não điện tử thực thụ, có thể tranh luận, ghi nhớ và cập nhật thông tin thế giới 24/7 để phục vụ các chủ nhân một cách hoàn hảo nhất. 🤖🌐🌸

## 📊 Giai đoạn 12: Tối Ưu Hóa Tìm Kiếm & Benchmark Hiệu Năng
Nâng cấp khả năng "nghĩ sâu" của AI và bổ sung công cụ đo đạc tài nguyên chuyên nghiệp.

- **Nâng cấp Tìm kiếm với Jina AI:** 
    - Thay vì chỉ đọc tóm tắt (snippet) từ DuckDuckGo, bot giờ đây sử dụng **Jina Reader API** để cào toàn bộ nội dung bài báo (lên đến 2500 ký tự).
    - AI có cái nhìn sâu sắc hơn, dẫn chứng chính xác và giảm thiểu tối đa hiện tượng "nói sảng".
- **Tối ưu hóa Truy vấn Đa ngôn ngữ:**
    - AI tự động dịch từ khóa tìm kiếm sang **Tiếng Anh** trước khi search để tiếp cận nguồn dữ liệu khổng lồ của thế giới.
    - Kết quả trả về sau đó được AI tổng hợp và phản hồi lại bằng Tiếng Việt một cách mượt mà.
- **Hệ thống Benchmark Tài nguyên:**
    - Tích hợp `pynvml` và `matplotlib` để theo dõi hiệu năng hệ thống trong thời gian thực.
    - Tự động vẽ biểu đồ biến thiên GPU và tính toán tốc độ sinh token (`tokens/s`) sau mỗi câu trả lời.
    - Hỗ trợ cơ chế dự phòng (fallback) qua `nvidia-smi` để đảm bảo đo đạc chính xác trên mọi môi trường Windows/Linux.
- **Vá lỗi Logic Search (False Positive):**
    - Triển khai bộ lọc từ khóa cá nhân (`personal_keywords`) để ngăn bot tự ý gọi web search khi người dùng chỉ đang trêu ghẹo hoặc tâm sự bình thường.
    - Thêm cơ chế chặn đứng lệnh search từ cấp độ Python nếu phát hiện ngữ cảnh không phù hợp.

**Kết quả:** Shimizu giờ đây không chỉ là một bot nhạc mà còn là một trợ lý AI "có kiến thức, có chiều sâu" và cực kỳ minh bạch về hiệu năng phần cứng. 🌸🤖📈

## 🌀 Giai đoạn 13: Kỷ Nguyên AI Hybrid & Hệ Thống Xoay Vòng API
Chuyển mình mạnh mẽ sang mô hình Hybrid AI, kết hợp sức mạnh của nhiều nhà cung cấp đám mây để đạt hiệu suất và độ ổn định cao nhất.

- **Hệ thống Groq Rotator (Primary AI):**
    - Tích hợp **Groq API** với tốc độ sinh token cực nhanh (gần như tức thì).
    - Triển khai cơ chế **Xoay vòng đa Model & đa Key**: Tự động chuyển đổi giữa 8 model hàng đầu (Llama 3.3-70B, Qwen 3, GPT-OSS...) và luân phiên các API Key khi gặp giới hạn (Rate Limit).
    - Loại bỏ các model kém chất lượng hoặc không phù hợp để đảm bảo persona luôn nhất quán.
- **Cơ chế Fallback Gemini (Secondary AI):**
    - Xây dựng **Unified Rotator**: Hệ thống ưu tiên gọi Groq trước, nếu Groq cạn kiệt tài nguyên sẽ tự động "nhảy" sang **Gemini 1.5/2.0** làm dự phòng.
    - Đảm bảo bot luôn phản hồi 24/7 bất kể sự cố từ nhà cung cấp đơn lẻ.
- **Hardening Công cụ Tìm kiếm (Search v3):**
    - **HTML Backend Fallback**: Bổ sung cơ chế cào dữ liệu từ bản DuckDuckGo HTML nếu bản API bị chặn, giúp bot "lì lợm" hơn trước các rào cản IP.
    - **Rút gọn đa tầng (Tiered Fallback)**: Tự động rút gọn câu lệnh tìm kiếm từ 10 từ -> 5 từ -> 3 từ để đảm bảo luôn tìm thấy kết quả ngay cả với những câu hỏi phức tạp.
    - **Tối ưu hóa Token**: Cân bằng lại dung lượng dữ liệu cào (từ 6000 xuống 3500 ký tự) để giảm thiểu chi phí token mà vẫn giữ được độ sâu thông tin.
- **Tinh chỉnh Persona & Search Logic:**
    - Loại bỏ từ khóa gây nhiễu "background" (vốn khiến search engine trả về hình nền) và thay bằng các từ khóa chuyên sâu như `biography`, `wiki`, `backstory`.
    - Nâng cấp lệnh `!ai_status`: Hiển thị chi tiết trạng thái, Model và Key hiện tại của cả hai hệ thống Groq và Gemini.

**Kết quả:** Shimizu hiện sở hữu một hạ tầng AI "bất tử" và thông minh vượt trội, có khả năng xử lý thông tin thực tế với độ chính xác cao và tốc độ phản hồi tính bằng miligiây. 🌀🤖🚀

## 🧠 Giai đoạn 14: Hệ Thống Hybrid Memory & Tri Thức Vĩnh Cửu (Vector RAG)
Nâng cấp toàn diện khả năng ghi nhớ và tra cứu tri thức của Shimizu lên một tầm cao mới.

- **Kiến trúc Hybrid Memory 3 tầng:**
    - **Short-term:** Giữ 5 tin nhắn gần nhất trong RAM để phản hồi tức thì.
    - **Mid-term:** Tóm tắt 10 tin nhắn gần đây để duy trì ngữ cảnh mà không làm tốn Token.
    - **Long-term (Vector Archive):** Sử dụng `text-embedding-004` (sau đó nâng cấp lên `gemini-embedding-2`) để nén ký ức thành các vector toán học.
- **Xây dựng Vector Engine nội bộ:**
    - Tự phát triển hệ thống lưu trữ Vector dựa trên **Numpy** (`.npy`) và Metadata (`.json`), giúp bot có khả năng "lục lại trí nhớ" hàng năm trời chỉ trong vài miligiây.
    - Cơ chế **Semantic Search** (Cosine Similarity) cho phép bot tìm kiếm ký ức theo ý nghĩa thay vì chỉ theo từ khóa.
- **Semantic Knowledge Cache:**
    *   Tự động lưu lại các kết quả tìm kiếm web thành "kho tri thức" (Knowledge Base).
    *   Giúp bot trả lời ngay các câu hỏi cũ mà không cần search lại, giảm thiểu chi phí API và độ trễ.
- **Bảo mật & Cá nhân hóa chuyên sâu:**
    *   Phân tách hoàn toàn không gian ký ức (Namespace) cho từng chủ nhân (**Cậu chủ Hoeng** và **Cô chủ Meng**).
    *   Cơ chế bảo vệ: Chỉ lưu dữ liệu thô từ Internet vào kho kiến thức, tuyệt đối không lưu "ảo giác" của AI.
- **Lệnh quản trị bộ não:**
    *   `!reset_ai`: Làm mới cuộc trò chuyện hiện tại (Short/Mid-term).
    *   `!clear_brain`: Xóa sạch vĩnh viễn kho ký ức dài hạn trong Vector DB.
    *   Nâng cấp lệnh `!help` với giao diện Embed hồng Sakura sang trọng, phân loại rõ ràng.

**Kết quả:** Shimizu giờ đây sở hữu một bộ não có chiều sâu, có khả năng học tập liên tục và ghi nhớ mọi kỷ niệm cùng các chủ nhân một cách bền vững. 🌸🧠🌀

## ⚔️ Giai đoạn 15: Cuộc Chiến YouTube Tái Khởi & Giải Pháp "Tà Đạo" Hybrid
Sau một thời gian yên bình với SoundCloud, chúng ta quyết định tái khởi động cuộc chiến lấy lại "chủ quyền" âm nhạc trên YouTube với những chiến thuật tinh vi hơn.

- **Nâng cấp Hệ thống Tải (Downloader v2.0):**
    - **Chiến dịch "Cửa hậu" (No-Cookie Embed):** Chuyển hướng yêu cầu từ `youtube.com` sang `youtube-nocookie.com` (tên miền dành cho nhúng video).
    - **Client Rotation 2.0:** Ép bot sử dụng các client "vùng xanh" như **`android_vr`** (Kính thực tế ảo) và `web_embedded` để lách bộ lọc của YouTube.
- **Tích hợp "Bên thứ 3" (Third-party Intermediaries):**
    - Xây dựng hệ thống Fallback 3 tầng: 
        1. **Direct Download:** Tải trực tiếp bằng kỹ thuật bypass.
        2. **Loader.to API:** Âm thầm nhờ server trung gian của Loader.to tải và convert hộ bài hát.
        3. **Invidious Proxy:** Sử dụng mạng lưới server Invidious toàn cầu làm "khiên" che IP server AWS.
- **Giải pháp "Chính đạo" - OAuth2 Authentication:**
    - Triển khai cơ chế **Device Code (TV App Authentication)**. Bot được cấp "giấy thông hành" chính chủ từ Google bằng cách giả danh một ứng dụng YouTube trên Smart TV.
    - Kết quả: Sau khi Cậu chủ nhập mã xác nhận, Bot chính thức có quyền truy cập "cửa hậu" của YouTube với độ ổn định tuyệt đối.
- **Tính năng tìm kiếm YouTube độc lập:**
    - Xây dựng lệnh `!yt`: Tách biệt hoàn toàn với hệ thống SoundCloud, mang lại trải nghiệm YouTube thuần túy cho người dùng với Top 5 kết quả tìm kiếm và giao diện đỏ đặc trưng.

**Kết quả:** Một thất bại "ngọt ngào". Dù đã tung ra mọi chiêu trò tà đạo từ Proxy, Embed đến giả danh TV App, YouTube vẫn quét ra IP của AWS và chặn đứng yêu cầu ở những bước cuối cùng.
**Bài học rút ra:** YouTube hiện tại đã chặn IP Datacenter ở mức độ "tận diệt". Giải pháp duy nhất còn lại để thắng cuộc chiến này là dùng **Cookies** của người dùng thật để bảo chứng cho Bot. Cuộc chiến tạm thời tạm dừng ở đây với tỉ lệ thắng 50/50. 🏳️⚔️🎵

## 👑 Giai đoạn 16: Thống Nhất Nhân Cách & Nhận Thức Toàn Diện (SQLite + Hybrid Memory + Intelligent Search)
Sau khi decommission hoàn toàn các hệ thống memory và mối quan hệ cũ để đơn giản hóa kiến trúc, Shimizu được nâng cấp toàn diện và đồng bộ từ Phase 1 đến Phase 5 của lộ trình phát triển.

- **Thống nhất Nhân Cách Hoàng Gia (Royal Maid):**
  - Loại bỏ các hệ thống prompt rườm rà, tsundere và phân chia người dùng phức tạp.
  - Shimizu giờ đây sở hữu nhân cách hầu gái trưởng lịch thiệp, quý tộc và trang nghiêm, xưng "Em/Tôi" và gọi người dùng là "Cậu chủ/Cô chủ/Chủ nhân".
- **Hạ tầng Bộ nhớ SQLite Persistent:**
  - Chuyển đổi toàn bộ việc lưu trữ lịch sử trò chuyện ngắn hạn từ file JSON sang cơ sở dữ liệu SQLite (`message_history`).
  - Tích hợp bộ nhớ ngữ nghĩa dài hạn (Semantic Memory - `user_facts`) lưu trữ thông tin/sở thích của chủ nhân.
  - Tích hợp bộ nhớ hồi ức (Episodic Memory - `episodes`) lưu trữ các tóm tắt cuộc hội thoại trước đó.
  - Thuật toán tìm kiếm bộ nhớ dựa trên Keyword Overlap giúp tìm kiếm hồi ức phù hợp nhất với ngữ cảnh hiện tại mà không phụ thuộc vào Vector DB bên thứ ba.
- **Tìm kiếm Web thông minh (Intelligent Search):**
  - Sử dụng LLM phân loại nhu cầu tìm kiếm (`SEARCH` hoặc `SKIP`) dựa trên câu hỏi của người dùng.
  - Viết lại câu hỏi thành query tối ưu, thực hiện tìm kiếm qua DuckDuckGo bất đồng bộ (`asyncio.to_thread`), và tích hợp cơ chế caching trong SQLite trong vòng 24 giờ.
- **Tự động trích xuất bộ nhớ & Chấm điểm chất lượng (LLM Judge):**
  - Sau mỗi câu trả lời, một tiến trình chạy ngầm bất đồng bộ tự động trích xuất các facts mới và tóm tắt cuộc hội thoại để lưu vào SQLite.
  - Tiến trình cũng tự động chấm điểm chất lượng câu trả lời từ 1-5 để lưu nhật ký đánh giá.
- **Lệnh tối ưu hóa và stress test nhân cách:**
  - `!ai_test`: Thực hiện stress test nhân cách, phát hiện các từ cấm (như ChatGPT, tôi là AI) để đảm bảo độ nhất quán của nhân cách hầu gái.
  - `!ai_review`: Phân tích tự động các câu trả lời điểm thấp và đưa ra giải pháp cải tiến Prompt hệ thống.
- **Tối ưu hóa kỹ thuật:**
  - Giới hạn ngữ cảnh thông minh bằng cách đếm token (ước lượng) giúp tối ưu hóa chi phí token.
  - Thiết lập timeout cứng 30 giây tránh treo tiến trình Discord.

**Kết quả:** Shimizu sở hữu một bộ não hoàn thiện, hoạt động cực kỳ mượt mà, ghi nhớ sâu sắc và tìm kiếm thông tin nhanh chóng từ Internet với phong thái phục vụ chuẩn mực quý tộc. 🌸🧠⚙️
