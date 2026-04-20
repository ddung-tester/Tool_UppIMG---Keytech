"""
Module gọi API: list học sinh, upload ảnh khuôn mặt.
"""

import os
import time
import logging
import requests
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = (10, 30)
MAX_RETRIES = 2
RETRY_DELAY = 2


def _make_session(jsessionid: str) -> requests.Session:
    sess = requests.Session()
    sess.cookies.set('JSESSIONID', jsessionid)
    sess.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'X-Requested-With': 'XMLHttpRequest',
    })
    return sess


def _request_with_retry(method, url, session, max_retries=MAX_RETRIES, **kwargs):
    kwargs.setdefault('timeout', DEFAULT_TIMEOUT)
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            resp = session.request(method, url, **kwargs)
            return resp
        except (requests.ConnectionError, requests.Timeout) as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(RETRY_DELAY)
            continue

    raise last_error


def _extract_student_list(d):
    """Tìm list học sinh trong response dict, hỗ trợ cấu trúc lồng nhau."""
    if isinstance(d, list):
        return d
    if not isinstance(d, dict):
        return None

    list_keys = ('rows', 'data', 'list', 'items', 'records', 'content', 'result')
    for key in list_keys:
        if key in d and isinstance(d[key], list):
            logger.debug("Found students under key '%s', count: %d", key, len(d[key]))
            return d[key]

    nested_keys = ('page', 'body', 'response', 'payload')
    for key in nested_keys:
        if key in d and isinstance(d[key], dict):
            logger.debug("Checking nested key '%s'", key)
            found = _extract_student_list(d[key])
            if found is not None:
                return found
        elif key in d and isinstance(d[key], list):
            return d[key]

    return None


