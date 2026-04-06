"""
Tập trung CSS selectors cho web KeyTech.
Khi web thay đổi HTML, chỉ cần sửa file này.
"""

# === Login Page ===

LOGIN_URL_PATH = '/web/login.html'

LOGIN_SELECTORS = {
    'username': ['#username', 'input[placeholder*="đăng nhập"]', 'input[name="username"]'],
    'password': ['#password', 'input[type="password"]', 'input[name="password"]'],
    'captcha':  ['#captcha', 'input[placeholder*="xác minh"]', 'input[name="captcha"]'],
    'submit':   ['#login', 'button.logBut', 'button:has-text("Đăng nhập")'],
}

# Dấu hiệu login thành công (URL chứa 1 trong các pattern này)
LOGIN_SUCCESS_PATTERNS = ['/index', '/home', '/main', '#/']

# Dấu hiệu vẫn ở trang login (login fail)
LOGIN_FAIL_PATTERNS = ['login.html', '/login']

# === Network Interception ===

# Pattern request chứa danh sách học sinh theo lớp
STUDENT_LIST_URL_PATTERN = 'staffType=S'
STUDENT_LIST_URL_CONTAINS = 'deptList'

# Pattern dept tree (thử lấy danh sách lớp)
DEPT_TREE_PATHS = [
    '/ent/ent/dept/treeData',
    '/ent/ent/dept/list',
    '/ent/ent/dept/getDeptTree',
]
