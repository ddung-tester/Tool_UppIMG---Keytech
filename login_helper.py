"""
Browser automation: login, session extraction, network interception.
Playwright là optional — nếu chưa cài, fallback sang manual mode.

Lưu ý quan trọng về threading:
  - Playwright sync API chỉ dispatch events trong lúc chạy API calls của nó.
  - Worker thread phải dùng page.wait_for_timeout() để pump event loop,
    KHÔNG được dùng threading.Event.wait() vì sẽ block event dispatch.
  - Mọi Playwright API (cookies, selectors, ...) phải gọi từ cùng thread
    đã khởi tạo Playwright. GUI thread (Tkinter) KHÔNG được gọi trực tiếp.
"""

import logging
import os
import threading
from typing import Callable, Optional
from urllib.parse import urlparse, parse_qs, unquote

from web_selectors import (
    LOGIN_URL_PATH,
    LOGIN_SELECTORS,
    LOGIN_SUCCESS_PATTERNS,
    STUDENT_LIST_URL_PATTERN,
    STUDENT_LIST_URL_CONTAINS,
)

logger = logging.getLogger(__name__)

PLAYWRIGHT_AVAILABLE = False
PLAYWRIGHT_ERR = None
_PLAYWRIGHT_PROBE_RESULT = None
_PLAYWRIGHT_PROBE_ERROR = None

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
    PLAYWRIGHT_AVAILABLE = True
except Exception as e:
    PLAYWRIGHT_ERR = str(e)
    logger.warning("Không tải được Playwright runtime: %s", e)


def get_playwright_status() -> tuple[bool, Optional[str]]:
    """Trạng thái import Playwright hiện tại."""
    return PLAYWRIGHT_AVAILABLE, PLAYWRIGHT_ERR


def _find_embedded_browser_path() -> Optional[str]:
    """
    Tìm Chromium đã nhúng sẵn trong playwright/driver/package/.local-browsers.
    Return absolute path tới chrome.exe nếu tìm thấy.
    """
    try:
        import playwright
    except Exception:
        return None

    package_root = os.path.join(os.path.dirname(playwright.__file__), 'driver', 'package', '.local-browsers')
    if not os.path.isdir(package_root):
        return None

    candidates = []
    for name in os.listdir(package_root):
        if not name.startswith('chromium-'):
            continue
        chrome_path = os.path.join(package_root, name, 'chrome-win', 'chrome.exe')
        if os.path.isfile(chrome_path):
            candidates.append(chrome_path)

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0]


def probe_playwright(force: bool = False) -> tuple[bool, Optional[str]]:
    """
    Kiểm tra toàn bộ runtime Playwright: import sync API + có browser bundle + launch/close được.
    Kết quả được cache để không kiểm tra lại không cần thiết.
    """
    global _PLAYWRIGHT_PROBE_RESULT, _PLAYWRIGHT_PROBE_ERROR

    if not force and _PLAYWRIGHT_PROBE_RESULT is not None:
        return _PLAYWRIGHT_PROBE_RESULT, _PLAYWRIGHT_PROBE_ERROR

    if not PLAYWRIGHT_AVAILABLE:
        _PLAYWRIGHT_PROBE_RESULT = False
        _PLAYWRIGHT_PROBE_ERROR = PLAYWRIGHT_ERR or "Khong import duoc playwright.sync_api"
        return _PLAYWRIGHT_PROBE_RESULT, _PLAYWRIGHT_PROBE_ERROR

    playwright_instance = None
    browser = None
    try:
        playwright_instance = sync_playwright().start()
        try:
            browser = playwright_instance.chromium.launch(headless=True)
        except Exception:
            browser_path = _find_embedded_browser_path()
            if not browser_path:
                raise RuntimeError(
                    "Không khởi được Chromium mặc định và không tìm thấy browser cài sẵn"
                )
            browser = playwright_instance.chromium.launch(headless=True, executable_path=browser_path)
        _PLAYWRIGHT_PROBE_RESULT = True
        _PLAYWRIGHT_PROBE_ERROR = None
    except Exception as e:
        _PLAYWRIGHT_PROBE_RESULT = False
        _PLAYWRIGHT_PROBE_ERROR = f"Playwright import OK nhưng không khởi chạy được Chromium: {e}"
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        if playwright_instance:
            try:
                playwright_instance.stop()
            except Exception:
                pass

    return _PLAYWRIGHT_PROBE_RESULT, _PLAYWRIGHT_PROBE_ERROR


