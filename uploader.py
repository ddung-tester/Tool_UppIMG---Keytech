"""
Module xử lý batch upload 2 pha:
  Phase 1: Upload an toàn (exact + suffix_2+). Collect pending (weak + ambiguous).
  Phase 2: Upload pending items sau khi user duyệt.
"""

import os
import logging
from collections import Counter
from typing import Callable, Optional

from name_utils import normalize_name, tokenize_name
from matcher import (
    build_student_index,
    format_candidate,
    MatchResult,
    RULE_EXACT,
    RULE_AMBIGUOUS,
    RULE_NOT_FOUND,
)
from api_client import (
    fetch_student_list,
    upload_face_image,
    SessionExpiredError,
    APIError,
)

logger = logging.getLogger(__name__)

STATUS_SUCCESS = 'success'
STATUS_SKIPPED = 'skipped_existing'
STATUS_NOT_FOUND = 'not_found'
STATUS_AMBIGUOUS = 'ambiguous_partial_match'
STATUS_PENDING_WEAK = 'pending_weak'
STATUS_PENDING_AMBIGUOUS = 'pending_ambiguous'
STATUS_UPLOAD_FAILED = 'upload_failed'
STATUS_API_LIST_FAILED = 'api_list_failed'
STATUS_SESSION_EXPIRED = 'session_expired'
STATUS_SKIPPED_BY_USER = 'skipped_by_user'

SAFE_RULES = {RULE_EXACT, 'suffix_2_unique', 'suffix_3_unique', 'suffix_4_unique', 'suffix_5_unique'}


def scan_image_folder(folder_path: str) -> list:
    supported_ext = ('.jpg', '.jpeg', '.png')
    files = [f for f in os.listdir(folder_path) if f.lower().endswith(supported_ext)]
    files.sort()
    return files


def has_existing_photo(student: dict) -> bool:
    photo = student.get('staffPhoto')
    face_id = student.get('staffFaceId')
    if photo and str(photo).strip():
        return True
    if face_id and str(face_id).strip() and str(face_id).strip() != '0':
        return True
    return False


def is_safe_rule(rule: str) -> bool:
    """Rule an toàn = exact hoặc suffix >= 2 token."""
    if rule in SAFE_RULES:
        return True
    if rule.startswith('suffix_') and rule.endswith('_unique'):
        try:
            n = int(rule.split('_')[1])
            return n >= 2
        except (ValueError, IndexError):
            pass
    return False


