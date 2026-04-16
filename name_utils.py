"""
Tiện ích normalize tên tiếng Việt để đối chiếu file ảnh <-> tên học sinh.
"""

import re
import unicodedata


_VIET_CHARS = {
    'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
    'ă': 'a', 'ắ': 'a', 'ằ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
    'â': 'a', 'ấ': 'a', 'ầ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
    'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
    'ê': 'e', 'ế': 'e', 'ề': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
    'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
    'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
    'ô': 'o', 'ố': 'o', 'ồ': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
    'ơ': 'o', 'ớ': 'o', 'ờ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
    'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
    'ư': 'u', 'ứ': 'u', 'ừ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
    'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
    'đ': 'd',
    'À': 'A', 'Á': 'A', 'Ả': 'A', 'Ã': 'A', 'Ạ': 'A',
    'Ă': 'A', 'Ắ': 'A', 'Ằ': 'A', 'Ẳ': 'A', 'Ẵ': 'A', 'Ặ': 'A',
    'Â': 'A', 'Ấ': 'A', 'Ầ': 'A', 'Ẩ': 'A', 'Ẫ': 'A', 'Ậ': 'A',
    'È': 'E', 'É': 'E', 'Ẻ': 'E', 'Ẽ': 'E', 'Ẹ': 'E',
    'Ê': 'E', 'Ế': 'E', 'Ề': 'E', 'Ể': 'E', 'Ễ': 'E', 'Ệ': 'E',
    'Ì': 'I', 'Í': 'I', 'Ỉ': 'I', 'Ĩ': 'I', 'Ị': 'I',
    'Ò': 'O', 'Ó': 'O', 'Ỏ': 'O', 'Õ': 'O', 'Ọ': 'O',
    'Ô': 'O', 'Ố': 'O', 'Ồ': 'O', 'Ổ': 'O', 'Ỗ': 'O', 'Ộ': 'O',
    'Ơ': 'O', 'Ớ': 'O', 'Ờ': 'O', 'Ở': 'O', 'Ỡ': 'O', 'Ợ': 'O',
    'Ù': 'U', 'Ú': 'U', 'Ủ': 'U', 'Ũ': 'U', 'Ụ': 'U',
    'Ư': 'U', 'Ứ': 'U', 'Ừ': 'U', 'Ử': 'U', 'Ữ': 'U', 'Ự': 'U',
    'Ỳ': 'Y', 'Ý': 'Y', 'Ỷ': 'Y', 'Ỹ': 'Y', 'Ỵ': 'Y',
    'Đ': 'D',
}
_VIET_MAP = str.maketrans(_VIET_CHARS)

_SUFFIX_PATTERN = re.compile(
    r'(?<=\D)[\s_-]*(?:\(\d+\)|\d+|-?\s*copy(?:\s*\d+)?)\s*$',
    re.IGNORECASE
)


def normalize_name(raw_name: str) -> str:
    """
    Normalize tên tiếng Việt:
    - Bỏ extension
    - Lowercase, NFC
    - Bỏ dấu, đ -> d
    - Thay _ - . thành space
    - Bỏ hậu tố trùng file: (1), _1, -copy
    - Gộp khoảng trắng, strip
    """
    if not raw_name:
        return ""

    name = re.sub(r'\.(jpg|jpeg|png|bmp|webp)$', '', raw_name, flags=re.IGNORECASE)
    name = unicodedata.normalize('NFC', name)
    name = name.lower()
    name = name.translate(_VIET_MAP)

    decomposed = unicodedata.normalize('NFD', name)
    name = ''.join(c for c in decomposed if unicodedata.category(c) != 'Mn')

    # Thay _ - . thành space
    name = re.sub(r'[_\-\.]+', ' ', name)

    name = _SUFFIX_PATTERN.sub('', name)
    name = re.sub(r'\s+', ' ', name).strip()

    return name


def tokenize_name(normalized_name: str) -> list:
    """Tách tên đã normalize thành list token."""
    if not normalized_name:
        return []
    return normalized_name.split()


def build_suffixes(tokens: list) -> dict:
    """
    Tạo dict suffix -> số token.
    VD: tokens = ["nguyen", "van", "an"]
    -> {
        "an": 1,
        "van an": 2,
        "nguyen van an": 3,
    }
    """
    suffixes = {}
    for i in range(len(tokens)):
        suffix = ' '.join(tokens[i:])
        token_count = len(tokens) - i
        suffixes[suffix] = token_count
    return suffixes
