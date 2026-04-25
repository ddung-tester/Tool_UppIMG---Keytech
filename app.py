"""
Face Upload Tool v3.0 - GUI chính.
3 khối: Login → Cấu hình lớp → Log/Upload.
Hỗ trợ auto login + detect API hoặc manual fallback.
"""

import os
import sys
import threading
import logging
from datetime import datetime
from collections import Counter

import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageEnhance

from uploader import (
    process_phase1,
    process_phase2,
    STATUS_SUCCESS,
    STATUS_PENDING_WEAK,
    STATUS_PENDING_AMBIGUOUS,
)
from api_client import (
    test_connection,
    fetch_student_list,
    fetch_all_students,
    SessionExpiredError,
    APIError,
)
from class_selector import (
    validate_class_config,
    guess_class_from_folder,
    count_images_in_folder,
)
from excel_exporter import (
    build_parent_account_rows,
    build_parent_account_rows_by_phone,
    export_parent_accounts_to_excel,
    EXPORT_MODE_GMAIL,
    EXPORT_MODE_PHONE,
)

# Playwright optional
try:
    from login_helper import (
        LoginHelper,
        run_login_flow,
        PLAYWRIGHT_AVAILABLE,
        PLAYWRIGHT_ERR,
        probe_playwright,
    )
except Exception as e:
    PLAYWRIGHT_AVAILABLE = False
    PLAYWRIGHT_ERR = str(e)
    LoginHelper = None
    run_login_flow = None


def get_playwright_probe_status():
    if not PLAYWRIGHT_AVAILABLE:
        return False, PLAYWRIGHT_ERR or "Playwright package/runtime khong kha dung."

    try:
        return probe_playwright()
    except Exception as e:
        return False, f"Playwright probe that bai: {e}"

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

APP_TITLE = "Face Upload Tool - KeyTech"
APP_VERSION = "3.0.0"

DEFAULT_BASE_URL = "https://keytechvietnam.vn"
DEFAULT_PASSWORD = "ZHYT@2210"
DEFAULT_CAPTCHA = "123"
DEFAULT_FACE_END_DATE = "2029-12-31"

COLOR_BG = "#101820"
COLOR_SURFACE = "#18212c"
COLOR_SURFACE_SOFT = "#202b38"
COLOR_BORDER = "#2c3a4a"
COLOR_TEXT_MUTED = "#9ca3af"
COLOR_PRIMARY = "#2563eb"
COLOR_PRIMARY_HOVER = "#1d4ed8"
COLOR_SUCCESS = "#2d8a4e"
COLOR_SUCCESS_HOVER = "#236b3e"
COLOR_WARNING = "#d97706"
COLOR_WARNING_HOVER = "#b45309"
COLOR_DANGER = "#b83232"
COLOR_DANGER_HOVER = "#8a2424"
COLOR_NEUTRAL = "#4b5563"
COLOR_NEUTRAL_HOVER = "#374151"

PAD_X = 12
PAD_Y = 8