def process_phase1(
    api_list_url: str,
    base_url: str,
    jsessionid: str,
    folder_path: str,
    face_end_date: str,
    dry_run: bool = True,
    skip_existing: bool = True,
    on_progress: Optional[Callable] = None,
    on_log: Optional[Callable] = None,
    should_stop: Optional[Callable] = None,
) -> dict:
    """
    Phase 1: Scan, match, upload an toàn.
    Returns dict với keys: results, pending, total_students, total_files
    """
    results = []
    pending = []

    def log(msg):
        logger.info(msg)
        if on_log:
            on_log(msg)

    def check_stop():
        if should_stop and should_stop():
            log("⛔ Đã dừng theo yêu cầu.")
            return True
        return False

    # === Lấy danh sách học sinh ===
    log("📋 Đang tải danh sách học sinh từ API...")

    try:
        students = fetch_student_list(api_list_url, jsessionid)
    except SessionExpiredError as e:
        log(f"❌ Lỗi: Phiên đăng nhập hết hạn — {e}")
        results.append(_make_result('', '', None, STATUS_SESSION_EXPIRED, str(e)))
        return {'results': results, 'pending': [], 'total_students': 0, 'total_files': 0}
    except Exception as e:
        log(f"❌ Lỗi: Không gọi được API — {e}")
        results.append(_make_result('', '', None, STATUS_API_LIST_FAILED, str(e)))
        return {'results': results, 'pending': [], 'total_students': 0, 'total_files': 0}

    if not students:
        log("❌ Lỗi: Danh sách học sinh trả về rỗng.")
        return {'results': results, 'pending': [], 'total_students': 0, 'total_files': 0}

    dept = students[0].get('deptName', '').strip().strip('/')
    total_students = len(students)
    has_photo_count = sum(1 for s in students if has_existing_photo(s))

    log(f"✅ Danh sách lớp {dept}: {total_students} học sinh")

    # === Đọc file ảnh ===
    image_files = scan_image_folder(folder_path)
    total_files = len(image_files)
    log(f"📁 Thư mục ảnh: {total_files} file")

    if not image_files:
        log("❌ Lỗi: Không tìm thấy file ảnh nào trong thư mục.")
        return {'results': results, 'pending': [], 'total_students': total_students, 'total_files': 0}

    # === Build index ===
    student_index = build_student_index(students)

    if has_photo_count > 0:
        log(f"📸 Đã có ảnh sẵn: {has_photo_count}/{total_students} học sinh")

    log(f"🔎 Bắt đầu đối chiếu {total_files} ảnh ↔ {total_students} học sinh...")
    log("─" * 55)

    if check_stop():
        return {'results': results, 'pending': pending, 'total_students': total_students, 'total_files': total_files}

    # === Phase 1: Đối chiếu ===
    for idx, filename in enumerate(image_files, 1):
        if check_stop():
            break

        if on_progress:
            on_progress(idx, total_files)

        file_path = os.path.join(folder_path, filename)
        norm_name = normalize_name(filename)
        file_tokens = tokenize_name(norm_name)
        match = student_index.match(norm_name)

        # Không tìm thấy
        if match.rule == RULE_NOT_FOUND:
            log(f"❌ Không khớp  → {filename}")
            results.append(_make_result(filename, norm_name, None, STATUS_NOT_FOUND,
                                        "Không tìm thấy học sinh phù hợp",
                                        match_rule='not_found', file_tokens=file_tokens))
            continue

        # Mơ hồ → pending
        if match.rule == RULE_AMBIGUOUS:
            cands = '; '.join(format_candidate(c) for c in match.candidates)
            n = len(match.candidates)
            log(f"⏳ Chờ duyệt (mơ hồ) → {filename}  [{n} ứng viên]")
            pending.append({
                'file_name': filename,
                'file_path': file_path,
                'norm_name': norm_name,
                'status': STATUS_PENDING_AMBIGUOUS,
                'match_rule': 'ambiguous',
                'proposed_match': None,
                'candidate_matches': match.candidates,
                'selected_student': None,
                'is_selected': False,
            })
            continue

        # Match thành công
        student = match.student
        staff_name = student.get('staffName', '')
        staff_id = student.get('id')
        rule = match.rule

        # Skip đã có ảnh
        if skip_existing and has_existing_photo(student):
            log(f"⏭ Bỏ qua (đã có ảnh) → {filename}  →  {staff_name}")
            results.append(_make_result(filename, norm_name, student, STATUS_SKIPPED, "Đã có ảnh",
                                        match_rule=rule, file_tokens=file_tokens))
            continue

        # Match yếu (suffix_1) → pending
        if match.is_weak:
            log(f"⏳ Chờ duyệt (khớp yếu) → {filename}  →  {staff_name}")
            pending.append({
                'file_name': filename,
                'file_path': file_path,
                'norm_name': norm_name,
                'status': STATUS_PENDING_WEAK,
                'match_rule': rule,
                'proposed_match': student,
                'candidate_matches': [],
                'selected_student': None,
                'is_selected': False,
            })
            continue

        # Match an toàn → upload hoặc dry run
        if dry_run:
            log(f"🔍 Khớp  (thử nghiệm) → {filename}  →  {staff_name}")
            results.append(_make_result(filename, norm_name, student, STATUS_SUCCESS,
                                        f"Thử nghiệm | Rule: {rule}", match_rule=rule, file_tokens=file_tokens))
            continue

        # Upload thật
        try:
            upload_face_image(base_url, jsessionid, staff_id, file_path, face_end_date)
            log(f"✅ Upload OK → {filename}  →  {staff_name}")
            results.append(_make_result(filename, norm_name, student, STATUS_SUCCESS,
                                        f"Upload OK | Rule: {rule}", match_rule=rule, file_tokens=file_tokens))
        except SessionExpiredError as e:
            log(f"❌ Lỗi: Phiên hết hạn — {filename}")
            results.append(_make_result(filename, norm_name, student, STATUS_SESSION_EXPIRED, str(e),
                                        match_rule=rule, file_tokens=file_tokens))
            log("⛔ Dừng xử lý — phiên đăng nhập đã hết hạn.")
            break
        except Exception as e:
            log(f"💥 Upload thất bại → {filename}  →  {staff_name} — {e}")
            results.append(_make_result(filename, norm_name, student, STATUS_UPLOAD_FAILED, str(e),
                                        match_rule=rule, file_tokens=file_tokens))

    # === Tổng kết Phase 1 ===
    log("─" * 55)
    _log_phase1_summary(results, pending, total_students, total_files, log)

    return {
        'results': results,
        'pending': pending,
        'total_students': total_students,
        'total_files': total_files,
    }


