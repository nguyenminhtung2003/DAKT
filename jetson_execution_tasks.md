# Jetson Nano A02 — Execution Tasks for Antigravity

## 1. Mục tiêu

Triển khai V1 cho hệ thống cảnh báo buồn ngủ trên **Jetson Nano A02** với các ưu tiên sau:

1. Hệ thống phải chạy ổn định local trước khi ghép backend.
2. Drowsiness detection phải hoạt động realtime ở mức thực dụng trên Jetson Nano.
3. Face verification chỉ chạy theo sự kiện, không chạy liên tục.
4. Camera CSI chỉ có một owner duy nhất trong toàn hệ thống.
5. Kiến trúc phải đủ rõ để mở rộng lên dashboard, session, OTA và giám sát phần cứng.

---

## 2. Tài liệu đầu vào bắt buộc phải tuân thủ

Agent phải dùng plan kiến trúc gốc làm tài liệu nguồn chính, và file này là tài liệu chỉ đạo thứ tự triển khai.

Ưu tiên hiểu theo thứ tự:
1. Plan kiến trúc gốc
2. File execution tasks này
3. Nếu có điểm chưa rõ thì dừng và báo lại, không tự suy diễn các quyết định lớn

---

## 3. Nguyên tắc bắt buộc

### 3.1 Không được phá kiến trúc camera
- Chỉ một module được quyền mở camera CSI trực tiếp.
- Không module nào khác được tự tạo `cv2.VideoCapture()` riêng.
- Các module khác chỉ đọc frame thông qua `latest_frame` hoặc buffer dùng chung.

### 3.2 Không được verify khuôn mặt liên tục
- Face verification chỉ được chạy trong 2 trường hợp:
  - khi quẹt RFID mở ca
  - khi tái xác minh định kỳ
- Không được biến face verification thành một pipeline realtime liên tục.

### 3.3 Không được ghép backend quá sớm
- Không triển khai logic phụ thuộc WebSocket trước khi local pipeline camera + drowsiness + alert chạy ổn.
- Nếu local pipeline chưa ổn định, phải ưu tiên sửa local trước.

### 3.4 Không được thay lõi drowsiness nếu chưa được duyệt
- Drowsiness V1 phải giữ hướng MediaPipe Face Mesh.
- Không tự thay bằng framework khác nếu chưa được chấp thuận.

### 3.5 Không được mở rộng OTA quá phạm vi V1
- OTA V1 ưu tiên an toàn.
- Không tự thiết kế OTA full-system phức tạp nếu chưa được yêu cầu.

### 3.6 Phải log rõ mọi quyết định runtime quan trọng
- Chuyển state
- Camera reconnect
- RFID scan
- Verify match/mismatch
- Alert level change
- WebSocket reconnect
- OTA apply/fail

---

## 4. Kết quả cuối cùng mong muốn của V1

Sau khi hoàn tất V1, hệ thống phải đạt được các điều sau:

1. Boot lên là service tự chạy.
2. Camera CSI chạy ổn định và cung cấp frame cho toàn hệ thống.
3. Drowsiness detection local hoạt động với EAR / MAR / pitch / PERCLOS.
4. Alert 3 mức hoạt động được qua buzzer / đèn / loa.
5. RFID quẹt được UID ổn định.
6. Face verification theo sự kiện hoạt động được.
7. Session mở và đóng đúng logic.
8. Tái xác minh định kỳ hoạt động.
9. GPS đọc được và gửi dữ liệu được.
10. WebSocket gửi/nhận message cơ bản được.
11. Mất mạng không làm mất các event quan trọng.
12. OTA V1 không làm hỏng hệ thống đang chạy nếu update lỗi.

---

## 5. Task triển khai bắt buộc theo đúng thứ tự

> Quy tắc: Không nhảy cóc task. Không làm Task N+1 nếu Task N chưa có deliverable tối thiểu.

### TASK 0 — Chốt các quyết định mở trước khi code lớn

**Mục tiêu:** Khóa các điểm có thể làm lệch toàn bộ implementation.

**Phải chốt:**
1. Face verification V1 chạy local hay backend.
2. Engine/thư viện face verification cụ thể.
3. Message schema Jetson ↔ Backend tối thiểu.
4. Chính sách offline queue.
5. Chính sách xử lý reverify fail.
6. Phạm vi OTA V1.
7. GPIO mapping thực tế.
8. KPI hiệu năng mục tiêu.