def resource_path(relative_path: str) -> str:
    """Lấy đường dẫn tài nguyên, tương thích với PyInstaller."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)


LOGO_PATH = resource_path(os.path.join('acset', 'KEYTECH-e1718420445743-removebg-preview.png'))
ICON_PATH = resource_path(os.path.join('acset', 'icon.ico'))


# =============================================================
# SPLASH SCREEN — Logo animation khi khởi động
# =============================================================

class SplashScreen(ctk.CTkToplevel):
    """Splash screen với logo fade-in animation."""

    def __init__(self, parent):
        super().__init__(parent)

        self.title("")
        self.overrideredirect(True)  # No title bar
        self.configure(fg_color="#1a1a2e")

        # Center on screen
        sw, sh = 480, 400
        x = (self.winfo_screenwidth() - sw) // 2
        y = (self.winfo_screenheight() - sh) // 2
        self.geometry(f"{sw}x{sh}+{x}+{y}")
        self.attributes('-topmost', True)

        # Load logo
        self._frames = []
        self._current_frame = 0
        self._logo_label = None
        self._title_label = None
        self._sub_label = None
        self._progress = None

        self._setup_ui(sw, sh)
        self._prepare_animation()
        self.after(100, self._animate)

    def _setup_ui(self, w, h):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Main frame with rounded corners effect
        main = ctk.CTkFrame(self, fg_color="#1a1a2e", corner_radius=20)
        main.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        main.grid_columnconfigure(0, weight=1)

        # Logo
        self._logo_label = ctk.CTkLabel(main, text="")
        self._logo_label.grid(row=0, column=0, pady=(50, 10))

        # Title
        self._title_label = ctk.CTkLabel(
            main, text="Face Upload Tool",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#e0e0e0",
        )
        self._title_label.grid(row=1, column=0, pady=(5, 2))

        # Subtitle
        self._sub_label = ctk.CTkLabel(
            main, text="KeyTech AI System",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#dbeafe",
        )
        self._sub_label.grid(row=2, column=0, pady=(0, 20))

        # Progress bar
        self._progress = ctk.CTkProgressBar(
            main, width=200, height=4,
            progress_color="#00d4ff",
            fg_color="#333355",
        )
        self._progress.grid(row=3, column=0, pady=(0, 40))
        self._progress.set(0)

        # Version
        ctk.CTkLabel(
            main, text=f"v{APP_VERSION}",
            font=ctk.CTkFont(size=10),
            text_color="#555555",
        ).grid(row=4, column=0, pady=(0, 15))

    def _prepare_animation(self):
        """Tạo các frame với độ mờ tăng dần cho logo."""
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo = ImageEnhance.Brightness(logo).enhance(1.22)
            logo = ImageEnhance.Contrast(logo).enhance(1.08)
            logo = logo.resize((160, 160), Image.LANCZOS)
        except Exception:
            return

        total_frames = 12  # ~0.8s animation (nhẹ hơn 20 frames)
        r, g, b, a = logo.split()
        for i in range(total_frames + 1):
            alpha = i / total_frames  # 0.0 -> 1.0
            a_frame = a.point(lambda p, _a=alpha: int(p * _a))
            frame = Image.merge("RGBA", (r, g, b, a_frame))

            ctk_img = ctk.CTkImage(light_image=frame, dark_image=frame, size=(160, 160))
            self._frames.append(ctk_img)

    def _animate(self):
        """Chạy animation fade-in."""
        if not self._frames:
            return

        total = len(self._frames)
        if self._current_frame < total:
            self._logo_label.configure(image=self._frames[self._current_frame])
            self._progress.set(self._current_frame / (total - 1))
            self._current_frame += 1
            self.after(65, self._animate)
        else:
            # Animation done — hold for a moment
            self._progress.set(1)
            self.after(600, self._finish)

    def _finish(self):
        self.destroy()


class FaceUploadApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"{APP_TITLE} v{APP_VERSION}")
        self.geometry("1120x860")
        self.minsize(960, 760)
        self.resizable(True, True)
        self.configure(fg_color=COLOR_BG)

        # Set window icon
        if os.path.exists(ICON_PATH):
            self.iconbitmap(ICON_PATH)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._running = False
        self._stop_flag = False
        self._results = []
        self._pending = []
        self._login_helper = None
        self._manual_mode = False
        self._playwright_ready = False
        self._playwright_error = None
        self._excel_mode = False
        self._excel_export_mode = EXPORT_MODE_GMAIL  # 'gmail' or 'phone'

        # Keep references to images so they aren't GC'd
        self._watermark_img = None
        self._watermark_label = None

        self._build_ui()
        self._setup_watermark()
        self.after(0, self._probe_playwright_runtime)

    # ===================================================
    # BUILD UI
    # ===================================================

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)  # log_box stretch

        # Header with mode switch
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=PAD_X, pady=(12, 6), sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header_frame, text=f"🎓 {APP_TITLE}",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#f8fafc",
        ).grid(row=0, column=0, sticky="w")

        self.btn_excel_mode = ctk.CTkButton(
            header_frame, text="📊 Chế độ Excel", width=150, height=34,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER,
            command=self._on_toggle_excel_mode,
        )
        self.btn_excel_mode.grid(row=0, column=1, padx=(8, 0), sticky="e")

        # --- KHỐI A: Login ---
        self.frame_login = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, border_width=1, border_color=COLOR_BORDER)
        self.frame_login.grid(row=1, column=0, padx=PAD_X, pady=PAD_Y, sticky="ew")
        self.frame_login.grid_columnconfigure(1, weight=1)
        self._build_login_section(self.frame_login)

        # --- KHỐI B: Cấu hình lớp (Upload mode) ---
        self.frame_config = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, border_width=1, border_color=COLOR_BORDER)
        self.frame_config.grid(row=2, column=0, padx=PAD_X, pady=PAD_Y, sticky="ew")
        self.frame_config.grid_columnconfigure(1, weight=1)
        self._build_config_section(self.frame_config)

        # --- KHỐI B2: Excel mode (ẩn mặc định) ---
        self.frame_excel = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, border_width=1, border_color=COLOR_BORDER)
        self.frame_excel.grid_columnconfigure(1, weight=1)
        self._build_excel_section(self.frame_excel)
        # Không grid() → ẩn mặc định

        # --- KHỐI C: Header log + Log box ---
        log_header = ctk.CTkFrame(self, fg_color="transparent")
        log_header.grid(row=3, column=0, padx=PAD_X, pady=(6, 0), sticky="ew")
        log_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            log_header, text="📋 NHẬT KÝ",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#888888",
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self.btn_clear_log = ctk.CTkButton(
            log_header, text="🗑 Xóa log", width=92, height=26,
            font=ctk.CTkFont(size=11),
            fg_color=COLOR_NEUTRAL, hover_color=COLOR_NEUTRAL_HOVER,
            command=self._on_clear_log,
        )
        self.btn_clear_log.grid(row=0, column=1, sticky="e")

        self.log_box = ctk.CTkTextbox(
            self, font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word", state="normal",
            fg_color="#0b1220", border_width=1, border_color=COLOR_BORDER,
        )
        self.log_box.grid(row=4, column=0, padx=PAD_X, pady=(2, 6), sticky="nsew")

        # Cấu hình tag màu cho log
        self.log_box.tag_config("success",  foreground="#4ade80")  # xanh lá
        self.log_box.tag_config("error",    foreground="#f87171")  # đỏ
        self.log_box.tag_config("warning",  foreground="#fbbf24")  # vàng
        self.log_box.tag_config("info",     foreground="#60a5fa")  # xanh dương
        self.log_box.tag_config("pending",  foreground="#c084fc")  # tím
        self.log_box.tag_config("skip",     foreground="#94a3b8")  # xám
        self.log_box.tag_config("sep",      foreground="#374151")  # xám tối (separator)
        self.log_box.tag_config("critical", foreground="#ff6b35")  # cam đồ
        self.log_box.tag_config("ts",       foreground="#555566")  # timestamp
        self.log_box.tag_config("normal",   foreground="#d1d5db")  # trắng xám

        # Stats bar
        self.lbl_stats = ctk.CTkLabel(
            self, text="Chưa chạy", anchor="w",
            font=ctk.CTkFont(size=11), text_color="#aaaaaa",
            fg_color=COLOR_SURFACE_SOFT, corner_radius=6,
        )
        self.lbl_stats.grid(row=5, column=0, padx=PAD_X, pady=(0, 10), sticky="ew")

        self._log("🎓 Sẵn sàng. Đăng nhập hoặc dùng cấu hình thủ công.")
        if not PLAYWRIGHT_AVAILABLE:
            self._log(
                f"⚠ Playwright không khả dụng do package/runtime: "
                f"{PLAYWRIGHT_ERR or 'không import được module'}"
            )
            self._log("ℹ Auto login tạm tắt. Bạn vẫn có thể dùng cấu hình thủ công.")

    def _setup_watermark(self):
        """Đặt logo mờ làm watermark nền cho cửa sổ chính."""
        pass  # Đã tắt vì logo hiện đè lên chữ trong log_box

    def _build_login_section(self, parent):
        parent.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            parent, text="🔐 Đăng nhập",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#f8fafc",
        ).grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w", columnspan=3)

        # Username
        ctk.CTkLabel(parent, text="Username:", width=110, anchor="w", text_color=COLOR_TEXT_MUTED).grid(
            row=1, column=0, padx=(12, 8), pady=(4, 12), sticky="w")
        self.entry_username = ctk.CTkEntry(parent, placeholder_text="Tên đăng nhập", height=32)
        self.entry_username.grid(row=1, column=1, padx=0, pady=(4, 12), sticky="ew")
        self.entry_username.bind("<Return>", lambda e: self._on_login())

        # Buttons
        btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        btn_frame.grid(row=1, column=2, padx=(12, 12), pady=(4, 12), sticky="e")

        self.btn_login = ctk.CTkButton(
            btn_frame, text="🔐 Đăng nhập", width=130, height=30,
            fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS_HOVER,
            command=self._on_login,
            state="disabled",
        )
        self.btn_login.grid(row=0, column=0, padx=(0, 6))

        ctk.CTkButton(
            btn_frame, text="✋ Thủ công", width=100, height=30,
            fg_color=COLOR_NEUTRAL, hover_color=COLOR_NEUTRAL_HOVER,
            command=self._on_manual_mode,
        ).grid(row=0, column=1, padx=(0, 6))

        self.btn_close_browser = ctk.CTkButton(
            btn_frame, text="🌐 Đóng browser", width=120, height=30,
            fg_color=COLOR_WARNING, hover_color=COLOR_WARNING_HOVER,
            command=self._on_close_browser,
            state="disabled",
        )
        self.btn_close_browser.grid(row=0, column=2)

    def _build_config_section(self, parent):
        parent.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            parent, text="📚 Cấu hình lớp",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#f8fafc",
        ).grid(row=0, column=0, padx=12, pady=(10, 6), sticky="w", columnspan=3)

        fields = [
            ("Base URL:", "entry_base_url", DEFAULT_BASE_URL),
            ("JSESSIONID:", "entry_session", ""),
            ("Lớp:", "entry_class_name", ""),
            ("API List URL:", "entry_api_url", ""),
            ("Face End Date:", "entry_face_date", DEFAULT_FACE_END_DATE),
        ]

        for i, (label, attr, default) in enumerate(fields, 1):
            ctk.CTkLabel(parent, text=label, width=120, anchor="w", text_color=COLOR_TEXT_MUTED).grid(
                row=i, column=0, padx=(12, 8), pady=3, sticky="w")
            entry_kwargs = {"height": 32}
            if attr == "entry_session":
                entry_kwargs["show"] = "*"
                entry_kwargs["placeholder_text"] = "Dán JSESSIONID tại đây"
            elif attr == "entry_api_url":
                entry_kwargs["placeholder_text"] = "Tự nhận diện hoặc dán API List URL"
            elif attr == "entry_class_name":
                entry_kwargs["placeholder_text"] = "Tên lớp"
            entry = ctk.CTkEntry(parent, **entry_kwargs)
            entry.grid(row=i, column=1, padx=(0, 12), pady=3, sticky="ew", columnspan=2)
            if default:
                entry.insert(0, default)
            setattr(self, attr, entry)

        # Folder ảnh row
        row_folder = len(fields) + 1
        ctk.CTkLabel(parent, text="Folder ảnh:", width=120, anchor="w", text_color=COLOR_TEXT_MUTED).grid(
            row=row_folder, column=0, padx=(12, 8), pady=3, sticky="w")

        folder_frame = ctk.CTkFrame(parent, fg_color="transparent")
        folder_frame.grid(row=row_folder, column=1, padx=(0, 12), pady=3, sticky="ew", columnspan=2)
        folder_frame.grid_columnconfigure(0, weight=1)

        self.entry_folder = ctk.CTkEntry(folder_frame, placeholder_text="Chọn thư mục ảnh", height=32)
        self.entry_folder.grid(row=0, column=0, padx=(0, 4), sticky="ew")
        ctk.CTkButton(folder_frame, text="📂", width=44, height=32, command=self._browse_folder).grid(
            row=0, column=1)

        # Options row
        row_opt = row_folder + 1
        opt_frame = ctk.CTkFrame(parent, fg_color="transparent")
        opt_frame.grid(row=row_opt, column=1, padx=(0, 12), pady=(6, 4), sticky="w", columnspan=2)

        self.var_dry_run = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(opt_frame, text="🔍 Thử nghiệm", variable=self.var_dry_run,
                         font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(0, 12))

        self.var_skip_existing = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(opt_frame, text="⏭ Skip đã có ảnh", variable=self.var_skip_existing,
                         font=ctk.CTkFont(size=12)).grid(row=0, column=1, padx=(0, 12))

        # Action buttons row
        row_act = row_opt + 1
        act_frame = ctk.CTkFrame(parent, fg_color="transparent")
        act_frame.grid(row=row_act, column=0, padx=12, pady=(6, 12), sticky="ew", columnspan=3)
        act_frame.grid_columnconfigure(5, weight=1)

        self.btn_check_api = ctk.CTkButton(
            act_frame, text="📡 Lấy API lớp", width=120, height=32,
            fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER,
            text_color="#ffffff", text_color_disabled="#d1d5db",
            command=self._on_capture_api,
            state="disabled",
        )
        self.btn_check_api.grid(row=0, column=0, padx=(0, 6))

        self.btn_reset_detect = ctk.CTkButton(
            act_frame, text="🔄 Nhận diện lại lớp", width=140, height=32,
            fg_color=COLOR_NEUTRAL, hover_color=COLOR_NEUTRAL_HOVER,
            text_color="#ffffff", text_color_disabled="#d1d5db",
            command=self._on_reset_detect,
            state="disabled",
        )
        self.btn_reset_detect.grid(row=0, column=1, padx=(0, 6))

        self.lbl_dept_id = ctk.CTkLabel(
            act_frame, text="deptId: ???", width=80,
            text_color="#f0ad4e", font=ctk.CTkFont(weight="bold")
        )
        self.lbl_dept_id.grid(row=0, column=2, padx=(0, 6))

        self.btn_validate = ctk.CTkButton(
            act_frame, text="🔎 Kiểm tra", width=100, height=32,
            command=self._on_validate,
        )
        self.btn_validate.grid(row=0, column=3, padx=(0, 6))

        self.btn_test_conn = ctk.CTkButton(
            act_frame, text="🔌 Test kết nối", width=110, height=32,
            command=self._on_test_connection,
        )
        self.btn_test_conn.grid(row=0, column=4, padx=(0, 6))

        self.btn_start = ctk.CTkButton(
            act_frame, text="▶ Chạy", width=100, height=32,
            font=ctk.CTkFont(weight="bold"),
            fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS_HOVER,
            command=self._on_start,
        )
        self.btn_start.grid(row=1, column=0, padx=(0, 6), pady=(8, 0))

        self.btn_stop = ctk.CTkButton(
            act_frame, text="⏹ Dừng", width=80, height=32,
            fg_color=COLOR_DANGER, hover_color=COLOR_DANGER_HOVER,
            text_color="#ffffff", text_color_disabled="#d1d5db",
            command=self._on_stop, state="disabled",
        )
        self.btn_stop.grid(row=1, column=1, padx=(0, 6), pady=(8, 0))

        self.progress_bar = ctk.CTkProgressBar(act_frame, height=12, progress_color=COLOR_SUCCESS)
        self.progress_bar.grid(row=1, column=2, padx=(6, 0), pady=(8, 0), sticky="ew", columnspan=4)
        self.progress_bar.set(0)

    # ===================================================
    # LOGIN
    # ===================================================

    def _probe_playwright_runtime(self):
        self.btn_login.configure(state="disabled")

        def _worker():
            ready, error = get_playwright_probe_status()
            self.after(0, lambda: self._apply_playwright_status(ready, error))

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_playwright_status(self, ready: bool, error: str | None):
        self._playwright_ready = ready
        self._playwright_error = error
        self.btn_login.configure(state="normal" if ready else "disabled")

        if ready:
            self._log("✅ Playwright sẵn sàng. Auto login khả dụng.")
        else:
            detail = error or "Không rõ nguyên nhân"
            self._log(f"⚠ Playwright runtime lỗi: {detail}")
            self._log("ℹ Auto login tạm tắt. Bạn vẫn có thể dùng cấu hình thủ công.")

    def _on_login(self):
        if not self._playwright_ready:
            detail = self._playwright_error or PLAYWRIGHT_ERR or "Playwright không khả dụng."
            messagebox.showerror(
                "Lỗi Playwright",
                "Auto login không khả dụng.\n\n"
                f"Chi tiết: {detail}\n\n"
                "Hãy dùng cấu hình thủ công hoặc rebuild lại bản đóng gói.",
            )
            return

        username = self.entry_username.get().strip()
        if not username:
            messagebox.showerror("Lỗi", "Nhập tên đăng nhập")
            return

        base_url = self.entry_base_url.get().strip() or DEFAULT_BASE_URL
        self.btn_login.configure(state="disabled")

        self._login_helper = run_login_flow(
            base_url=base_url,
            username=username,
            password=DEFAULT_PASSWORD,
            captcha=DEFAULT_CAPTCHA,
            on_log=self._on_log_callback,
            on_api_detected=self._on_api_auto_detected,
            on_complete=lambda ok, helper: self.after(0, lambda: self._on_login_complete(ok, helper)),
        )

    def _on_login_complete(self, success, helper):
        self.btn_login.configure(state="normal")
        self._login_helper = helper

        if success and helper.jsessionid:
            # Fill session
            self.entry_session.delete(0, 'end')
            self.entry_session.insert(0, helper.jsessionid)

            if helper.base_url:
                self.entry_base_url.delete(0, 'end')
                self.entry_base_url.insert(0, helper.base_url)

            self.btn_close_browser.configure(state="normal")
            self.btn_check_api.configure(state="normal")
            self.btn_reset_detect.configure(state="normal")

            self._log("✅ Session đã được áp dụng. Hãy chọn lớp trên browser, tool sẽ bắt API URL.")
            self._log("💡 Mở đúng trang danh sách HS của lớp cần upload trên browser hỗ trợ.")
        else:
            self._log("❌ Login không thành công. Hãy thử lại hoặc dùng cấu hình thủ công.")

    def _on_manual_mode(self):
        self._manual_mode = True
        self._log("✋ Chế độ thủ công — nhập JSESSIONID và API URL bằng tay.")
        self._log("ℹ  Copy JSESSIONID từ browser DevTools → Application → Cookies")
        self._log("ℹ  Copy API URL từ browser DevTools → Network → request list?staffType=S...")

    def _on_close_browser(self):
        if self._login_helper:
            def _close():
                self._login_helper.close_browser()
            threading.Thread(target=_close, daemon=True).start()
        self.btn_close_browser.configure(state="disabled")
        self.btn_check_api.configure(state="disabled")
        self.btn_reset_detect.configure(state="disabled")

    def _on_capture_api(self):
        """Lấy API URL đã detect từ browser listener (thủ công)."""
        if not self._login_helper or not self._login_helper.is_browser_open:
            self._log("⚠ Browser không còn mở. Mở lại hoặc paste API URL thủ công.")
            return

        # Read cached session (already extracted on Playwright thread)
        cached_session = self._login_helper.jsessionid
        if cached_session:
            self.entry_session.delete(0, 'end')
            self.entry_session.insert(0, cached_session)

        # Lấy API URL + deptId + class_name
        url, dept_id, class_name = self._login_helper.get_detected_api()
        if url and dept_id:
            self.entry_api_url.delete(0, 'end')
            self.entry_api_url.insert(0, url)
            self.lbl_dept_id.configure(text=f"deptId: {dept_id}")
            if class_name:
                self.entry_class_name.delete(0, 'end')
                self.entry_class_name.insert(0, class_name)
            self._log(f"✅ Đã nhận diện lớp! {class_name or ''} (deptId: {dept_id})")
            self._log("👉 Bạn có thể tiếp tục Kiểm tra & Upload.")
        else:
            self._log("⚠ Chưa phát hiện API hợp lệ của lớp.")
            self._log("👉 Hãy click vào một lớp cụ thể trên danh sách bên trái web.")

    def _on_api_auto_detected(self, api_url: str, dept_id: int, jsessionid: str = None, class_name: str = None):
        """Callback từ listener khi detect được API — tự động cập nhật UI."""
        def _update():
            # Update session if extracted from request
            if jsessionid:
                self.entry_session.delete(0, 'end')
                self.entry_session.insert(0, jsessionid)

            # Fill API URL
            self.entry_api_url.delete(0, 'end')
            self.entry_api_url.insert(0, api_url)

            # Update deptId label
            self.lbl_dept_id.configure(text=f"deptId: {dept_id}")

            # Fill class name (tạm enable nếu đang disabled)
            if class_name:
                was_disabled = str(self.entry_class_name.cget('state')) == 'disabled'
                if was_disabled:
                    self.entry_class_name.configure(state="normal")
                self.entry_class_name.delete(0, 'end')
                self.entry_class_name.insert(0, class_name)
                if was_disabled:
                    self.entry_class_name.configure(state="disabled")

            class_display = f" | Lớp: {class_name}" if class_name else ""
            self._log(f"🎯 Đã tự động cập nhật lớp! deptId: {dept_id}{class_display}")

            # Chế độ Excel: cập nhật label + tự động xuất Excel khi detect API
            if self._excel_mode:
                self.excel_lbl_class.configure(
                    text=class_name if class_name else "Chưa chọn lớp",
                    text_color="#4ade80" if class_name else "#aaaaaa",
                )
                self._log("📊 Chế độ Excel: tự động xuất file...")
                self.after(300, self._on_export_accounts_excel)
            else:
                self._log("👉 API URL đã được điền. Bạn có thể Kiểm tra & Upload ngay.")

        # Schedule UI update on main thread (callback comes from Playwright thread)
        self.after(0, _update)

    def _on_reset_detect(self):
        """Reset listener để nhận diện lớp khác."""
        if not self._login_helper or not self._login_helper.is_browser_open:
            self._log("⚠ Browser không mở.")
            return

        self._login_helper.reset_detection()
        self.lbl_dept_id.configure(text="deptId: ???")
        self.entry_api_url.delete(0, 'end')
        self.entry_class_name.delete(0, 'end')

    # ===================================================
    # VALIDATION
    # ===================================================

    def _on_validate(self):
        class_name = self.entry_class_name.get().strip()
        api_url = self.entry_api_url.get().strip()
        folder_path = self.entry_folder.get().strip()

        self._log("🔎 Kiểm tra cấu hình lớp...")

        warnings = validate_class_config(class_name, api_url, folder_path)

        if not self.entry_session.get().strip():
            warnings.insert(0, "Chưa có JSESSIONID")

        if warnings:
            for w in warnings:
                self._log(f"⚠ {w}")
        else:
            img_count = count_images_in_folder(folder_path)
            self._log(f"✅ Cấu hình OK | Lớp: {class_name} | Folder: {img_count} ảnh")

    def _on_test_connection(self):
        base_url = self.entry_base_url.get().strip()
        jsessionid = self.entry_session.get().strip()

        if not base_url or not jsessionid:
            self._log("⚠ Cần Base URL và JSESSIONID để test")
            return

        self._log("🔌 Đang kiểm tra kết nối...")

        def _test():
            ok, msg = test_connection(base_url, jsessionid)
            self.after(0, lambda: self._log(f"{'✅' if ok else '❌'} {msg}"))

        threading.Thread(target=_test, daemon=True).start()

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Chọn thư mục chứa ảnh học sinh")
        if folder:
            self.entry_folder.delete(0, 'end')
            self.entry_folder.insert(0, folder)

            count = count_images_in_folder(folder)
            self._log(f"📁 Đã chọn: {folder} ({count} ảnh)")

            # Auto-guess class name nếu trống
            if not self.entry_class_name.get().strip():
                guessed = guess_class_from_folder(folder)
                if guessed:
                    self.entry_class_name.delete(0, 'end')
                    self.entry_class_name.insert(0, guessed)
                    self._log(f"💡 Tên lớp tự nhận diện: {guessed}")

    # ===================================================
    # START / STOP
    # ===================================================

    def _validate_before_run(self) -> bool:
        errors = []
        if not self.entry_base_url.get().strip():
            errors.append("Base URL trống")
        if not self.entry_session.get().strip():
            errors.append("JSESSIONID trống")
        if not self.entry_api_url.get().strip():
            errors.append("API List URL trống")

        folder = self.entry_folder.get().strip()
        if not folder:
            errors.append("Chưa chọn folder ảnh")
        elif not os.path.isdir(folder):
            errors.append(f"Folder không tồn tại: {folder}")

        if errors:
            messagebox.showerror("Thiếu thông tin", "\n".join(f"• {e}" for e in errors))
            return False

        # Class validation warnings
        class_name = self.entry_class_name.get().strip()
        api_url = self.entry_api_url.get().strip()
        warnings = validate_class_config(class_name, api_url, folder)

        if warnings and not self.var_dry_run.get():
            msg = "Cảnh báo:\n\n" + "\n".join(f"⚠ {w}" for w in warnings)
            msg += "\n\nBạn có muốn tiếp tục?"
            if not messagebox.askyesno("Cảnh báo cấu hình", msg):
                return False

        return True

    def _on_start(self):
        if self._running:
            return
        if not self._validate_before_run():
            return

        if not self.var_dry_run.get():
            class_name = self.entry_class_name.get().strip() or "(chưa nhập)"
            confirm = messagebox.askyesno(
                "⚠ Xác nhận Upload thật",
                f"Chế độ: UPLOAD THẬT\n"
                f"Lớp: {class_name}\n\n"
                f"Bạn có chắc chắn?"
            )
            if not confirm:
                return

        self._running = True
        self._stop_flag = False
        self._results = []
        self._pending = []

        if self._login_helper:
            self._login_helper.pause_listening()

        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.progress_bar.set(0)

        class_name = self.entry_class_name.get().strip() or "?"
        mode = "THỬ NGHIỆM" if self.var_dry_run.get() else "UPLOAD THẬT"
        self.lbl_stats.configure(text=f"Giai đoạn 1 | Lớp: {class_name} | {mode}")

        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self._log(f"🚀 Bắt đầu {mode} cho lớp {class_name}")

        thread = threading.Thread(target=self._run_phase1, daemon=True)
        thread.start()

    def _on_stop(self):
        self._stop_flag = True
        self._log("⛔ Đang dừng...")

    # ===================================================
    # PHASE 1
    # ===================================================

    def _run_phase1(self):
        try:
            result = process_phase1(
                api_list_url=self.entry_api_url.get().strip(),
                base_url=self.entry_base_url.get().strip(),
                jsessionid=self.entry_session.get().strip(),
                folder_path=self.entry_folder.get().strip(),
                face_end_date=self.entry_face_date.get().strip(),
                dry_run=self.var_dry_run.get(),
                skip_existing=self.var_skip_existing.get(),
                on_progress=lambda c, t: self.after(0, lambda: self.progress_bar.set(c / t) if t else None),
                on_log=self._on_log_callback,
                should_stop=lambda: self._stop_flag,
            )
            self._results = result['results']
            self._pending = result['pending']
        except Exception as e:
            self._on_log_callback(f"💥 Lỗi: {e}")
            logger.exception("Phase 1 error")

        self.after(0, self._on_phase1_complete)

    def _on_log_callback(self, message):
        self.after(0, lambda: self._log(message))

    def _on_phase1_complete(self):
        self._running = False
        self.btn_stop.configure(state="disabled")
        self.btn_start.configure(state="normal")
        self.progress_bar.set(1)

        counter = Counter(r['status'] for r in self._results)
        pending_count = len(self._pending)
        class_name = self.entry_class_name.get().strip() or "?"

        self.lbl_stats.configure(
            text=f"Lớp: {class_name} | ✅ {counter.get('success', 0)} | "
                 f"⏳ {pending_count} | ❌ {counter.get('not_found', 0)}"
        )

        if pending_count > 0 and not self._stop_flag:
            self._log(f"\n⏳ Có {pending_count} mục chờ xác nhận...")
            self.after(300, self._open_pending_dialog)
        else:
            if self._stop_flag:
                self._log("⛔ Đã dừng.")
            else:
                self._log("✅ Hoàn tất — không có mục pending.")
            if self._login_helper:
                self._login_helper.resume_listening()

    # ===================================================
    # PENDING DIALOG
    # ===================================================

    def _open_pending_dialog(self):
        dialog = PendingReviewDialog(self, self._pending, self._on_pending_confirmed)
        dialog.grab_set()

    def _on_pending_confirmed(self, pending_items):
        self._pending = pending_items

        selected = [p for p in pending_items if p.get('is_selected') and p.get('selected_student')]
        if not selected:
            self._log("ℹ Không có mục nào được chọn. Kết thúc.")
            self._running = False
            self.btn_start.configure(state="normal")
            if self._login_helper:
                self._login_helper.resume_listening()
            return

        self._running = True
        self._stop_flag = False
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.lbl_stats.configure(text="Giai đoạn 2 — Đang upload mục đã duyệt...")

        thread = threading.Thread(target=self._run_phase2, daemon=True)
        thread.start()

    def _run_phase2(self):
        try:
            phase2_results = process_phase2(
                pending_items=self._pending,
                base_url=self.entry_base_url.get().strip(),
                jsessionid=self.entry_session.get().strip(),
                face_end_date=self.entry_face_date.get().strip(),
                dry_run=self.var_dry_run.get(),
                on_log=self._on_log_callback,
                should_stop=lambda: self._stop_flag,
            )
            self._results.extend(phase2_results)
        except Exception as e:
            self._on_log_callback(f"💥 Lỗi giai đoạn 2: {e}")

        self.after(0, self._on_phase2_complete)

    def _on_phase2_complete(self):
        self._running = False
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")

        if self._login_helper:
            self._login_helper.resume_listening()

        counter = Counter(r['status'] for r in self._results)
        self._log("─" * 55)
        self._log("✅ Hoàn tất toàn bộ (Giai đoạn 1 + 2)")
        self.lbl_stats.configure(
            text=f"Hoàn thành | ✅ {counter.get('success', 0)} | "
                 f"❌ {counter.get('not_found', 0)} | 💥 {counter.get('upload_failed', 0)}"
        )

    # ===================================================
    # CHẾ ĐỘ XUẤT EXCEL TÀI KHOẢN PHỤ HUYNH
    # ===================================================

    def _on_export_mode_changed(self, value: str):
        """Callback khi người dùng chọn chế độ xuất Gmail/SĐT."""
        self._excel_export_mode = value
        if value == EXPORT_MODE_GMAIL:
            self._log("📧 Chế độ xuất: Tài khoản theo Gmail")
        else:
            self._log("📱 Chế độ xuất: Tài khoản theo SĐT phụ huynh")

    def _build_excel_section(self, parent):
        """Xây dựng giao diện riêng cho chế độ xuất Excel."""
        ctk.CTkLabel(
            parent, text="📊 Xuất Excel tài khoản phụ huynh",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#f8fafc",
        ).grid(row=0, column=0, padx=12, pady=(10, 6), sticky="w", columnspan=3)

        # Base URL (dùng chung với entry_base_url ở frame_config, nên tạo label tham chiếu)
        ctk.CTkLabel(parent, text="Base URL:", width=120, anchor="w", text_color=COLOR_TEXT_MUTED).grid(
            row=1, column=0, padx=(12, 8), pady=3, sticky="w")
        self.excel_lbl_base_url = ctk.CTkLabel(
            parent, text=DEFAULT_BASE_URL, anchor="w",
            text_color="#cbd5e1", font=ctk.CTkFont(size=12),
        )
        self.excel_lbl_base_url.grid(row=1, column=1, padx=(0, 12), pady=3, sticky="ew", columnspan=2)

        # Session status
        ctk.CTkLabel(parent, text="Session:", width=120, anchor="w", text_color=COLOR_TEXT_MUTED).grid(
            row=2, column=0, padx=(12, 8), pady=3, sticky="w")
        self.excel_lbl_session = ctk.CTkLabel(
            parent, text="Chưa đăng nhập", anchor="w",
            text_color="#f87171", font=ctk.CTkFont(size=12),
        )
        self.excel_lbl_session.grid(row=2, column=1, padx=(0, 12), pady=3, sticky="ew", columnspan=2)

        # Lớp đã detect
        ctk.CTkLabel(parent, text="Lớp:", width=120, anchor="w", text_color=COLOR_TEXT_MUTED).grid(
            row=3, column=0, padx=(12, 8), pady=3, sticky="w")
        self.excel_lbl_class = ctk.CTkLabel(
            parent, text="Chưa chọn lớp", anchor="w",
            text_color="#cbd5e1", font=ctk.CTkFont(size=12),
        )
        self.excel_lbl_class.grid(row=3, column=1, padx=(0, 12), pady=3, sticky="ew", columnspan=2)

        # Chế độ xuất: Gmail / SĐT
        ctk.CTkLabel(parent, text="Tài khoản theo:", width=120, anchor="w", text_color=COLOR_TEXT_MUTED).grid(
            row=4, column=0, padx=(12, 8), pady=(8, 4), sticky="w")

        self.var_excel_export_mode = ctk.StringVar(value=EXPORT_MODE_GMAIL)
        self.seg_export_mode = ctk.CTkSegmentedButton(
            parent,
            values=[EXPORT_MODE_GMAIL, EXPORT_MODE_PHONE],
            variable=self.var_excel_export_mode,
            command=self._on_export_mode_changed,
            width=240, height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            selected_color=COLOR_WARNING,
            selected_hover_color=COLOR_WARNING_HOVER,
            unselected_color=COLOR_SURFACE_SOFT,
            unselected_hover_color=COLOR_NEUTRAL,
        )
        self.seg_export_mode.grid(row=4, column=1, padx=(0, 12), pady=(8, 4), sticky="w", columnspan=2)
        try:
            for btn_key in self.seg_export_mode._buttons_dict:
                if btn_key == EXPORT_MODE_GMAIL:
                    self.seg_export_mode._buttons_dict[btn_key].configure(text="📧 Gmail")
                elif btn_key == EXPORT_MODE_PHONE:
                    self.seg_export_mode._buttons_dict[btn_key].configure(text="📱 SĐT")
        except Exception:
            pass

        # Action buttons
        excel_act = ctk.CTkFrame(parent, fg_color="transparent")
        excel_act.grid(row=5, column=0, padx=12, pady=(8, 12), sticky="ew", columnspan=3)
        excel_act.grid_columnconfigure(1, weight=1)

        self.btn_export_excel = ctk.CTkButton(
            excel_act, text="📥 Xuất Excel", width=140, height=34,
            fg_color=COLOR_WARNING, hover_color=COLOR_WARNING_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_export_accounts_excel,
        )
        self.btn_export_excel.grid(row=0, column=0, padx=(0, 8))

        self.excel_lbl_hint = ctk.CTkLabel(
            excel_act,
            text="💡 Click lớp trên browser → tool tự động xuất, hoặc bấm nút xuất thủ công.",
            font=ctk.CTkFont(size=11), text_color="#888888", anchor="w",
            wraplength=620,
        )
        self.excel_lbl_hint.grid(row=0, column=1, sticky="ew")

    def _on_toggle_excel_mode(self):
        """Chuyển đổi giữa giao diện Upload và Excel."""
        self._excel_mode = not self._excel_mode

        if self._excel_mode:
            # Ẩn frame upload, hiện frame excel
            self.frame_config.grid_forget()
            self.frame_excel.grid(row=2, column=0, padx=PAD_X, pady=PAD_Y, sticky="ew")

            self.btn_excel_mode.configure(
                text="🔙 Chế độ Upload",
                fg_color=COLOR_WARNING, hover_color=COLOR_WARNING_HOVER,
            )

            # Cập nhật thông tin hiển thị trên frame excel
            base_url = self.entry_base_url.get().strip() or DEFAULT_BASE_URL
            self.excel_lbl_base_url.configure(text=base_url)

            jsessionid = self.entry_session.get().strip()
            if jsessionid:
                short = jsessionid[:12] + "..." if len(jsessionid) > 12 else jsessionid
                self.excel_lbl_session.configure(text=f"✅ {short}", text_color="#4ade80")
            else:
                self.excel_lbl_session.configure(text="❌ Chưa đăng nhập", text_color="#f87171")

            class_name = self.entry_class_name.get().strip()
            self.excel_lbl_class.configure(
                text=class_name if class_name else "Chưa chọn lớp",
                text_color="#4ade80" if class_name else "#aaaaaa",
            )

            self._log("━" * 55)
            self._log("📊 CHUYỂN SANG CHẾ ĐỘ XUẤT EXCEL")
            self._log("━" * 55)

            # Cho phép bắt mọi staff/list request
            if self._login_helper:
                self._login_helper._require_dept_list = False
                if self._login_helper.is_browser_open:
                    self._login_helper.reset_detection()

            if not jsessionid:
                self._log("⚠ Chưa có JSESSIONID — hãy đăng nhập trước hoặc nhập thủ công.")
            else:
                self._log("👉 Bấm nút [📥 Xuất Excel] để xuất file.")
                self._log("👉 Hoặc click lớp trên browser → tool tự động xuất.")
        else:
            # Ẩn frame excel, hiện frame upload
            self.frame_excel.grid_forget()
            self.frame_config.grid(row=2, column=0, padx=PAD_X, pady=PAD_Y, sticky="ew")

            self.btn_excel_mode.configure(
                text="📊 Chế độ Excel",
                fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER,
            )
            self._log("📊 Đã quay về chế độ Upload.")

            # Khôi phục yêu cầu deptList cho chế độ upload
            if self._login_helper:
                self._login_helper._require_dept_list = True

    def _on_export_accounts_excel(self):
        """Xuất Excel tài khoản phụ huynh từ API URL hiện tại."""
        # Validate đầu vào
        api_url = self.entry_api_url.get().strip()
        jsessionid = self.entry_session.get().strip()
        base_url = self.entry_base_url.get().strip()

        # Nếu chưa có API URL → tự tạo từ base_url
        if not api_url and base_url:
            api_url = base_url.rstrip('/') + '/ent/ent/staff/list?staffType=S'
            self.entry_api_url.delete(0, 'end')
            self.entry_api_url.insert(0, api_url)

        if not api_url:
            self._log("⚠ API URL trống và Base URL cũng trống — không thể xuất.")
            return

        if not jsessionid:
            self._log("⚠ JSESSIONID trống — chưa đăng nhập.")
            return

        # Chọn nơi lưu file
        class_name = self.entry_class_name.get().strip() or "TatCa"
        default_filename = f"Dsach tài khoản HS {class_name}.xlsx"
        output_path = filedialog.asksaveasfilename(
            title="Lưu file Excel tài khoản phụ huynh",
            defaultextension=".xlsx",
            filetypes=[("Excel Files", "*.xlsx")],
            initialfile=default_filename,
        )
        if not output_path:
            return  # User hủy — vẫn giữ chế độ Excel

        self.btn_excel_mode.configure(state="disabled")
        self.btn_export_excel.configure(state="disabled")
        self._log("📥 Đang xuất Excel tài khoản phụ huynh...")

        def _worker():
            try:
                # Fetch TOÀN BỘ danh sách học sinh (tự động phân trang)
                students = fetch_all_students(
                    api_url, jsessionid,
                    on_log=self._on_log_callback,
                )

                if not students:
                    self._on_log_callback("❌ Không có dữ liệu học sinh để xuất.")
                    return

                # Build rows theo chế độ đã chọn
                export_mode = self._excel_export_mode
                if export_mode == EXPORT_MODE_PHONE:
                    self._on_log_callback("📱 Đang tạo tài khoản theo SĐT phụ huynh...")
                    rows = build_parent_account_rows_by_phone(
                        students,
                        on_log=self._on_log_callback,
                    )
                else:
                    self._on_log_callback("📧 Đang tạo tài khoản theo Gmail...")
                    rows = build_parent_account_rows(
                        students,
                        on_log=self._on_log_callback,
                    )

                if not rows:
                    self._on_log_callback("❌ Không thể tạo dữ liệu tài khoản.")
                    return

                # Export to Excel
                success = export_parent_accounts_to_excel(
                    rows,
                    output_path,
                    on_log=self._on_log_callback,
                )

                if success:
                    self._on_log_callback(f"🎉 Xuất Excel thành công: {output_path}")

            except SessionExpiredError as e:
                self._on_log_callback(f"❌ Phiên đăng nhập hết hạn: {e}")
            except APIError as e:
                self._on_log_callback(f"❌ Lỗi API: {e}")
            except Exception as e:
                self._on_log_callback(f"💥 Lỗi không mong đợi: {e}")
                logger.exception("Export Excel error")
            finally:
                def _re_enable():
                    self.btn_excel_mode.configure(state="normal")
                    self.btn_export_excel.configure(state="normal")
                    # Reset detect để bắt lớp tiếp theo
                    if self._excel_mode and self._login_helper and self._login_helper.is_browser_open:
                        self._login_helper.reset_detection()
                        self._log("👉 Sẵn sàng — click lớp tiếp theo trên browser để xuất tiếp.")
                self.after(0, _re_enable)

        threading.Thread(target=_worker, daemon=True).start()

    # ===================================================
    # HELPERS
    # ===================================================

    def _on_clear_log(self):
        """Xóa toàn bộ nội dung log."""
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self._log("🗑 Log đã được xóa.")

    # Prefix → tag map cho _log (O(1) lookup thay vì scan list mỗi lần)
    _LOG_TAG_MAP = {}
    for _tag, _prefixes in [
        ("sep",     ["─", "━"]),
        ("success", ["✅", "✔", "🎉"]),
        ("error",   ["❌", "💥", "⛔"]),
        ("warning", ["⚠", "⚠️"]),
        ("skip",    ["⏭", "🔍"]),
        ("pending", ["⏳", "⌛"]),
        ("info",    ["📋", "📊", "📁", "👤", "🖼", "📡", "🎯", "📌", "🔒", "🏥", "📖",
                     "🚀", "🔄", "ℹ", "💡", "👉", "📍", "📧", "📱", "🔐", "📂", "🔙"]),
    ]:
        for _p in _prefixes:
            _LOG_TAG_MAP[_p] = _tag
    del _tag, _prefixes, _p  # cleanup class scope

    MAX_LOG_LINES = 1000  # Giới hạn dòng log để tránh chậm render

    def _log(self, message: str):
        """Ghi log có timestamp và màu sắc theo loại."""
        ts = datetime.now().strftime('%H:%M:%S')
        self.log_box.configure(state="normal")

        # Xác định tag — thử ký tự đầu tiên (emoji thường 1-2 codepoint)
        tag = "normal"
        if message:
            # Thử 1 char, rồi 2 chars (emoji có thể 2 codepoint)
            tag = self._LOG_TAG_MAP.get(message[0],
                    self._LOG_TAG_MAP.get(message[:2], "normal"))

        self.log_box.insert("end", f"[{ts}] ", "ts")
        self.log_box.insert("end", f"{message}\n", tag)
        self.log_box.see("end")

        # Trim log nếu quá dài — giữ render mượt
        line_count = int(self.log_box.index('end-1c').split('.')[0])
        if line_count > self.MAX_LOG_LINES:
            trim = line_count - self.MAX_LOG_LINES
            self.log_box.delete("1.0", f"{trim}.0")


# =====================================================
# Pending Review Dialog (giữ nguyên từ v2.1)
# =====================================================

class PendingReviewDialog(ctk.CTkToplevel):

    def __init__(self, parent, pending_items: list, on_confirm_callback):
        super().__init__(parent)
        self.title("⏳ Duyệt match yếu / mơ hồ")
        self.geometry("980x640")
        self.minsize(860, 540)
        self.resizable(True, True)
        self.configure(fg_color=COLOR_BG)

        self._pending = pending_items
        self._on_confirm = on_confirm_callback
        self._weak_vars = []
        self._ambig_combos = []

        self.protocol("WM_DELETE_WINDOW", self._on_close_window)
        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self, text="⏳ Duyệt match yếu / mơ hồ",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color="#f8fafc",
        ).grid(row=0, column=0, padx=16, pady=(14, 6), sticky="w")

        scroll = ctk.CTkScrollableFrame(
            self, label_text="",
            fg_color=COLOR_SURFACE, border_width=1, border_color=COLOR_BORDER,
        )
        scroll.grid(row=1, column=0, padx=16, pady=6, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        weak_items = [p for p in self._pending if p['status'] == STATUS_PENDING_WEAK]
        ambig_items = [p for p in self._pending if p['status'] == STATUS_PENDING_AMBIGUOUS]
        current_row = 0

        if weak_items:
            ctk.CTkLabel(scroll, text=f"⚠ Match yếu ({len(weak_items)} mục)",
                          font=ctk.CTkFont(size=14, weight="bold"), text_color="#f0ad4e",
                          ).grid(row=current_row, column=0, padx=5, pady=(10, 5), sticky="w")
            current_row += 1

            for item in weak_items:
                var = ctk.BooleanVar(value=False)
                student = item['proposed_match']
                name = student.get('staffName', '')
                sid = student.get('id', '')

                frame = ctk.CTkFrame(scroll, fg_color=COLOR_SURFACE_SOFT)
                frame.grid(row=current_row, column=0, padx=5, pady=2, sticky="ew")
                frame.grid_columnconfigure(1, weight=1)

                ctk.CTkCheckBox(frame, text="", variable=var, width=28).grid(
                    row=0, column=0, padx=(8, 4), pady=6)
                ctk.CTkLabel(frame, text=f"📄 {item['file_name']}  →  {name}  |  ID: {sid}",
                              anchor="w", font=ctk.CTkFont(family="Consolas", size=11),
                              wraplength=760,
                              ).grid(row=0, column=1, padx=(0, 8), pady=6, sticky="ew")

                self._weak_vars.append((item, var))
                current_row += 1

        if ambig_items:
            ctk.CTkLabel(scroll, text=f"🔀 Mơ hồ ({len(ambig_items)} mục)",
                          font=ctk.CTkFont(size=14, weight="bold"), text_color="#d9534f",
                          ).grid(row=current_row, column=0, padx=5, pady=(15, 5), sticky="w")
            current_row += 1

            for item in ambig_items:
                frame = ctk.CTkFrame(scroll, fg_color=COLOR_SURFACE_SOFT)
                frame.grid(row=current_row, column=0, padx=5, pady=4, sticky="ew")
                frame.grid_columnconfigure(1, weight=1)

                ctk.CTkLabel(frame, text=f"📄 {item['file_name']}",
                              font=ctk.CTkFont(family="Consolas", size=11), anchor="w",
                              wraplength=760,
                              ).grid(row=0, column=0, padx=(8, 4), pady=(6, 2), sticky="ew", columnspan=2)

                options = ["-- Bỏ qua --"]
                for c in item['candidate_matches']:
                    options.append(f"{c.get('staffName', '')} (ID: {c.get('id', '')})")

                combo_var = ctk.StringVar(value=options[0])
                ctk.CTkComboBox(frame, values=options, variable=combo_var,
                                 width=520, font=ctk.CTkFont(size=11), state="readonly",
                                 ).grid(row=1, column=0, padx=(8, 8), pady=(2, 8), sticky="w", columnspan=2)

                self._ambig_combos.append((item, combo_var))
                current_row += 1

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, padx=16, pady=(8, 14), sticky="ew")
        btn_frame.grid_columnconfigure(2, weight=1)

        if weak_items:
            ctk.CTkButton(btn_frame, text="☑ Chọn tất cả", width=120,
                           command=lambda: [v.set(True) for _, v in self._weak_vars]).grid(
                row=0, column=0, padx=(0, 6))
            ctk.CTkButton(btn_frame, text="☐ Bỏ chọn", width=100,
                           fg_color=COLOR_NEUTRAL, hover_color=COLOR_NEUTRAL_HOVER,
                           command=lambda: [v.set(False) for _, v in self._weak_vars]).grid(
                row=0, column=1, padx=(0, 6))

        ctk.CTkButton(btn_frame, text="▶ Chạy tiếp", width=140, height=34,
                       font=ctk.CTkFont(weight="bold"),
                       fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS_HOVER,
                       command=self._on_run).grid(row=0, column=3, padx=(0, 6))

        ctk.CTkButton(btn_frame, text="⏭ Bỏ qua tất cả", width=130, height=34,
                       fg_color=COLOR_DANGER, hover_color=COLOR_DANGER_HOVER,
                       command=self._on_skip_all).grid(row=0, column=4)

    def _apply_selections(self):
        for item, var in self._weak_vars:
            item['is_selected'] = var.get()
            item['selected_student'] = item['proposed_match'] if var.get() else None

        for item, combo_var in self._ambig_combos:
            text = combo_var.get()
            if text == "-- Bỏ qua --":
                item['is_selected'] = False
                item['selected_student'] = None
            else:
                for c in item['candidate_matches']:
                    if f"{c.get('staffName', '')} (ID: {c.get('id', '')})" == text:
                        item['is_selected'] = True
                        item['selected_student'] = c
                        break

    def _on_run(self):
        self._apply_selections()
        self.destroy()
        self._on_confirm(self._pending)

    def _on_skip_all(self):
        for item in self._pending:
            item['is_selected'] = False
            item['selected_student'] = None
        self.destroy()
        self._on_confirm(self._pending)

    def _on_close_window(self):
        self._on_skip_all()


def main():
    # Init hidden root for splash
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = FaceUploadApp()

    # Show splash on top of (hidden) main window
    app.withdraw()  # Hide main window during splash

    splash = SplashScreen(app)

    def _on_splash_done():
        if not splash.winfo_exists():
            app.deiconify()  # Show main window
            return
        app.after(100, _on_splash_done)

    app.after(200, _on_splash_done)
    app.mainloop()


if __name__ == '__main__':
    main()
