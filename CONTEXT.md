# CONTEXT.md — AI Project Context

> File này cung cấp context kỹ thuật cho AI đọc khi làm việc với dự án.
> Cập nhật lần cuối: 2026-04-24

## Dự án là gì?

**Face Upload Tool** — Desktop app (Python + CustomTkinter) dùng để:
1. **Upload ảnh khuôn mặt** học sinh lên hệ thống quản lý KeyTech (keytechvietnam.vn)
2. **Xuất Excel** danh sách tài khoản phụ huynh (Gmail hoặc SĐT)

## Tech stack

- **GUI**: CustomTkinter (dark mode)
- **Browser automation**: Playwright (sync API, optional)
- **HTTP**: requests
- **Excel**: openpyxl
- **Build**: PyInstaller (spec file: `FaceUploadTool.spec`)
- **Python**: 3.10+, Windows only

## Cấu trúc module

| File | Vai trò | Phụ thuộc |
|---|---|---|
| `app.py` | GUI chính, entry point | Tất cả module bên dưới |
| `login_helper.py` | Playwright login + network interception | `web_selectors.py` |
| `api_client.py` | HTTP client (fetch students, upload face) | — |
| `uploader.py` | Batch processing 2 pha | `api_client`, `matcher`, `name_utils`, `class_selector` |
| `matcher.py` | Đối chiếu tên file ↔ tên HS (StudentIndex) | `name_utils` |
| `name_utils.py` | Normalize tên tiếng Việt, bỏ dấu | — |
| `class_selector.py` | Validate cấu hình, đoán tên lớp | — |
| `excel_exporter.py` | Xuất Excel tài khoản phụ huynh | `openpyxl` |
| `web_selectors.py` | CSS selectors + URL patterns | — |

## Kiến trúc UI (app.py)

```
┌─ Header ─────────────────────────────────────────────────┐
│  🎓 Title                          [📊 Chế độ Excel]    │
├─ Khối A: Login ──────────────────────────────────────────┤
│  Username + [Đăng nhập] [Thủ công] [Đóng browser]       │
├─ Khối B: Upload Mode (frame_config) ────────────────────┤
│  Base URL, Session, Lớp, API URL, Face Date, Folder     │
│  [Lấy API] [Detect lại] [Kiểm tra] [Test] [▶ Chạy]     │
├─ Khối B2: Excel Mode (frame_excel) ── ẩn mặc định ─────┤
│  Base URL, Session status, Lớp (read-only labels)       │
│  Chế độ xuất: [📧 Gmail | 📱 SĐT]                      │
│  [📥 Xuất Excel]  💡 hint text                          │
├─ Log Box ────────────────────────────────────────────────┤
│  Realtime log với timestamp + color tags                 │
│  Auto-trim tại 1000 dòng                                │
├─ Stats Bar ──────────────────────────────────────────────┤
└──────────────────────────────────────────────────────────┘
```

**Chuyển chế độ**: Nút header toggle `frame_config` ↔ `frame_excel` (grid/grid_forget tại row=2).

## Threading model

| Thread | Vai trò | Constraint |
|---|---|---|
| **Main (Tkinter)** | UI rendering | KHÔNG gọi Playwright API |
| **Playwright Worker** | Login, network events | Giữ sống bằng `page.wait_for_timeout(500)` loop |
| **Upload/Excel Worker** | Phase 1/2, Excel export | Daemon, giao tiếp UI qua `self.after(0, cb)` |

## API KeyTech

- Auth: Cookie `JSESSIONID`
- Student List: `GET {base}/ent/ent/staff/list?staffType=S&deptList=[id]&limit=500`
- Upload Face: `POST {base}/ent/ent/staffface/save` (multipart: staffId, faceEndDate, imageFile)
- Session expire → 401/403 hoặc redirect `/web/login.html`

## Name matching (matcher.py)

Priority: exact_full_name → suffix_N_unique (N≥2, auto upload) → suffix_1_unique (pending) → subset_match (pending) → ambiguous (pending) → not_found

## Excel export (excel_exporter.py)

Hai chế độ:
- **Gmail**: field email → bỏ `@gmail.com` → tài khoản
- **SĐT**: `contactsMobile1` (fallback `contactsMobile2`) → tài khoản

Output: `.xlsx` với header xanh, columns: STT, Lớp, Họ và tên, Tài khoản, Mật khẩu (mặc định `123456`)

## Lưu ý quan trọng khi sửa code

1. **KHÔNG gọi Playwright API từ Tkinter thread** — sẽ crash greenlet
2. **Mọi UI update từ background thread** phải dùng `self.after(0, callback)`
3. **Playwright event loop** cần `page.wait_for_timeout()` — không dùng `time.sleep()`
4. **Session extraction** từ request Cookie header (thread-safe), KHÔNG dùng `context.cookies()`
5. **`web_selectors.py`** — khi web KeyTech đổi HTML, chỉ cần sửa file này
6. **Log tags** — dùng `_LOG_TAG_MAP` (dict prefix→tag), thêm emoji mới thì thêm vào dict