**Deliverable:**
- Một section cấu hình/quyết định đã được chốt rõ.
- Không còn câu hỏi kiến trúc lớn treo lại trước khi viết các module chính.

**Nếu chưa chốt được:** dừng và báo lại.

---

### TASK 1 — Bring-up môi trường Jetson

**Mục tiêu:** Xác nhận hệ điều hành, dependency và driver đủ để chạy project.

**Việc phải làm:**
1. Tạo Python environment.
2. Cài dependency cần thiết.
3. Kiểm tra OpenCV hoạt động.
4. Kiểm tra MediaPipe import được.
5. Kiểm tra serial hoạt động.
6. Kiểm tra audio playback.
7. Kiểm tra GPIO control.
8. Ghi toàn bộ dependency vào `requirements.txt` và script setup.

**Deliverable:**
- Môi trường chạy được đầy đủ.
- Không còn lỗi import hoặc thiếu package nền tảng.

**Chưa đạt nếu:** camera/audio/serial/GPIO chưa test được ít nhất mức cơ bản.

---

### TASK 2 — Viết test độc lập cho từng phần cứng

**Mục tiêu:** Chứng minh từng phần cứng hoạt động độc lập trước khi tích hợp.

**Việc phải làm:**
1. Script test camera CSI.
2. Script test RFID.
3. Script test GPS.
4. Script test buzzer.
5. Script test LED.
6. Script test speaker/loa.
7. Ghi nhận mapping chân và hành vi thực tế.

**Deliverable:**
- Có script test riêng cho từng phần cứng.
- Có thể chạy từng phần độc lập để debug.

**Chưa đạt nếu:** phải chạy cả hệ thống mới test được một phần cứng.

---

### TASK 3 — Dựng skeleton project

**Mục tiêu:** Tạo khung project rõ ràng trước khi đổ logic vào.

**Việc phải làm:**
1. Tạo cấu trúc thư mục chuẩn.
2. Tạo `main.py` orchestration khung.
3. Tạo `config.py`.
4. Tạo logger dùng chung.
5. Tạo class/interface khung cho camera, alerts, sensors, network, storage.
6. Tạo service systemd.
7. Test auto-start service.

**Deliverable:**
- Project khởi động được.
- Service tự start khi boot.

**Chưa đạt nếu:** project chưa có khung chạy tối thiểu hoặc log chưa có chuẩn thống nhất.

---

### TASK 4 — Xây camera pipeline và frame buffer

**Mục tiêu:** Giải quyết sớm module quan trọng nhất và rủi ro nhất.

**Việc phải làm:**
1. Tạo module capture camera CSI bằng GStreamer.
2. Tạo `frame_buffer` chứa frame mới nhất.
3. Chỉ định camera producer là owner duy nhất của camera.
4. Tạo watchdog/reconnect nếu camera lỗi.
5. Đo FPS capture thực tế.
6. Test chạy liên tục ít nhất 30 phút.

**Deliverable:**
- Camera mở ổn định.
- Frame mới được cập nhật liên tục.
- Các module khác chỉ đọc qua buffer.

**Chưa đạt nếu:** có hơn một nơi mở camera hoặc camera dễ treo sau thời gian ngắn.

---

### TASK 5 — Làm Face Analyzer cho drowsiness local

**Mục tiêu:** Có pipeline tính chỉ số buồn ngủ local trước khi ghép bất kỳ phần nào khác.

**Việc phải làm:**
1. Tích hợp MediaPipe Face Mesh.
2. Chỉ xử lý 1 mặt tài xế.
3. Tính EAR.
4. Tính MAR.
5. Tính pitch/head pose.
6. Tạo smoothing cho tín hiệu.
7. Loại bỏ frame kém chất lượng.
8. Xuất metrics dùng cho alert logic.

**Deliverable:**
- Có kết quả realtime: `face_present`, `EAR`, `MAR`, `pitch`, `confidence`.

**Chưa đạt nếu:** chỉ số dao động quá mạnh hoặc không ổn định đủ để dùng cho alert.

---

### TASK 6 — Tạo calibration đầu ca

**Mục tiêu:** Cá nhân hóa ngưỡng cho từng tài xế ở mức V1.