def fetch_student_list(api_list_url: str, jsessionid: str) -> list:
    """
    Gọi API list để lấy toàn bộ học sinh.
    Returns: list các dict student record.
    Raises: SessionExpiredError, APIError
    """
    sess = _make_session(jsessionid)

    parsed = urlparse(api_list_url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params['limit'] = ['500']
    params['page'] = ['1']

    flat_params = {k: v[0] for k, v in params.items()}
    new_query = urlencode(flat_params)
    final_url = urlunparse(parsed._replace(query=new_query))

    logger.debug("API URL: %s", final_url)

    resp = _request_with_retry('GET', final_url, sess)

    logger.debug("HTTP %s | Response URL: %s", resp.status_code, resp.url)

    if resp.status_code in (401, 403):
        raise SessionExpiredError("Session hết hạn (HTTP {})".format(resp.status_code))

    if resp.status_code != 200:
        raise APIError("API trả về HTTP {}".format(resp.status_code))

    if 'login' in resp.url.lower() and resp.url != final_url:
        raise SessionExpiredError("Session hết hạn (redirect về trang login)")

    data = resp.json()

    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        students = _extract_student_list(data)
        if students is not None:
            return students
        raise APIError("Không tìm thấy danh sách học sinh. Response keys: {}".format(list(data.keys())))
    else:
        raise APIError("Response không đúng format")


def _extract_pagination_info(data):
    """Trích thông tin phân trang từ response dict (nếu có)."""
    if not isinstance(data, dict):
        return None

    total_keys = ('total', 'totalRecords', 'totalCount', 'count', 'recordsTotal')
    total_pages_keys = ('totalPages', 'pages', 'pageCount')

    info = {}
    for key in total_keys:
        if key in data and data[key] is not None:
            try:
                info['total'] = int(data[key])
                break
            except (ValueError, TypeError):
                pass

    for key in total_pages_keys:
        if key in data and data[key] is not None:
            try:
                info['total_pages'] = int(data[key])
                break
            except (ValueError, TypeError):
                pass

    # Tìm trong nested 'page' dict
    if not info and 'page' in data and isinstance(data['page'], dict):
        return _extract_pagination_info(data['page'])

    return info if info else None


def fetch_all_students(api_list_url: str, jsessionid: str,
                       on_log=None, page_limit: int = 5000) -> list:
    """
    Gọi API list để lấy TOÀN BỘ học sinh qua tất cả các trang.
    Tự động xử lý phân trang, deduplicate theo id.

    Args:
        api_list_url: API URL danh sách học sinh.
        jsessionid: JSESSIONID hiện tại.
        on_log: Callback ghi log (optional).
        page_limit: Số bản ghi mỗi trang (mặc định 500).

    Returns: list các dict student record (deduplicated).
    Raises: SessionExpiredError, APIError
    """
    def log(msg):
        logger.info(msg)
        if on_log:
            on_log(msg)

    sess = _make_session(jsessionid)

    parsed = urlparse(api_list_url)
    base_params = parse_qs(parsed.query, keep_blank_values=True)
    base_params['limit'] = [str(page_limit)]

    all_students = []
    seen_ids = set()
    current_page = 1
    total_pages = None
    total_records = None

    while True:
        base_params['page'] = [str(current_page)]
        flat_params = {k: v[0] for k, v in base_params.items()}
        new_query = urlencode(flat_params)
        final_url = urlunparse(parsed._replace(query=new_query))

        log(f"📄 Đang tải trang {current_page}"
            f"{f'/{total_pages}' if total_pages else ''}"
            f" (limit={page_limit})...")

        resp = _request_with_retry('GET', final_url, sess)

        if resp.status_code in (401, 403):
            raise SessionExpiredError("Session hết hạn (HTTP {})".format(resp.status_code))

        if resp.status_code != 200:
            raise APIError("API trả về HTTP {}".format(resp.status_code))

        if 'login' in resp.url.lower() and resp.url != final_url:
            raise SessionExpiredError("Session hết hạn (redirect về trang login)")

        data = resp.json()

        # Trích danh sách học sinh từ response
        if isinstance(data, list):
            page_students = data
        elif isinstance(data, dict):
            page_students = _extract_student_list(data)
            if page_students is None:
                if current_page == 1:
                    raise APIError("Không tìm thấy danh sách học sinh. "
                                   "Response keys: {}".format(list(data.keys())))
                else:
                    break  # Trang sau không có dữ liệu

            # Lấy thông tin phân trang ở trang đầu tiên
            if current_page == 1:
                pag_info = _extract_pagination_info(data)
                if pag_info:
                    total_records = pag_info.get('total')
                    total_pages = pag_info.get('total_pages')

                    # Tính total_pages từ total nếu chưa có
                    if total_pages is None and total_records is not None:
                        total_pages = (total_records + page_limit - 1) // page_limit

                    if total_records is not None:
                        log(f"📊 API báo tổng cộng: {total_records} học sinh"
                            f", {total_pages} trang")
        else:
            if current_page == 1:
                raise APIError("Response không đúng format")
            else:
                break

        if not page_students:
            log(f"📄 Trang {current_page}: 0 học sinh — kết thúc.")
            break

        # Deduplicate theo id
        new_count = 0
        for student in page_students:
            sid = student.get('id')
            if sid is not None and sid in seen_ids:
                continue
            if sid is not None:
                seen_ids.add(sid)
            all_students.append(student)
            new_count += 1

        dup_count = len(page_students) - new_count
        dup_note = f" ({dup_count} trùng bỏ qua)" if dup_count > 0 else ""
        log(f"✅ Trang {current_page}: {len(page_students)} học sinh"
            f", mới: {new_count}{dup_note}")

        # Kiểm tra điều kiện dừng
        if total_pages is not None and current_page >= total_pages:
            break  # Đã lấy hết trang

        if len(page_students) < page_limit:
            # Trang trả về ít hơn limit → đây là trang cuối
            break

        current_page += 1

        # Giới hạn an toàn: không quá 100 trang
        if current_page > 100:
            log("⚠ Đã đạt giới hạn 100 trang, dừng lại.")
            break

    log(f"📋 Tổng cộng: {len(all_students)} học sinh (sau deduplicate)")
    return all_students


def upload_face_image(
    base_url: str,
    jsessionid: str,
    staff_id: int,
    image_path: str,
    face_end_date: str
) -> dict:
    """Upload ảnh khuôn mặt cho 1 học sinh."""
    sess = _make_session(jsessionid)
    upload_url = base_url.rstrip('/') + '/ent/ent/staffface/save'

    filename = os.path.basename(image_path)
    with open(image_path, 'rb') as f:
        files = {'imageFile': (filename, f, 'image/jpeg')}
        form_data = {
            'staffId': str(staff_id),
            'faceEndDate': face_end_date,
        }
        resp = _request_with_retry('POST', upload_url, sess, files=files, data=form_data)

    if resp.status_code in (401, 403):
        raise SessionExpiredError("Session hết hạn khi upload (HTTP {})".format(resp.status_code))

    if 'login' in resp.url.lower():
        raise SessionExpiredError("Session hết hạn (redirect về login khi upload)")

    if resp.status_code != 200:
        raise APIError("Upload thất bại (HTTP {})".format(resp.status_code))

    try:
        return resp.json()
    except ValueError:
        return {'status_code': resp.status_code}


def test_connection(base_url: str, jsessionid: str) -> tuple:
    """Test session còn sống không. Returns (ok: bool, message: str)."""
    try:
        sess = _make_session(jsessionid)
        test_url = base_url.rstrip('/') + '/ent/ent/staff/list?limit=1&page=1&staffType=S'
        resp = sess.get(test_url, timeout=(5, 10), allow_redirects=False)

        if resp.status_code in (401, 403):
            return False, f"Session hết hạn (HTTP {resp.status_code})"

        if resp.status_code in (301, 302):
            location = resp.headers.get('Location', '')
            if 'login' in location.lower():
                return False, "Session hết hạn (redirect về login)"

        if resp.status_code == 200:
            return True, "Kết nối OK"

        return False, f"HTTP {resp.status_code}"
    except requests.ConnectionError:
        return False, "Không thể kết nối đến server"
    except requests.Timeout:
        return False, "Timeout khi kết nối"
    except Exception as e:
        return False, str(e)


class SessionExpiredError(Exception):
    pass


class APIError(Exception):
    pass
