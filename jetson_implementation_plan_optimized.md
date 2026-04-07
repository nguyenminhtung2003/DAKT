# Jetson Nano A02 — Kế hoạch triển khai tối ưu V1.1

## 1. Mục tiêu

Triển khai phần mềm chạy trên **Jetson Nano A02** cho hệ thống cảnh báo buồn ngủ trên xe ô tô, với các yêu cầu sau:

- Phát hiện buồn ngủ **realtime** bằng **MediaPipe Face Mesh**
- Tính các chỉ số **EAR**, **MAR**, **Head Pose (Pitch)** và **PERCLOS**
- Phát cảnh báo 3 mức qua **buzzer / đèn / loa**
- Xác thực tài xế bằng **RFID + ảnh khuôn mặt**
- **Không xác minh khuôn mặt liên tục**; chỉ xác minh khi:
  - quẹt RFID lúc bắt đầu ca
  - đến chu kỳ tái xác minh chống đổi tài xế
- Đọc **GPS GY-NEO 6M V2** và gửi vị trí về hệ thống quản lý
- Gửi trạng thái phần cứng về server: **nguồn điện, GPS, RFID, camera, loa, kết nối mạng**
- Kết nối **WebSocket 2 chiều** với backend
- Nhận lệnh **Test Alert** và **OTA Update** từ dashboard

---

## 2. Nguyên tắc kỹ thuật chốt

### 2.1 Giữ MediaPipe cho bài toán buồn ngủ
MediaPipe Face Mesh là lõi xử lý chính cho:
- EAR
- MAR
- pitch/head pose
- PERCLOS

### 2.2 Không dùng Face Mesh landmarks để nhận diện danh tính
**Không dùng vector 468 landmarks + cosine similarity** để xác minh tài xế.

Thay vào đó:
- MediaPipe dùng để phát hiện và crop mặt tốt
- face verification là một module riêng, chỉ chạy theo sự kiện

### 2.3 Camera chỉ có một owner duy nhất
Chỉ **CameraProducer** được quyền đọc camera CSI.
Mọi module khác lấy ảnh từ:
- `latest_frame`
- `latest_good_face_frame`

=> tránh xung đột camera giữa main loop và RFID thread.

### 2.4 Không cần AI inference 30 FPS
- Camera có thể capture 30 FPS
- Nhưng AI chỉ cần xử lý khoảng **10–15 FPS ổn định**
- Đây là đủ cho bài toán buồn ngủ vì quyết định dựa theo thời gian vài giây

---

## 3. Cơ chế hoạt động tổng thể

### 3.1 Luồng buồn ngủ
Luôn chạy liên tục trong trạng thái `RUNNING`:
1. Camera đọc frame
2. MediaPipe Face Mesh xử lý 1 mặt tài xế
3. Tính EAR, MAR, pitch
4. Làm mượt chỉ số
5. Tính PERCLOS
6. AlertManager quyết định mức 1 / 2 / 3
7. Kích hoạt buzzer / loa / đèn và gửi event về server

### 3.2 Luồng xác minh tài xế lúc quẹt RFID
1. RFID đọc UID thẻ
2. Jetson chuyển sang trạng thái `VERIFYING_DRIVER`
3. Lấy 1–3 frame mặt gần nhất từ camera
4. So khớp với dữ liệu khuôn mặt tài xế đã đăng ký cho UID đó
5. Nếu khớp:
   - gửi `driver`
   - gửi `session_start`
   - chuyển sang `RUNNING`
6. Nếu không khớp:
   - gửi `face_mismatch`
   - bật cảnh báo tại xe
   - không mở ca làm việc
   - quay về `IDLE`

### 3.3 Luồng tái xác minh chống đổi tài xế
- Mặc định tái xác minh **mỗi 5 phút**
- Có thể rút xuống **2–3 phút** nếu phát hiện bất thường:
  - mất mặt nhiều lần
  - tài xế ra khỏi khung hình lâu
  - góc mặt lệch quá lâu
  - xe đang di chuyển tốc độ cao

