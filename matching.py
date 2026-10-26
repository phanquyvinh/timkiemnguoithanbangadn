"""
Logic đối chiếu ADN + địa lý – phiên bản thông minh nâng cấp v4.0.
"""
import re
from typing import Dict, List, Optional, Any, Tuple


def normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    replacements = {
        r"[àáạảãâầấậẩẫăằắặẳẵ]": "a",
        r"[èéẹẻẽêềếệểễ]": "e",
        r"[ìíịỉĩ]": "i",
        r"[òóọỏõôồốộổỗơờớợởỡ]": "o",
        r"[ùúụủũưừứựửữ]": "u",
        r"[ỳýỵỷỹ]": "y",
        r"đ": "d",
    }
    for pattern, repl in replacements.items():
        text = re.sub(pattern, repl, text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def location_similarity(a: Optional[str], b: Optional[str]) -> float:
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return 0.0
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return 0.0
    # Loại bỏ các từ khóa địa lý chung để tránh khớp ảo (tỉnh, huyện, xã, phố...)
    stop_words = {"tinh", "thanh", "pho", "quan", "huyen", "thi", "xa", "phuong", "duong", "pho", "thon", "xom"}
    ta = ta - stop_words
    tb = tb - stop_words
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    union = ta | tb
    return len(inter) / len(union) if union else 0.0


def text_keyword_match(text_a: Optional[str], text_b: Optional[str]) -> float:
    """Kiểm tra độ tương đồng từ khóa giữa các đoạn văn bản dài (hoàn cảnh, đặc điểm)."""
    na, nb = normalize_text(text_a), normalize_text(text_b)
    if not na or not nb or len(na) < 4 or len(nb) < 4:
        return 0.0
    words_a = [w for w in na.split() if len(w) > 2]
    words_b = [w for w in nb.split() if len(w) > 2]
    if not words_a or not words_b:
        return 0.0
    inter = set(words_a) & set(words_b)
    return len(inter) / min(len(words_a), len(words_b))


def kiem_tra_truc_he(dna_a: Dict, dna_b: Dict) -> Tuple[bool, int, int]:
    """
    Parent-child.
    Returns: (passed, số_locus_khớp, số_locus_sai)
    Cho phép tối đa 1 locus không có allele chung (mutation).
    """
    khop = 0
    sai = 0
    for locus, alleles in dna_a.items():
        if locus not in dna_b:
            continue
        if set(alleles) & set(dna_b[locus]):
            khop += 1
        else:
            sai += 1
            if sai > 1:
                return False, khop, sai
    return True, khop, sai


def kiem_tra_anh_em(dna_a: Dict, dna_b: Dict) -> Tuple[bool, float, int]:
    """
    Full sibling.
    Returns: (passed, tỷ_lệ, số_locus_chung)
    Ngưỡng ≥ 0.55
    """
    chung = 0
    tong = 0
    for locus, alleles in dna_a.items():
        if locus not in dna_b:
            continue
        tong += 1
        if set(alleles) & set(dna_b[locus]):
            chung += 1
    ty_le = chung / tong if tong else 0.0
    return ty_le >= 0.55, ty_le, chung


def tinh_diem_tong_hop(
    user_dna: Dict,
    target_dna: Dict,
    user_loai: str,
    target_loai: str,
    user_vi_tri: Optional[str],
    target_vi_tri: Optional[str],
    user_dia_chi_truoc: Optional[str],
    target_dia_chi_truoc: Optional[str],
    user_dia_chi_hien: str,
    target_dia_chi_hien: str,
    user_nam: Optional[str] = None,
    target_nam: Optional[str] = None,
    # === THAM SỐ MỚI THÊM VÀO ĐỂ TỐI ƯU ĐỐI CHIẾU ===
    user_name_input: Optional[str] = None,          # Tên của người đăng hồ sơ A
    target_name_input: Optional[str] = None,        # Tên của người đăng hồ sơ B
    user_target_name: Optional[str] = None,         # Tên người cần tìm trong hồ sơ A
    target_target_name: Optional[str] = None,       # Tên người cần tìm trong hồ sơ B
    user_hoan_canh: Optional[str] = None,
    target_hoan_canh: Optional[str] = None,
    user_dac_diem: Optional[str] = None,
    target_dac_diem: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Chấm điểm đa tiêu chí nâng cao.
    ADN phải vượt qua kiểm tra sinh học → mới kích hoạt đối chiếu các trường metadata để chấm điểm cộng.
    """
    score = 0.0
    reasons: List[str] = []
    loai_quan_he = None

    # ----- 1. ĐỐI CHIẾU ADN (BẮT BUỘC KHỚP SINH HỌC) -----
    if (user_loai == "TIM_CON" and target_loai == "TIM_CHA_ME") or (
        user_loai == "TIM_CHA_ME" and target_loai == "TIM_CON"
    ):
        passed, khop, sai = kiem_tra_truc_he(user_dna, target_dna)
        if not passed:
            return None
        score += 60 + khop * 2.5
        loai_quan_he = "Cha/Mẹ – Con trực hệ"
        reasons.append(f"ADN khớp {khop}/12 locus (sai lệch mutation: {sai})")

    elif user_loai == "TIM_ANH_CH_EM" and target_loai == "TIM_ANH_CH_EM":
        passed, ty_le, chung = kiem_tra_anh_em(user_dna, target_dna)
        if not passed:
            return None
        score += 45 + ty_le * 32
        loai_quan_he = "Anh/Chị/Em ruột tiềm năng"
        reasons.append(f"ADN chia sẻ {ty_le*100:.0f}% locus ({chung} locus chung)")

    else:
        return None

    # ----- 2. ĐỐI CHIẾU THÔNG TIN ĐỊA LÝ -----
    sim_that_lac = location_similarity(user_vi_tri, target_vi_tri)
    if sim_that_lac >= 0.35:
        score += sim_that_lac * 15
        reasons.append(f"Vị trí thất lạc trùng khớp {sim_that_lac*100:.0f}%")

    sim_truoc = location_similarity(user_dia_chi_truoc, target_dia_chi_truoc)
    if sim_truoc >= 0.25:
        score += sim_truoc * 10
        reasons.append(f"Nơi sinh sống trước đây trùng khớp {sim_truoc*100:.0f}%")

    sim_hien = location_similarity(user_dia_chi_hien, target_dia_chi_hien)
    if sim_hien >= 0.3:
        score += sim_hien * 4
        reasons.append(f"Địa chỉ hiện tại gần vùng khảo sát {sim_hien*100:.0f}%")

    # ----- 3. ĐỐI CHIẾU THỜI GIAN/NĂM THẤT LẠC -----
    if user_nam and target_nam:
        try:
            y1 = int(re.search(r"\d{4}", user_nam).group())
            y2 = int(re.search(r"\d{4}", target_nam).group())
            diff = abs(y1 - y2)
            if diff <= 2:
                score += 6
                reasons.append(f"Thời điểm mất liên lạc trùng khớp hoàn hảo (cách {diff} năm)")
            elif diff <= 5:
                score += 3
                reasons.append(f"Thời điểm mất liên lạc có biên độ gần nhau (cách {diff} năm)")
        except Exception:
            pass

    # ----- 4. ĐỐI CHIẾU TÊN CHÉO (HỌ TÊN NGƯỜI ĐĂNG <=> NGƯỜI CẦN TÌM) -----
    # Trường hợp lý tưởng: Tên người đăng hồ sơ này chính là tên người cần tìm ở hồ sơ kia
    if user_name_input and target_target_name:
        n_user = normalize_text(user_name_input)
        n_target_find = normalize_text(target_target_name)
        if n_user in n_target_find or n_target_find in n_user:
            score += 10
            reasons.append("Họ tên người đăng trùng khớp với họ tên người đang được tìm kiếm")

    if target_name_input and user_target_name:
        n_target = normalize_text(target_name_input)
        n_user_find = normalize_text(user_target_name)
        if n_target in n_user_find or n_user_find in n_target:
            score += 10
            if "Họ tên người đăng trùng khớp với họ tên người đang được tìm kiếm" not in reasons:
                reasons.append("Họ tên người đăng trùng khớp với họ tên người đang được tìm kiếm")

    # ----- 5. ĐỐI CHIẾU HOÀN CẢNH & ĐẶC ĐIỂM NHẬN DẠNG -----
    sim_hoan_canh = text_keyword_match(user_hoan_canh, target_hoan_canh)
    if sim_hoan_canh >= 0.25:
        score += sim_hoan_canh * 8
        reasons.append(f"Từ khóa hoàn cảnh thất lạc có sự tương đồng cao")

    sim_dac_diem = text_keyword_match(user_dac_diem, target_dac_diem)
    if sim_dac_diem >= 0.25:
        score += sim_dac_diem * 6
        reasons.append(f"Đặc điểm nhận dạng cơ thể trùng khớp từ khóa")

    return {
        "score": round(score, 1),
        "loai_quan_he": loai_quan_he,
        "reasons": reasons,
    }