**Việc phải làm:**
1. Thu dữ liệu 5–10 giây đầu session.
2. Tính `ear_open_baseline`.
3. Tính `pitch_neutral`.
4. Tạo fallback mặc định nếu fail.
5. Gắn baseline vào session hiện tại.

**Deliverable:**
- Có baseline dùng cho alert logic.

**Chưa đạt nếu:** hệ thống chỉ dùng ngưỡng cứng tuyệt đối trong mọi trường hợp.

---

### TASK 7 — Xây AlertManager local 3 mức

**Mục tiêu:** Hoàn thiện lõi cảnh báo local.

**Việc phải làm:**
1. Logic Level 1.
2. Logic Level 2.
3. Logic Level 3.
4. Tính PERCLOS theo cửa sổ thời gian.
5. Thêm cooldown/hysteresis.
6. Sinh event cảnh báo.

**Deliverable:**
- Cảnh báo 3 mức hoạt động local.

**Chưa đạt nếu:** alert nhấp nháy liên tục hoặc level tăng giảm không kiểm soát.

---

### TASK 8 — Hoàn thiện driver buzzer / đèn / loa

**Mục tiêu:** Tách output phần cứng khỏi alert logic.

**Việc phải làm:**
1. Tạo `buzzer.py`.
2. Tạo `led.py`.
3. Tạo `speaker.py`.
4. Chuẩn hóa API điều khiển.
5. Test từng level cảnh báo thực tế.

**Deliverable:**
- AlertManager gọi được output qua interface rõ ràng.

**Chưa đạt nếu:** AlertManager chứa trực tiếp mã điều khiển GPIO/audio quá chi tiết.

---

### TASK 9 — Tạo state machine hệ thống

**Mục tiêu:** Làm xương sống vận hành để tránh logic rối.

**Việc phải làm:**
1. Định nghĩa các state.
2. Định nghĩa transition hợp lệ.
3. Gắn event dispatcher.
4. Log mọi lần chuyển state.
5. Tách side-effect theo transition.

**Deliverable:**
- State machine chạy được với các state chính: BOOTING, IDLE, VERIFYING_DRIVER, RUNNING, MISMATCH_ALERT, OFFLINE_DEGRADED, UPDATING.

**Chưa đạt nếu:** luồng main còn là tập hợp `if/else` khó kiểm soát.

---

### TASK 10 — Tích hợp GPS local

**Mục tiêu:** Có dữ liệu GPS sạch trước khi đẩy lên backend.

**Việc phải làm:**
1. Đọc NMEA từ UART.
2. Parse `$GPRMC` và `$GPGGA`.
3. Chuẩn hóa lat/lng/speed/heading/fix.
4. Xử lý reconnect serial và timeout.

**Deliverable:**
- Có output GPS đáng tin cậy.

**Chưa đạt nếu:** GPS chỉ hoạt động chập chờn hoặc không có trạng thái fix/module rõ ràng.

---

### TASK 11 — Tích hợp RFID local

**Mục tiêu:** Tạo event mở phiên làm việc.

**Việc phải làm:**
1. Đọc UID ổn định.
2. Debounce thẻ quét lặp.
3. Phát event `rfid_scanned(uid)`.
4. Không tự gọi camera hoặc verify trong module RFID.

**Deliverable:**
- RFID reader sạch trách nhiệm, chỉ đọc và phát event.

**Chưa đạt nếu:** module RFID tự xử lý chéo sang camera/verify.

---

### TASK 12 — Làm Face Verification V1

**Mục tiêu:** Hoàn thành xác minh tài xế theo sự kiện.

**Việc phải làm:**
1. Lấy frame phù hợp từ buffer.
2. Crop mặt tài xế.
3. So khớp với dữ liệu tài xế/UID.
4. Trả `MATCH`, `MISMATCH`, `LOW_CONFIDENCE`.
5. Log thời gian verify và kết quả.

**Deliverable:**
- Có verify dùng được cho mở ca và reverify.

**Chưa đạt nếu:** verify quá chậm hoặc không phân biệt được low confidence với mismatch thật.

---

### TASK 13 — Hoàn thiện session lifecycle

**Mục tiêu:** Nối RFID + verify + state machine thành luồng mở ca hoàn chỉnh.

**Việc phải làm:**
1. RFID scan → `VERIFYING_DRIVER`.
2. Verify face.
3. Match → tạo session và vào `RUNNING`.
4. Mismatch → cảnh báo và quay về `IDLE`.
5. Tạo `session_start` / `session_end` local event.

