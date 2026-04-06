"""
Test cases cho matching logic.
Chạy: python test_matcher.py
"""

from name_utils import normalize_name, tokenize_name, build_suffixes
from matcher import build_student_index, RULE_EXACT, RULE_AMBIGUOUS, RULE_NOT_FOUND


def make_student(name, sid):
    return {'staffName': name, 'id': sid, 'staffCode': str(sid), 'deptName': 'Test'}


def test_normalize():
    print("=== Test normalize ===")

    cases = [
        ('Nguyễn Văn An.jpg', 'nguyen van an'),
        ('Nguyễn_Văn_An.jpg', 'nguyen van an'),
        ('van-an (1).jpeg', 'van an'),
        ('AN.PNG', 'an'),
        ('Trần Đức Huy.jpg', 'tran duc huy'),
        ('nguyen van an (1).jpg', 'nguyen van an'),
        ('  Le  Thi   Hoa  .jpg', 'le thi hoa'),
        ('abc-copy.jpg', 'abc'),
        ('test_2.jpg', 'test'),
    ]

    for raw, expected in cases:
        result = normalize_name(raw)
        status = "✅" if result == expected else "❌"
        print(f"  {status} normalize('{raw}') = '{result}' (expected: '{expected}')")

    print()


def test_tokenize():
    print("=== Test tokenize ===")

    cases = [
        ('nguyen van an', ['nguyen', 'van', 'an']),
        ('an', ['an']),
        ('', []),
    ]

    for name, expected in cases:
        result = tokenize_name(name)
        status = "✅" if result == expected else "❌"
        print(f"  {status} tokenize('{name}') = {result}")

    print()


def test_suffixes():
    print("=== Test build_suffixes ===")

    tokens = ['nguyen', 'van', 'an']
    result = build_suffixes(tokens)
    expected = {'an': 1, 'van an': 2, 'nguyen van an': 3}
    status = "✅" if result == expected else "❌"
    print(f"  {status} build_suffixes({tokens}) = {result}")
    print()


def test_case_1_exact():
    print("=== Case 1: Exact full-name match ===")
    students = [make_student('Nguyễn Văn An', 1)]
    index = build_student_index(students)

    m = index.match(normalize_name('nguyen van an.jpg'))
    status = "✅" if m.rule == RULE_EXACT and m.student['id'] == 1 else "❌"
    print(f"  {status} 'nguyen van an.jpg' -> rule={m.rule}, id={m.student['id'] if m.student else None}")
    print()


def test_case_2_suffix_2_unique():
    print("=== Case 2: Suffix 2 token, unique ===")
    students = [
        make_student('Nguyễn Văn An', 1),
        make_student('Trần Minh Đức', 2),
    ]
    index = build_student_index(students)

    m = index.match(normalize_name('van an.jpg'))
    ok = m.rule == 'suffix_2_unique' and m.student['id'] == 1 and not m.is_weak
    status = "✅" if ok else "❌"
    print(f"  {status} 'van an.jpg' -> rule={m.rule}, id={m.student['id'] if m.student else None}, weak={m.is_weak}")
    print()


def test_case_3_suffix_1_unique():
    print("=== Case 3: Suffix 1 token, unique ===")
    students = [
        make_student('Nguyễn Văn An', 1),
        make_student('Trần Minh Đức', 2),
    ]
    index = build_student_index(students)

    m = index.match(normalize_name('an.jpg'))
    ok = m.rule == 'suffix_1_unique' and m.student['id'] == 1 and m.is_weak
    status = "✅" if ok else "❌"
    print(f"  {status} 'an.jpg' -> rule={m.rule}, id={m.student['id'] if m.student else None}, weak={m.is_weak}")
    print()


def test_case_4_suffix_1_ambiguous():
    print("=== Case 4: Suffix 1 token, ambiguous ===")
    students = [
        make_student('Nguyễn Văn An', 1),
        make_student('Trần Hoàng An', 2),
    ]
    index = build_student_index(students)

    m = index.match(normalize_name('an.jpg'))
    ok = m.rule == RULE_AMBIGUOUS and len(m.candidates) == 2
    status = "✅" if ok else "❌"
    print(f"  {status} 'an.jpg' -> rule={m.rule}, candidates={len(m.candidates)}")
    print()


def test_case_5_not_found():
    print("=== Case 5: Not found ===")
    students = [make_student('Nguyễn Văn An', 1)]
    index = build_student_index(students)

    m = index.match(normalize_name('quang.jpg'))
    status = "✅" if m.rule == RULE_NOT_FOUND else "❌"
    print(f"  {status} 'quang.jpg' -> rule={m.rule}")
    print()


def test_case_6_suffix_with_junk():
    print("=== Case 6: Suffix with junk suffix (1) ===")
    students = [make_student('Nguyễn Văn An', 1)]
    index = build_student_index(students)

    m = index.match(normalize_name('van an (1).jpg'))
    ok = m.rule == 'suffix_2_unique' and m.student['id'] == 1
    status = "✅" if ok else "❌"
    print(f"  {status} 'van an (1).jpg' -> rule={m.rule}, id={m.student['id'] if m.student else None}")
    print()


def test_case_7_suffix_2_ambiguous():
    print("=== Case 7: Suffix 2 tokens, ambiguous (Nguyễn Văn An vs Trần Văn An) ===")
    students = [
        make_student('Nguyễn Văn An', 1),
        make_student('Trần Văn An', 2),
    ]
    index = build_student_index(students)

    m = index.match(normalize_name('van an.jpg'))
    ok = m.rule == RULE_AMBIGUOUS and len(m.candidates) == 2
    status = "✅" if ok else "❌"
    print(f"  {status} 'van an.jpg' -> rule={m.rule}, candidates={len(m.candidates)}")
    print()


def test_case_8_exact_beats_suffix():
    print("=== Case 8: Exact match wins over suffix ===")
    students = [
        make_student('Văn An', 1),
        make_student('Nguyễn Văn An', 2),
    ]
    index = build_student_index(students)

    m = index.match(normalize_name('van an.jpg'))
    ok = m.rule == RULE_EXACT and m.student['id'] == 1
    status = "✅" if ok else "❌"
    print(f"  {status} 'van an.jpg' -> rule={m.rule}, id={m.student['id'] if m.student else None}")
    print(f"         (Should match 'Van An' exactly, not suffix of 'Nguyen Van An')")
    print()


def test_case_9_underscore_dash():
    print("=== Case 9: File with underscores and dashes ===")
    students = [make_student('Nguyễn Văn An', 1)]
    index = build_student_index(students)

    m = index.match(normalize_name('Nguyen_Van_An.jpg'))
    ok = m.rule == RULE_EXACT and m.student['id'] == 1
    status = "✅" if ok else "❌"
    print(f"  {status} 'Nguyen_Van_An.jpg' -> rule={m.rule}")

    m2 = index.match(normalize_name('Van-An.jpg'))
    ok2 = m2.rule == 'suffix_2_unique' and m2.student['id'] == 1
    status2 = "✅" if ok2 else "❌"
    print(f"  {status2} 'Van-An.jpg' -> rule={m2.rule}")
    print()


if __name__ == '__main__':
    test_normalize()
    test_tokenize()
    test_suffixes()
    test_case_1_exact()
    test_case_2_suffix_2_unique()
    test_case_3_suffix_1_unique()
    test_case_4_suffix_1_ambiguous()
    test_case_5_not_found()
    test_case_6_suffix_with_junk()
    test_case_7_suffix_2_ambiguous()
    test_case_8_exact_beats_suffix()
    test_case_9_underscore_dash()

    print("=" * 40)
    print("All tests complete.")