def process_phase2(
    pending_items: list,
    base_url: str,
    jsessionid: str,
    face_end_date: str,
    dry_run: bool = True,
    on_log: Optional[Callable] = None,
    should_stop: Optional[Callable] = None,
) -> list:
    """
    Phase 2: Upload các pending items đã được user duyệt.
    Chỉ xử lý items có is_selected=True và selected_student != None.
    """
    results = []

    def log(msg):
        logger.info(msg)
        if on_log:
            on_log(msg)

    log("")
    log("━" * 55)
    log("🔄 GIAI ĐOẠN 2 — Upload các mục đã xác nhận")
    log("━" * 55)

    selected = [p for p in pending_items if p.get('is_selected') and p.get('selected_student')]
    skipped = [p for p in pending_items if not p.get('is_selected') or not p.get('selected_student')]

    if not selected:
        log("ℹ Không có mục nào được chọn để upload.")
        return results

    log(f"📋 Được duyệt: {len(selected)} mục  |  Bỏ qua: {len(skipped)} mục")
    log("─" * 55)

    for item in selected:
        if should_stop and should_stop():
            log("⛔ Đã dừng theo yêu cầu.")
            break

        filename = item['file_name']
        file_path = item['file_path']
        student = item['selected_student']
        staff_name = student.get('staffName', '')
        staff_id = student.get('id')
        rule = item['match_rule']
        origin = "khớp yếu" if item['status'] == STATUS_PENDING_WEAK else "đã xác nhận"

        if dry_run:
            log(f"🔍 Khớp  (thử nghiệm, {origin}) → {filename}  →  {staff_name}")
            results.append(_make_result(filename, item['norm_name'], student, STATUS_SUCCESS,
                                        f"Thử nghiệm | Giai đoạn 2 ({origin})", match_rule=rule))
            continue

        try:
            upload_face_image(base_url, jsessionid, staff_id, file_path, face_end_date)
            log(f"✅ Upload OK ({origin}) → {filename}  →  {staff_name}")
            results.append(_make_result(filename, item['norm_name'], student, STATUS_SUCCESS,
                                        f"Upload OK | Phase 2 ({origin})", match_rule=rule))
        except SessionExpiredError as e:
            log(f"❌ Lỗi: Phiên hết hạn — {filename}")
            results.append(_make_result(filename, item['norm_name'], student, STATUS_SESSION_EXPIRED, str(e),
                                        match_rule=rule))
            log("⛔ Dừng xử lý — phiên đăng nhập đã hết hạn.")
            break
        except Exception as e:
            log(f"💥 Upload thất bại → {filename}  →  {staff_name} — {e}")
            results.append(_make_result(filename, item['norm_name'], student, STATUS_UPLOAD_FAILED, str(e),
                                        match_rule=rule))

    # Ghi result cho items bị bỏ qua
    for item in skipped:
        results.append(_make_result(item['file_name'], item['norm_name'], None, STATUS_SKIPPED_BY_USER,
                                    "Người dùng bỏ qua", match_rule=item['match_rule']))

    log("─" * 55)
    _log_phase2_summary(results, log)

    return results


def _make_result(filename, norm_name, student, status, message,
                 match_rule='', file_tokens=None):
    return {
        'file_name': filename,
        'normalized_file_name': norm_name,
        'matched_staff_name': student.get('staffName', '') if student else '',
        'staff_id': student.get('id', '') if student else '',
        'staff_code': student.get('staffCode', '') if student else '',
        'dept_name': student.get('deptName', '') if student else '',
        'status': status,
        'message': message,
        'match_rule': match_rule,
        'file_tokens': ' '.join(file_tokens) if file_tokens else '',
    }


def _log_phase1_summary(results, pending, total_students, total_files, log_fn):
    counter = Counter(r['status'] for r in results)
    pending_weak = sum(1 for p in pending if p['status'] == STATUS_PENDING_WEAK)
    pending_ambig = sum(1 for p in pending if p['status'] == STATUS_PENDING_AMBIGUOUS)

    log_fn("📊 KẾT QUẢ GIAI ĐOẠN 1")
    log_fn(f"   👤 Học sinh từ API    : {total_students}")
    log_fn(f"   🖼  File ảnh tìm thấy : {total_files}")
    log_fn(f"   ✅ Upload tự động     : {counter.get(STATUS_SUCCESS, 0)}")
    log_fn(f"   ⏭  Bỏ qua (có ảnh)   : {counter.get(STATUS_SKIPPED, 0)}")
    log_fn(f"   ⏳ Chờ duyệt (yếu)   : {pending_weak}")
    log_fn(f"   ⏳ Chờ duyệt (mơ hồ) : {pending_ambig}")
    log_fn(f"   ❌ Không khớp         : {counter.get(STATUS_NOT_FOUND, 0)}")
    log_fn(f"   💥 Upload thất bại    : {counter.get(STATUS_UPLOAD_FAILED, 0)}")
    if counter.get(STATUS_SESSION_EXPIRED, 0):
        log_fn(f"   🔒 Phiên hết hạn      : {counter.get(STATUS_SESSION_EXPIRED, 0)}")

    if pending_weak + pending_ambig > 0:
        log_fn("")
        log_fn(f"⏳ Có {pending_weak + pending_ambig} mục chờ xác nhận thủ công — đang mở cửa sổ duyệt...")


def _log_phase2_summary(results, log_fn):
    counter = Counter(r['status'] for r in results)

    log_fn("📊 KẾT QUẢ GIAI ĐOẠN 2")
    log_fn(f"   ✅ Upload sau duyệt   : {counter.get(STATUS_SUCCESS, 0)}")
    log_fn(f"   ⏭  Người dùng bỏ qua : {counter.get(STATUS_SKIPPED_BY_USER, 0)}")
    log_fn(f"   💥 Upload thất bại    : {counter.get(STATUS_UPLOAD_FAILED, 0)}")
    if counter.get(STATUS_SESSION_EXPIRED, 0):
        log_fn(f"   🔒 Phiên hết hạn      : {counter.get(STATUS_SESSION_EXPIRED, 0)}")