**Deliverable:**
- Mở ca và đóng ca đúng logic.

**Chưa đạt nếu:** session chưa có current driver rõ ràng hoặc không reset sạch khi kết thúc.

---

### TASK 14 — Tái xác minh định kỳ

**Mục tiêu:** Chống đổi tài xế sau khi session đã mở.

**Việc phải làm:**
1. Tạo timer reverify.
2. Hỗ trợ fast reverify nếu có bất thường.
3. Verify tài xế active.
4. Áp dụng policy fail đã chốt.
5. Sinh event mismatch nếu cần.

**Deliverable:**
- Cơ chế chống đổi tài xế hoạt động.

**Chưa đạt nếu:** reverify không chạy đúng chu kỳ hoặc fail handling mơ hồ.

---

### TASK 15 — Hardware Monitor

**Mục tiêu:** Theo dõi sức khỏe thiết bị để đưa lên dashboard.

**Việc phải làm:**
1. Tổng hợp trạng thái camera.
2. Tổng hợp trạng thái RFID.
3. Tổng hợp trạng thái GPS.
4. Tổng hợp trạng thái speaker.
5. Tổng hợp trạng thái mạng/cellular.
6. Tạo snapshot hardware định kỳ.

**Deliverable:**
- Có payload hardware rõ ràng.

**Chưa đạt nếu:** trạng thái phần cứng không có tiêu chí healthy/unhealthy cụ thể.

---

### TASK 16 — WebSocket client và local queue

**Mục tiêu:** Kết nối backend ổn định và không làm mất event quan trọng.

**Việc phải làm:**
1. Kết nối WebSocket hai chiều.
2. Reconnect bằng backoff.
3. Gửi các message chính.
4. Nhận command cơ bản.
5. Lưu local khi mất mạng.
6. Flush queue khi reconnect.
7. Chống gửi trùng nếu có retry.

**Deliverable:**
- Online/offline đều vận hành được ở mức V1.

**Chưa đạt nếu:** mất mạng là mất event quan trọng hoặc reconnect gây loop lỗi.

---

### TASK 17 — Tích hợp command từ backend

**Mục tiêu:** Cho dashboard tác động được thiết bị ở mức tối thiểu.

**Việc phải làm:**
1. Nhận `test_alert`.
2. Kích hoạt alert test đúng level.
3. Nhận `update_software`.
4. Validate command trước khi xử lý.

**Deliverable:**
- Test alert chạy được từ backend.
- OTA command đi vào đúng flow xử lý.

**Chưa đạt nếu:** command backend nhận được nhưng không có validation hoặc log.

---

### TASK 18 — OTA an toàn V1

**Mục tiêu:** Update có kiểm soát, không phá hệ thống đang chạy.

**Việc phải làm:**
1. Tải file update vào khu vực tạm.
2. Kiểm tra tính hợp lệ ở mức V1.
3. Backup bản cũ.
4. Apply update.
5. Restart service.
6. Nếu fail thì rollback.
7. Gửi `ota_status`.

**Deliverable:**
- OTA lỗi không làm chết bản đang chạy.

**Chưa đạt nếu:** apply lỗi mà hệ thống không tự hồi phục được.

---

### TASK 19 — Logging và metrics

**Mục tiêu:** Giúp debug trong demo và chạy thực tế.

**Việc phải làm:**
1. Chuẩn hóa log theo module.
2. Log state transition.
3. Log reconnect.
4. Log verify time.
5. Log alert changes.
6. Log queue size / FPS / lỗi camera.

**Deliverable:**
- Có đủ log để truy vết lỗi chính.

**Chưa đạt nếu:** lỗi xuất hiện mà không biết module nào gây ra.

---

### TASK 20 — Tối ưu hiệu năng Jetson

**Mục tiêu:** Đưa hệ thống về mức chạy thực tế ổn định.

**Việc phải làm:**
1. Đo CPU/RAM/FPS.
2. Kiểm tra latency alert.
3. Giảm tải nếu cần bằng resolution/FPS phù hợp.
4. Kiểm tra rò RAM.
5. Kiểm tra nhiệt độ và thời gian chạy dài.

**Deliverable:**
- Hệ thống đạt KPI đã chốt từ TASK 0.

**Chưa đạt nếu:** chạy được nhưng không đạt mức ổn định chấp nhận được trên Jetson Nano.