Quy trình tái xác minh:
1. Timer kích hoạt `reverify`
2. Chụp 1–3 frame gần nhất
3. So khớp với tài xế đang active
4. Nếu sai:
   - gửi `face_mismatch`
   - bật cảnh báo tại xe
   - nếu lặp lại nhiều lần có thể buộc hệ thống về `IDLE`

### 3.4 Luồng gửi trạng thái phần cứng
Jetson gửi định kỳ:
- `hardware`: mỗi 5 giây
- `gps`: mỗi 3 giây khi có dữ liệu hợp lệ
- `metrics`: mỗi 1 giây (nếu backend cần)
- `alert`: khi đổi trạng thái
- `session_start/session_end`: theo sự kiện
- `ota_status`: theo tiến trình OTA

---

## 4. State machine của Jetson

```text
BOOTING
  -> IDLE
  -> VERIFYING_DRIVER
  -> RUNNING
  -> MISMATCH_ALERT
  -> OFFLINE_DEGRADED
  -> UPDATING
```

### 4.1 Ý nghĩa trạng thái

- **BOOTING**: Khởi tạo camera, GPIO, audio, RFID, GPS, WebSocket
- **IDLE**: Hệ thống đã sẵn sàng nhưng chưa có tài xế hợp lệ
- **VERIFYING_DRIVER**: Đang xác minh RFID + khuôn mặt
- **RUNNING**: Tài xế hợp lệ, thuật toán buồn ngủ chạy liên tục
- **MISMATCH_ALERT**: Phát hiện sai người lái
- **OFFLINE_DEGRADED**: Mất WebSocket hoặc mất mạng, vẫn chạy local
- **UPDATING**: Đang thực hiện OTA

---

## 5. Kiến trúc phần mềm

```text
┌──────────────────────────────────────────────────────────────┐
│                      main.py (Orchestrator)                 │
├──────────────┬──────────────┬──────────────┬────────────────┤
│ Camera       │ Drowsiness   │ Sensors      │ Network        │
│ Producer     │ Worker       │              │                │
├──────────────┼──────────────┼──────────────┼────────────────┤
│ capture.py   │ face_analyzer│ rfid_reader  │ ws_client      │
│ frame_buffer │ alert_manager│ gps_reader   │ ota_handler    │
│              │              │ hw_monitor   │                │
├──────────────┴──────────────┴──────────────┴────────────────┤
│ FaceVerifier │ AudioManager │ Local Store  │ systemd        │
│              │              │ queue/state  │ auto-restart   │
└──────────────────────────────────────────────────────────────┘
```

---

## 6. Cấu trúc thư mục đề xuất

```text
CodeJetsonNano/
├── main.py
├── config.py
├── camera/
│   ├── __init__.py
│   ├── capture.py
│   ├── frame_buffer.py
│   ├── face_analyzer.py
│   └── face_verifier.py
├── sensors/
│   ├── __init__.py
│   ├── rfid_reader.py
│   ├── gps_reader.py
│   └── hardware_monitor.py
├── alerts/
│   ├── __init__.py
│   ├── alert_manager.py
│   ├── buzzer.py
│   ├── speaker.py
│   └── led.py
├── network/
│   ├── __init__.py
│   ├── ws_client.py
│   └── ota_handler.py
├── storage/
│   ├── __init__.py
│   ├── local_queue.py
│   ├── state_store.py
│   └── driver_registry.py
├── utils/
│   ├── logger.py
│   ├── timers.py
│   └── metrics.py
├── sounds/
│   ├── alert_level1.wav
│   ├── alert_level2.wav
│   └── alert_level3.wav
├── requirements.txt
├── install.sh
└── drowsiguard.service
```

---

## 7. Thiết kế từng module