def extract_dept_ids(url: str) -> list:
    """
    Trích deptList từ URL.
    VD: deptList=%5B9291%5D → [9291]
    Returns list of int. Empty nếu không có/invalid.
    """
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        raw = params.get('deptList', [''])[0]
        raw = unquote(raw).strip('[]')
        if not raw:
            return []
        parts = [p.strip() for p in raw.split(',') if p.strip()]
        return [int(p) for p in parts]
    except (ValueError, IndexError):
        return []


class LoginHelper:
    """Quản lý browser lifecycle: login, extract session, intercept requests."""

    def __init__(self, on_log: Optional[Callable] = None, on_api_detected: Optional[Callable] = None):
        self._on_log = on_log
        self._on_api_detected = on_api_detected
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._jsessionid = None
        self._base_url = None

        # API detect state
        self._detected_api_url = None
        self._detected_dept_id = None
        self._detected_class_name = None
        self._listening_active = False
        self._skip_count = 0

        # Thread lifecycle: keeps Playwright thread alive until browser is closed
        self._browser_closed_event = threading.Event()

    def log(self, msg):
        logger.info(msg)
        if self._on_log:
            self._on_log(msg)

    @property
    def is_available(self):
        return PLAYWRIGHT_AVAILABLE

    @property
    def is_browser_open(self):
        return self._page is not None and not self._page.is_closed()

    @property
    def jsessionid(self):
        return self._jsessionid

    @property
    def base_url(self):
        return self._base_url

    @property
    def detected_api_url(self):
        return self._detected_api_url

    @property
    def detected_dept_id(self):
        return self._detected_dept_id

    def _find_element(self, page, selector_key: str, timeout=5000):
        """Thử từng selector fallback cho đến khi tìm được."""
        selectors = LOGIN_SELECTORS.get(selector_key, [])
        for sel in selectors:
            try:
                el = page.wait_for_selector(sel, timeout=timeout)
                if el:
                    logger.debug("Selector '%s' matched: %s", selector_key, sel)
                    return el
            except PwTimeout:
                logger.debug("Selector '%s' không match: %s", selector_key, sel)
                continue
        self.log(f"⚠ Không tìm thấy element '{selector_key}'")
        return None

    def open_browser(self, base_url: str):
        """Mở Chromium, navigate đến trang login."""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(PLAYWRIGHT_ERR or "Playwright khong kha dung")

        self._base_url = base_url.rstrip('/')
        login_url = self._base_url + LOGIN_URL_PATH
        self.log("🌐 Đang mở trình duyệt...")

        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.launch(headless=False)
        except Exception as launch_err:
            browser_path = _find_embedded_browser_path()
            if not browser_path:
                raise RuntimeError(f"Không mở được trình duyệt: {launch_err}") from launch_err
            self._browser = self._playwright.chromium.launch(
                headless=False,
                executable_path=browser_path,
            )
        self._context = self._browser.new_context(
            viewport={'width': 1280, 'height': 800},
            ignore_https_errors=True,
        )
        self._page = self._context.new_page()

        # Listen network requests & responses
        self._page.on("request", self._on_network_request)
        self._page.on("response", self._on_network_response)

        self._page.goto(login_url, wait_until='domcontentloaded', timeout=15000)
        self.log(f"🌐 Đã mở: {login_url}")

    def fill_and_login(self, username: str, password: str, captcha: str):
        """Điền form login và submit."""
        if not self._page:
            raise RuntimeError("Browser chưa mở")

        self.log(f"🔐 Đang điền thông tin đăng nhập | username: {username}")

        el_user = self._find_element(self._page, 'username')
        if el_user:
            el_user.fill('')
            el_user.fill(username)

        el_pass = self._find_element(self._page, 'password')
        if el_pass:
            el_pass.fill('')
            el_pass.fill(password)
            self.log("🔑 Password đã được áp dụng")

        el_captcha = self._find_element(self._page, 'captcha')
        if el_captcha:
            el_captcha.fill('')
            el_captcha.fill(captcha)
            self.log(f"🔢 Captcha đã được áp dụng: {captcha}")

        self.log("🚀 Đang gửi đăng nhập...")
        el_submit = self._find_element(self._page, 'submit')
        if el_submit:
            el_submit.click()
        else:
            self.log("⚠ Không tìm thấy nút đăng nhập, thử Enter...")
            if el_captcha:
                el_captcha.press('Enter')

    def wait_for_login_result(self, timeout=10000) -> bool:
        """Chờ login xong. Returns True nếu thành công."""
        if not self._page:
            return False

        try:
            self._page.wait_for_load_state('networkidle', timeout=timeout)
        except PwTimeout:
            pass

        current_url = self._page.url
        self.log(f"📍 URL sau login: {current_url}")

        for pattern in LOGIN_SUCCESS_PATTERNS:
            if pattern in current_url:
                self.log("✅ Đăng nhập thành công")
                return True

        try:
            error_el = self._page.query_selector('.error-msg, .el-message--error, [class*="error"]')
            if error_el:
                error_text = error_el.inner_text().strip()
                if error_text:
                    self.log(f"❌ Đăng nhập thất bại: {error_text}")
                    return False
        except Exception:
            pass

        self.log("⚠ Không chắc chắn login thành công hay thất bại")
        return False

    def extract_session(self) -> Optional[str]:
        """Đọc JSESSIONID từ cookies."""
        if not self._context:
            return None

        cookies = self._context.cookies()
        for c in cookies:
            if c['name'] == 'JSESSIONID':
                self._jsessionid = c['value']
                self.log(f"🍪 Đã lấy JSESSIONID: {self._jsessionid[:16]}...")
                return self._jsessionid

        self.log("⚠ Không tìm thấy cookie JSESSIONID")
        return None

    # ===================================================
    # NETWORK INTERCEPTION — API DETECT
    # ===================================================

    def start_listening(self):
        """Bắt đầu lắng nghe request API lớp. Gọi sau khi login thành công."""
        self._listening_active = True
        self._detected_api_url = None
        self._detected_dept_id = None
        self._skip_count = 0
        self.log("📡 Đang lắng nghe request API lớp...")
        self.log("👉 Vui lòng click vào lớp cần upload trên trình duyệt")

    def pause_listening(self):
        """Tạm dừng nhận diện (khi đang chạy tiến trình)."""
        self._listening_active = False
        self.log("⏸ Tạm dừng nhận diện lớp trên trình duyệt.")

    def resume_listening(self):
        """Tiếp tục nhận diện."""
        self._listening_active = True
        self.log("▶ Tiếp tục nhận diện lớp trên trình duyệt.")

    def reset_detection(self):
        """Reset để detect lại lớp khác."""
        self._detected_api_url = None
        self._detected_dept_id = None
        self._detected_class_name = None
        self._skip_count = 0
        self._listening_active = True
        self.log("🔄 Đã reset — sẵn sàng nhận diện lớp mới")
        self.log("👉 Vui lòng click vào lớp cần upload trên trình duyệt")

    def _on_network_request(self, request):
        """
        Lắng nghe mọi request. Chỉ capture request hợp lệ:
        - Phải có staff/list
        - Phải có deptList
        - deptList phải chứa đúng 1 ID
        - Cập nhật liên tục theo URL cuối cùng
        """
        if not self._listening_active:
            return

        try:
            url = request.url

            # Chỉ quan tâm request staff/list
            if 'staff/list' not in url:
                return

            self.log(f"📡 Bắt được request: ...{url.split('?')[0].split('/')[-1]}?...")

            # RULE 1: Phải có deptList
            if STUDENT_LIST_URL_CONTAINS not in url:
                self._skip_count += 1
                self.log(f"ℹ Bỏ qua request staff/list không có deptList (lần #{self._skip_count})")
                return

            # RULE 2: deptList phải chứa đúng 1 ID
            dept_ids = extract_dept_ids(url)

            if len(dept_ids) == 0:
                self.log("ℹ Bỏ qua: deptList rỗng")
                return

            if len(dept_ids) > 1:
                self.log(f"ℹ Bỏ qua: deptList có {len(dept_ids)} ID (chỉ chấp nhận 1)")
                return

            # RULE 3+4: Cập nhật liên tục URL cuối cùng
            dept_id = dept_ids[0]
            
            # Ghi nhận URL mới và reset class name để response handler lấy tên lớp mới
            if self._detected_api_url != url:
                self._detected_api_url = url
                self._detected_dept_id = dept_id
                self._detected_class_name = None

            # Extract session from request cookies (thread-safe)
            jsessionid = None
            try:
                cookie_header = request.headers.get('cookie', '')
                for part in cookie_header.split(';'):
                    part = part.strip()
                    if part.startswith('JSESSIONID='):
                        jsessionid = part.split('=', 1)[1]
                        self._jsessionid = jsessionid
                        break
            except Exception:
                pass

            self.log(f"🎯 Đã cập nhật API lớp mới!")
            self.log(f"📌 deptId: {dept_id}")
            self.log("⏳ Đang chờ response để lấy tên lớp...")

        except Exception as e:
            logger.debug("Ấy sinh lỗi trong network handler: %s", e)

    def _on_network_response(self, response):
        """
        Bắt response của request đã detect.
        Trích tên lớp từ dữ liệu học sinh và notify GUI.
        """
        if not self._detected_api_url:
            return
        # Chỉ xử lý response của URL đã detect (và chưa có class_name)
        if self._detected_class_name:
            return

        try:
            url = response.url
            if 'staff/list' not in url or STUDENT_LIST_URL_CONTAINS not in url:
                return

            if response.status != 200:
                return

            # Parse response body để lấy tên lớp
            body = response.json()
            class_name = self._extract_class_name(body)

            if class_name:
                self._detected_class_name = class_name
                self.log(f"🏫 Tên lớp: {class_name}")

            # Extract jsessionid from request headers
            jsessionid = self._jsessionid

            # Notify GUI with all info
            if self._on_api_detected:
                try:
                    self._on_api_detected(
                        self._detected_api_url,
                        self._detected_dept_id,
                        jsessionid,
                        class_name,
                    )
                except Exception as cb_err:
                    logger.debug("on_api_detected callback error: %s", cb_err)

        except Exception as e:
            logger.debug("Ấy sinh lỗi trong response handler: %s", e)

    def _extract_class_name(self, data) -> Optional[str]:
        """Trích tên lớp từ response JSON (deptName của học sinh đầu tiên)."""
        students = None

        if isinstance(data, list):
            students = data
        elif isinstance(data, dict):
            # Tìm list học sinh trong các key phổ biến
            for key in ('rows', 'data', 'list', 'items', 'records', 'content', 'result'):
                if key in data and isinstance(data[key], list) and len(data[key]) > 0:
                    students = data[key]
                    break

        if not students or len(students) == 0:
            return None

        # Lấy tên lớp từ học sinh đầu tiên
        first = students[0]
        if isinstance(first, dict):
            for field in ('deptName', 'departmentName', 'dept_name', 'className', 'class_name'):
                val = first.get(field, '')
                if val and isinstance(val, str):
                    return val.strip()

        return None

    def get_detected_api(self) -> tuple:
        """
        Returns (api_url, dept_id, class_name) nếu đã detect được.
        Returns (None, None, None) nếu chưa.
        """
        return self._detected_api_url, self._detected_dept_id, self._detected_class_name

    # ===================================================
    # BROWSER LIFECYCLE
    # ===================================================

    def close_browser(self):
        """Đóng browser và cleanup."""
        self._listening_active = False
        # Signal the worker thread to exit
        self._browser_closed_event.set()
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as e:
            logger.debug("Error closing browser: %s", e)
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            self.log("🌐 Đã đóng trình duyệt")