---

### TASK 21 — Integration test end-to-end

**Mục tiêu:** Chứng minh toàn bộ luồng hoạt động đúng.

**Checklist tối thiểu:**
1. Boot lên service tự chạy.
2. Camera ổn định.
3. Alert local đúng level.
4. RFID đúng → mở session.
5. RFID sai mặt → mismatch.
6. Reverify chạy đúng.
7. GPS có dữ liệu.
8. Hardware heartbeat đúng.
9. WebSocket reconnect đúng.
10. Test alert từ backend đúng.
11. OTA lỗi không phá hệ thống.

**Deliverable:**
- Checklist pass rõ ràng.

---

### TASK 22 — Soak test

**Mục tiêu:** Đánh giá độ bền của hệ thống trước khi demo/nghiệm thu.

**Việc phải làm:**
1. Chạy liên tục 1–2 giờ.
2. Theo dõi camera freeze.
3. Theo dõi RAM.
4. Theo dõi reconnect mạng.
5. Theo dõi GPS fix.
6. Theo dõi queue local.

**Deliverable:**
- Báo cáo ngắn về độ ổn định của bản V1.

**Chưa đạt nếu:** hệ thống treo, rò RAM rõ rệt hoặc camera chết sau thời gian chạy.

---

## 6. Quy tắc dừng và báo lại

Agent phải dừng và báo lại thay vì tự tiếp tục nếu gặp một trong các tình huống sau:

1. Chưa chốt được face verification V1.
2. Camera CSI không ổn định hoặc có xung đột ownership.
3. MediaPipe không đạt mức sử dụng chấp nhận được trên Jetson.
4. GPIO mapping thực tế không khớp tài liệu.
5. WebSocket schema backend khác với tài liệu đã chốt.
6. OTA cần mở rộng vượt phạm vi V1.
7. Reverify fail policy chưa có quyết định rõ.

---

## 7. Điều không được tự ý thay đổi

1. Không thay MediaPipe Face Mesh bằng framework khác.
2. Không đổi nguyên tắc one-camera-owner.
3. Không verify face liên tục.
4. Không ghép backend trước khi local pipeline ổn.
5. Không bỏ state machine.
6. Không mở rộng OTA quá lớn ở V1.
7. Không bỏ local queue nếu backend có yêu cầu event reliability.

---

## 8. Định nghĩa hoàn thành tối thiểu cho từng phase

### Phase 1 hoàn thành khi:
- Toàn bộ phần cứng có script test độc lập.

### Phase 2 hoàn thành khi:
- Project có skeleton rõ ràng và service tự chạy.

### Phase 3 hoàn thành khi:
- Drowsiness local + alert local chạy được ổn định.

### Phase 4 hoàn thành khi:
- GPS + hardware + WebSocket cơ bản chạy được.

### Phase 5 hoàn thành khi:
- RFID + verify + session mở ca chạy đúng.

### Phase 6 hoàn thành khi:
- Reverify định kỳ chạy đúng policy.

### Phase 7 hoàn thành khi:
- Test alert và OTA V1 chạy được.

### Phase 8 hoàn thành khi:
- Soak test pass ở mức chấp nhận được.

---

## 9. Cách báo cáo tiến độ mong muốn

Sau mỗi task, agent nên báo theo format ngắn:

- Đã làm xong gì
- Deliverable hiện có
- Vấn đề phát sinh
- Có thể sang task tiếp theo hay chưa

Ví dụ:

```text
TASK 4 complete:
- Camera CSI mở ổn định bằng GStreamer
- Frame buffer cập nhật đều
- Test 30 phút chưa freeze
- Có thể chuyển sang TASK 5
```

---

## 10. Kết luận chỉ đạo triển khai

Ưu tiên triển khai đúng như sau:

1. Phần cứng + môi trường
2. Camera pipeline
3. Drowsiness local
4. Alert local
5. State machine
6. GPS/RFID
7. Face verification
8. Session + reverify
9. WebSocket + offline queue
10. Backend command + OTA
11. Tối ưu hiệu năng
12. Integration test + soak test

Nếu có mâu thuẫn giữa việc “làm nhanh” và “ổn định kiến trúc”, ưu tiên **ổn định kiến trúc**.

Nếu có mâu thuẫn giữa “ghép backend sớm” và “local pipeline chưa ổn”, ưu tiên **local pipeline**.