## 7.1 `camera/capture.py`

Nhiệm vụ:
- Mở camera IMX219-77 IR bằng GStreamer CSI
- Tự reconnect nếu lỗi
- Đẩy frame mới nhất vào buffer

### GStreamer pipeline đề xuất
```text
nvarguscamerasrc ! video/x-raw(memory:NVMM), width=1280, height=720, framerate=30/1 ! \
nvvidconv flip-method=0 ! video/x-raw, width=640, height=360, format=BGRx ! \
videoconvert ! video/x-raw, format=BGR ! appsink drop=true sync=false
```

### Quy tắc
- Camera chỉ mở một lần
- Không module nào khác được tự tạo `cv2.VideoCapture()` riêng

---

## 7.2 `camera/frame_buffer.py`

Chứa:
- `latest_frame`
- `latest_timestamp`
- `latest_good_face_frame`
- `latest_face_bbox`

Mục đích:
- Worker AI dùng `latest_frame`
- RFID/FaceVerifier dùng `latest_good_face_frame`

---

## 7.3 `camera/face_analyzer.py`

### Chức năng
- Chạy MediaPipe Face Mesh với `max_num_faces=1`
- Tính:
  - EAR
  - MAR
  - pitch
  - face confidence
- Trả về kết quả cho AlertManager

### Landmark dùng cho EAR
- Mắt trái: `[362, 385, 387, 263, 373, 380]`
- Mắt phải: `[33, 160, 158, 133, 153, 144]`

### Landmark dùng cho MAR
- Miệng: `[13, 14, 78, 308, 81, 311]`

### Head pose
- `solvePnP` với các điểm mặt ổn định
- Dùng `pitch_delta = pitch - pitch_neutral`

### Cơ chế lọc nhiễu
- EMA hoặc moving average cho EAR/MAR/pitch
- Bỏ frame khi:
  - mặt quá lệch
  - landmark không ổn định
  - confidence thấp

---

## 7.4 `alerts/alert_manager.py`

### Input
- `ear_smooth`
- `mar_smooth`
- `pitch_delta`
- `perclos_30s`
- `face_present`

### Output
- mức cảnh báo hiện tại
- lệnh điều khiển buzzer/loa/đèn
- event gửi về server

### Logic cảnh báo V1

#### Level 1
Kích hoạt khi:
- EAR thấp liên tục 1.5–2.0 giây
- hoặc ngáp lặp lại >= 2 lần / 60 giây

Hành động:
- buzzer ngắt quãng
- đèn cảnh báo mức 1
- gửi `alert`

#### Level 2
Kích hoạt khi:
- EAR thấp liên tục 3–4 giây
- hoặc gật đầu kéo dài > 2 giây
- hoặc PERCLOS cao kéo dài

Hành động:
- buzzer liên tục
- loa phát âm thanh cảnh báo
- đèn mức 2
- gửi `alert`

#### Level 3
Kích hoạt khi:
- EAR thấp > 5–6 giây
- hoặc lặp lại Level 2 nhiều lần trong 2 phút

Hành động:
- còi + loa mức khẩn
- đèn khẩn cấp
- gửi `alert`

---

## 7.5 `sensors/rfid_reader.py`

### Chức năng
- Poll MFRC522 mỗi 300–500 ms
- Khi có thẻ:
  - đọc UID
  - phát sự kiện `rfid_scanned(uid)`

### Không làm trong module này
- Không mở camera
- Không tự xử lý face verification

---

## 7.6 `camera/face_verifier.py`

### Chức năng
- Chạy khi:
  - quẹt RFID
  - timer tái xác minh
- Lấy 1–3 frame từ `latest_good_face_frame`
- Crop mặt và so khớp với dữ liệu tài xế

### Thiết kế V1
Face verification là module **độc lập** với MediaPipe drowsiness.

Output:
- `MATCH`
- `MISMATCH`
- `LOW_CONFIDENCE`

