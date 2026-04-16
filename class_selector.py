"""
Module quản lý lớp: validation bộ cấu hình, detect class từ folder/URL.
"""

import os
import re
import logging
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


def extract_dept_from_api_url(api_url: str) -> str:
    """Trích deptList từ API URL. VD: deptList=[9063] → '9063'."""
    if not api_url:
        return ''
    parsed = urlparse(api_url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    dept_list = params.get('deptList', [''])[0]
    # Bỏ [] nếu có
    dept_list = dept_list.strip('[]')
    return dept_list


def guess_class_from_folder(folder_path: str) -> str:
    """Đoán tên lớp từ tên folder. VD: 'D:\\Anh HS\\6A1' → '6A1'."""
    if not folder_path:
        return ''
    basename = os.path.basename(folder_path.rstrip('/\\'))
    # Tìm pattern lớp: số + chữ + số (6A1, 8A8, 10A2, ...)
    match = re.search(r'\d+[A-Za-z]\d*', basename)
    if match:
        return match.group(0).upper()
    return basename


def validate_class_config(class_name: str, api_url: str, folder_path: str) -> list:
    """
    Kiểm tra bộ cấu hình lớp có nhất quán không.
    Returns list of warning strings. Empty = OK.
    """
    warnings = []

    if not class_name:
        warnings.append("Chưa nhập tên lớp")

    if not api_url:
        warnings.append("Chưa có API List URL")

    if not folder_path:
        warnings.append("Chưa chọn folder ảnh")
    elif not os.path.isdir(folder_path):
        warnings.append(f"Folder không tồn tại: {folder_path}")

    if not warnings and class_name and folder_path:
        folder_name = os.path.basename(folder_path.rstrip('/\\'))
        class_upper = class_name.upper()
        folder_upper = folder_name.upper()

        if class_upper not in folder_upper:
            warnings.append(
                f"Lớp đang chọn là '{class_name}' nhưng folder là '{folder_name}'"
            )

    if api_url and 'deptList' not in api_url:
        warnings.append("API URL không chứa deptList — có thể không đúng lớp")

    return warnings


def count_images_in_folder(folder_path: str) -> int:
    """Đếm file ảnh trong folder."""
    if not folder_path or not os.path.isdir(folder_path):
        return 0
    supported = ('.jpg', '.jpeg', '.png')
    return sum(1 for f in os.listdir(folder_path) if f.lower().endswith(supported))
