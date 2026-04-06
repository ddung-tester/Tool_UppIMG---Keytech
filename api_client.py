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