### Lưu ý
- Không dùng cosine similarity trực tiếp trên 468 landmarks
- Dữ liệu đăng ký tài xế phải được đồng bộ từ hệ thống quản lý hoặc lưu local theo `driver_id` / `rfid_uid`

---

## 7.7 `sensors/gps_reader.py`

### Chức năng
- Đọc GPS GY-NEO 6M V2 từ UART
- Parse `$GPRMC`, `$GPGGA`
- Lấy:
  - latitude
  - longitude
  - speed
  - heading
  - valid fix

### Tần suất
- Gửi mỗi 3 giây nếu có fix hợp lệ

### Trạng thái GPS
- `gps_module_ok`: serial mở được
- `gps_fix_ok`: có fix tọa độ hợp lệ

---

## 7.8 `sensors/hardware_monitor.py`

### Nhiệm vụ
Kiểm tra và đóng gói trạng thái phần cứng:
- `power`
- `camera`
- `rfid`
- `gps`
- `speaker`
- `cellular`

### Quy tắc xác định
- `power = true`: Jetson đang chạy ổn định
- `camera = true`: có frame mới trong 2 giây gần nhất
- `rfid = true`: RFID init và poll không lỗi
- `gps = true`: serial hoạt động và nhận được dữ liệu hợp lệ gần đây
- `speaker = true`: phát test tone hoặc playback không lỗi
- `cellular = true`: WebSocket còn sống hoặc ping backend thành công

### Tần suất
- gửi `hardware` mỗi 5 giây

---

## 7.9 `network/ws_client.py`

### Chức năng
- Duy trì WebSocket 2 chiều với backend
- Auto reconnect bằng exponential backoff
- Queue message local nếu mất mạng

### Gửi lên server
- `hardware`
- `driver`
- `session_start`
- `session_end`
- `alert`
- `gps`
- `face_mismatch`
- `ota_status`

### Nhận từ server
- `test_alert`
- `update_software`

---

## 7.10 `network/ota_handler.py`

### Cơ chế OTA an toàn
1. nhận lệnh update từ server
2. tải file vào `/tmp`
3. kiểm tra syntax bằng:
   ```bash
   python3 -m py_compile /tmp/update.py
   ```
4. nếu pass:
   - backup file cũ
   - copy file mới vào project
   - restart systemd service
5. nếu fail:
   - hủy update
   - gửi `ota_status = FAILED`
   - hệ thống cũ tiếp tục chạy

---

## 7.11 `storage/local_queue.py`

### Chức năng
Lưu cục bộ khi mất mạng:
- alert chưa gửi
- gps chưa gửi
- hardware log quan trọng
- event session

### Mục đích
- không mất log khi rớt 4G
- reconnect xong có thể gửi lại

---

## 8. Session lifecycle

### 8.1 Mở ca
Điều kiện:
- RFID hợp lệ
- face verification hợp lệ

Hành động:
- set `current_driver`
- set `session_active = true`
- gửi `driver`
- gửi `session_start`
- chuyển sang `RUNNING`

### 8.2 Trong ca
- thuật toán buồn ngủ chạy liên tục
- cứ 5 phút tái xác minh tài xế
- gửi GPS + hardware heartbeat định kỳ

### 8.3 Kết thúc ca
Khi:
- người dùng tắt máy / hệ thống tắt
- hoặc tài xế logout hợp lệ

Hành động:
- gửi `session_end`
- reset trạng thái tài xế
- quay về `IDLE`

---

## 9. Message schema Jetson -> Backend

## 9.1 Hardware
```json
{
  "type": "hardware",
  "data": {
    "power": true,
    "cellular": true,
    "gps": true,
    "camera": true,
    "rfid": true,
    "speaker": true,
    "timestamp": "2026-04-07T20:15:30+07:00"
  }
}
```