def run_login_flow(
    base_url: str,
    username: str,
    password: str,
    captcha: str,
    on_log: Optional[Callable] = None,
    on_api_detected: Optional[Callable] = None,
    on_complete: Optional[Callable] = None,
):
    """
    Chạy full login flow trong background thread.
    on_complete(success: bool, helper: LoginHelper)
    """
    helper = LoginHelper(on_log=on_log, on_api_detected=on_api_detected)

    def _worker():
        success = False
        try:
            helper.open_browser(base_url)
            helper.fill_and_login(username, password, captcha)
            success = helper.wait_for_login_result()
            if success:
                helper.extract_session()
                helper.start_listening()
        except Exception as e:
            helper.log(f"❌ Lỗi login: {e}")
            logger.exception("Login flow error")

        if on_complete:
            on_complete(success, helper)

        # Keep Playwright event loop alive so network interception works.
        # IMPORTANT: Must use page.wait_for_timeout() instead of threading.Event.wait()
        # because Playwright dispatches events only during its own API calls.
        if success and helper.is_browser_open:
            helper.log("📡 Playwright đang lắng nghe request — click vào lớp trên browser...")
            try:
                while not helper._browser_closed_event.is_set() and helper.is_browser_open:
                    helper._page.wait_for_timeout(500)  # Pump Playwright event loop
            except Exception:
                pass  # Browser was closed or page navigated away
            logger.debug("Playwright worker thread đã kết thúc")

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return helper
