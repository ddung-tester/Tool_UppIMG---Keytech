"""
Module đối chiếu tên file ảnh với danh sách học sinh.
Hỗ trợ exact full-name match và suffix-token match.
"""

from name_utils import normalize_name, tokenize_name, build_suffixes

RULE_EXACT = 'exact_full_name'
RULE_SUFFIX = 'suffix_{n}_unique'
RULE_AMBIGUOUS = 'ambiguous'
RULE_NOT_FOUND = 'not_found'


class MatchResult:
    __slots__ = ('student', 'rule', 'token_count', 'is_weak', 'candidates')

    def __init__(self, student=None, rule=RULE_NOT_FOUND, token_count=0,
                 is_weak=False, candidates=None):
        self.student = student
        self.rule = rule
        self.token_count = token_count
        self.is_weak = is_weak
        self.candidates = candidates or []


class StudentIndex:
    """
    Index học sinh theo full name và tất cả suffix token.
    Cho phép match exact trước, rồi fallback suffix từ dài đến ngắn.
    """

    def __init__(self, students: list):
        self.students = students

        # exact_index: normalized_full_name -> list[student]
        self.exact_index = {}

        # suffix_index: suffix_string -> list[student]
        self.suffix_index = {}

        self._build(students)

    def _build(self, students):
        for s in students:
            name = s.get('staffName', '')
            norm = normalize_name(name)
            tokens = tokenize_name(norm)

            # Exact index
            self.exact_index.setdefault(norm, []).append(s)

            # Suffix index: mỗi suffix từ 1 token đến N-1 token
            # (full name đã có trong exact_index, không cần thêm vào suffix)
            for i in range(1, len(tokens)):
                suffix = ' '.join(tokens[i:])
                self.suffix_index.setdefault(suffix, []).append(s)

    def match(self, file_norm_name: str) -> MatchResult:
        """
        Match file name đã normalize với học sinh.
        Priority: exact > suffix dài > suffix ngắn.
        Chỉ chấp nhận nếu match DUY NHẤT.
        """
        file_tokens = tokenize_name(file_norm_name)
        file_token_count = len(file_tokens)

        if not file_tokens:
            return MatchResult()

        # Priority 1: Exact full-name match
        exact_matches = self.exact_index.get(file_norm_name, [])
        if len(exact_matches) == 1:
            return MatchResult(
                student=exact_matches[0],
                rule=RULE_EXACT,
                token_count=file_token_count,
                is_weak=False,
            )
        if len(exact_matches) > 1:
            return MatchResult(
                rule=RULE_AMBIGUOUS,
                token_count=file_token_count,
                candidates=exact_matches,
            )

        # Priority 2: Suffix match
        # Tìm trong suffix_index với đúng file_norm_name
        suffix_matches = self.suffix_index.get(file_norm_name, [])

        if len(suffix_matches) == 1:
            is_weak = file_token_count == 1
            rule = f'suffix_{file_token_count}_unique'
            return MatchResult(
                student=suffix_matches[0],
                rule=rule,
                token_count=file_token_count,
                is_weak=is_weak,
            )

        if len(suffix_matches) > 1:
            return MatchResult(
                rule=RULE_AMBIGUOUS,
                token_count=file_token_count,
                candidates=suffix_matches,
            )

        # Không tìm thấy
        return MatchResult()


def build_student_index(students: list) -> StudentIndex:
    return StudentIndex(students)


def format_candidate(student: dict) -> str:
    name = student.get('staffName', '')
    sid = student.get('id', '')
    return f"{name} ({sid})"