## 9.2 Driver
```json
{
  "type": "driver",
  "data": {
    "name": "Nguyen Van A",
    "rfid": "ABC123"
  }
}
```

## 9.3 Session start
```json
{
  "type": "session_start",
  "data": {
    "rfid_tag": "ABC123",
    "driver_id": 3
  }
}
```

## 9.4 Session end
```json
{
  "type": "session_end",
  "data": {
    "rfid_tag": "ABC123"
  }
}
```

## 9.5 GPS
```json
{
  "type": "gps",
  "data": {
    "lat": 10.762,
    "lng": 106.660,
    "speed": 45,
    "heading": 120
  }
}
```

## 9.6 Drowsiness alert
```json
{
  "type": "alert",
  "data": {
    "alert_type": "DROWSINESS",
    "alert_level": "LEVEL_2",
    "ear": 0.18,
    "mar": 0.32,
    "pitch": -12.5,
    "timestamp": "2026-04-07T20:16:12+07:00"
  }
}
```

## 9.7 Face mismatch
```json
{
  "type": "face_mismatch",
  "data": {
    "rfid_tag": "ABC123",
    "expected": "Nguyen Van A",
    "snapshot": "base64..."
  }
}
```

## 9.8 OTA status
```json
{
  "type": "ota_status",
  "data": {
    "status": "APPLIED",
    "filename": "main.py"
  }
}
```

---

## 10. Message schema Backend -> Jetson

## 10.1 Test alert
```json
{
  "action": "test_alert",
  "level": 2,
  "state": "on"
}
```

## 10.2 OTA
```json
{
  "action": "update_software",
  "download_url": "http://SERVER_IP/static/updates/main.py"
}
```

---

## 11. Config mặc định đề xuất

```python
# Camera
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 360
CAMERA_FPS = 30
AI_TARGET_FPS = 12
MAX_NUM_FACES = 1

# Drowsiness thresholds (default fallback)
EAR_THRESHOLD = 0.21
MAR_THRESHOLD = 0.65
PITCH_DELTA_THRESHOLD = -15.0
PERCLOS_THRESHOLD = 0.35

# Alert timing
LEVEL1_DURATION = 2.0
LEVEL2_DURATION = 4.0
LEVEL3_DURATION = 6.0

# Reverification
REVERIFY_INTERVAL_SEC = 300      # 5 phút
REVERIFY_FAST_INTERVAL_SEC = 180 # 3 phút

# Hardware pins
BUZZER_RELAY_PIN = 18
LED_WARNING_PIN = 16
LED_CRITICAL_PIN = 22

# GPS
GPS_PORT = "/dev/ttyTHS1"
GPS_BAUDRATE = 9600

# WebSocket
WS_SERVER_URL = "ws://<SERVER_IP>:8000/ws/jetson/<DEVICE_ID>"
DEVICE_ID = "JETSON-001"

# Local store
QUEUE_DB_PATH = "storage/local_events.db"
```

---

## 12. Calibration đầu ca

Sau khi `session_start`, chạy calibration 5–10 giây:
- EAR mở mắt trung bình
- pitch trung tính
- kích thước khuôn mặt tham chiếu

Output:
- `ear_open_baseline`
- `pitch_neutral`

### Cách dùng
- `EAR_closed_threshold = min(0.21, 0.75 * ear_open_baseline)`
- `pitch_delta = pitch - pitch_neutral`

Nếu calibration fail:
- dùng giá trị fallback mặc định

---

## 13. Lộ trình triển khai theo phase

## Phase 1 — Bring-up phần cứng
Mục tiêu:
- camera CSI chạy ổn định
- RFID đọc được UID
- GPS đọc được NMEA
- buzzer/đèn/loa hoạt động
- xác nhận chân GPIO đúng

Kết quả cần có:
- script test riêng cho từng phần cứng

## Phase 2 — Skeleton project
Mục tiêu:
- tạo cấu trúc thư mục
- `main.py` điều phối
- logging
- config
- thread model
- systemd service chạy được

