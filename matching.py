"""
Logic đối chiếu ADN + địa lý – phiên bản thông minh hơn.
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
    inter = ta & tb
    union = ta | tb
    return len(inter) / len(union) if union else 0.0


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
) -> Optional[Dict[str, Any]]:
    """
    Chấm điểm đa tiêu chí.
    DNA phải pass → mới tính điểm địa lý.
    """
    score = 0.0
    reasons: List[str] = []
    loai_quan_he = None

    # ----- DNA -----
    if (user_loai == "TIM_CON" and target_loai == "TIM_CHA_ME") or (
        user_loai == "TIM_CHA_ME" and target_loai == "TIM_CON"
    ):
        passed, khop, sai = kiem_tra_truc_he(user_dna, target_dna)
        if not passed:
            return None
        score += 65 + khop * 2.5
        loai_quan_he = "Cha/Mẹ – Con trực hệ"
        reasons.append(f"ADN khớp {khop}/12 locus (sai lệch mutation: {sai})")

    elif user_loai == "TIM_ANH_CH_EM" and target_loai == "TIM_ANH_CH_EM":
        passed, ty_le, chung = kiem_tra_anh_em(user_dna, target_dna)
        if not passed:
            return None
        score += 48 + ty_le * 32
        loai_quan_he = "Anh/Chị/Em ruột tiềm năng"
        reasons.append(f"ADN chia sẻ {ty_le*100:.0f}% locus ({chung} locus chung)")

    else:
        return None

    # ----- Địa lý (thu hẹp kết quả) -----
    sim_that_lac = location_similarity(user_vi_tri, target_vi_tri)
    if sim_that_lac >= 0.35:
        bonus = sim_that_lac * 22
        score += bonus
        reasons.append(f"Vị trí thất lạc tương đồng {sim_that_lac*100:.0f}%")

    sim_truoc = location_similarity(user_dia_chi_truoc, target_dia_chi_truoc)
    if sim_truoc >= 0.25:
        bonus = sim_truoc * 14
        score += bonus
        reasons.append(f"Địa chỉ trước đây tương đồng {sim_truoc*100:.0f}%")

    sim_hien = location_similarity(user_dia_chi_hien, target_dia_chi_hien)
    if sim_hien >= 0.3:
        score += sim_hien * 6
        reasons.append(f"Địa chỉ hiện tại gần nhau {sim_hien*100:.0f}%")

    # Năm thất lạc gần nhau → cộng nhẹ
    if user_nam and target_nam:
        try:
            # Lấy số năm đầu tiên xuất hiện
            y1 = int(re.search(r"\d{4}", user_nam).group())
            y2 = int(re.search(r"\d{4}", target_nam).group())
            diff = abs(y1 - y2)
            if diff <= 3:
                score += 5
                reasons.append(f"Năm thất lạc gần nhau (cách {diff} năm)")
            elif diff <= 8:
                score += 2
        except Exception:
            pass

    return {
        "score": round(score, 1),
        "loai_quan_he": loai_quan_he,
        "reasons": reasons,
    }