## Phase 3 — Drowsiness local realtime
Mục tiêu:
- MediaPipe Face Mesh chạy ổn
- tính EAR/MAR/pitch
- alert 3 mức local
- chưa cần mạng

## Phase 4 — WebSocket + hardware + GPS
Mục tiêu:
- kết nối backend
- gửi `hardware`, `gps`, `alert`
- reconnect khi mất mạng

## Phase 5 — RFID + session
Mục tiêu:
- quẹt thẻ
- xác minh khuôn mặt
- gửi `driver`, `session_start`
- session_end khi tắt máy / kết thúc ca

## Phase 6 — Tái xác minh định kỳ
Mục tiêu:
- timer 5 phút
- chống đổi tài xế
- gửi `face_mismatch` nếu sai

## Phase 7 — OTA + test_alert
Mục tiêu:
- backend gửi test alert
- Jetson phát đúng mức
- OTA an toàn với `py_compile`

## Phase 8 — Soak test
Mục tiêu:
- chạy liên tục 1–2 giờ
- không treo camera
- không rò RAM rõ rệt
- reconnect tốt

---

## 14. Verification plan

## 14.1 Test từng module

```bash
# Camera
python -c "from camera.capture import CSICamera; c = CSICamera(); print(c.read())"

# MediaPipe
python -c "from camera.face_analyzer import FaceAnalyzer; a = FaceAnalyzer(); print('OK')"

# RFID
python -c "from sensors.rfid_reader import RFIDReader; r = RFIDReader(); r.read_once()"

# GPS
python -c "from sensors.gps_reader import GPSReader; g = GPSReader(); print(g.read_once())"

# Buzzer
python -c "from alerts.buzzer import Buzzer; b = Buzzer(); b.beep(3)"

# WebSocket
python -c "from network.ws_client import WSClient; c = WSClient(); c.test_connect()"
```

## 14.2 Test tích hợp
- [ ] Boot lên là service tự chạy
- [ ] Camera stream ổn định sau 30 phút
- [ ] Nhắm mắt đủ thời gian thì đúng level alert
- [ ] Quẹt RFID đúng -> mở session
- [ ] Quẹt RFID sai mặt -> `face_mismatch`
- [ ] Sau 5 phút -> tái xác minh chạy đúng
- [ ] GPS hiển thị được trên dashboard
- [ ] Hardware badge đổi đúng màu
- [ ] Dashboard test alert bật/tắt được
- [ ] OTA lỗi cú pháp không làm hỏng hệ thống cũ

---

## 15. Open questions cần chốt trước khi code

1. Face verification V1 sẽ chạy:
   - local hoàn toàn trên Jetson
   - hay Jetson gửi ảnh lên backend để backend xác minh?

2. Có mạch đo nguồn riêng không?
   - nếu chưa có, `power=true` tạm hiểu là Jetson đang chạy

3. Khi tái xác minh thất bại:
   - cảnh báo nhưng vẫn cho chạy tiếp?
   - hay buộc session về `IDLE`?

4. Có cần chụp snapshot lưu local khi mismatch không?

---

## 16. Kết luận triển khai

Bản V1 tối ưu cho Jetson Nano A02 nên được chốt như sau:

- **MediaPipe giữ cho realtime drowsiness**
- **RFID + face verification chạy theo sự kiện**
- **Tái xác minh mỗi 5 phút** để chống đổi tài xế
- **Hardware status gửi định kỳ về dashboard**
- **OTA phải an toàn qua py_compile + backup**
- **Camera chỉ có một owner duy nhất**

Đây là phương án cân bằng nhất giữa:
- tính đúng kỹ thuật
- khả năng chạy ổn trên Jetson Nano A02
- phù hợp với web dashboard hiện tại
- đủ mạnh để triển khai thành đồ án tốt nghiệp
