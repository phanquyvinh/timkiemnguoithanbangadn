const LOCI = [
    { id: "D3S1358", default: "14, 15" },
    { id: "vWA",     default: "16, 17" },
    { id: "FGA",     default: "21, 24" },
    { id: "TH01",    default: "6, 9.3" },
    { id: "D21S11",  default: "29, 30" },
    { id: "D18S51",  default: "12, 15" },
    { id: "D5S818",  default: "11, 12" },
    { id: "D13S317", default: "8, 12" },
    { id: "D7S820",  default: "9, 10" },
    { id: "D16S539", default: "11, 13" },
    { id: "CSF1PO",  default: "10, 12" },
    { id: "TPOX",    default: "8, 8" },
];

function renderDnaGrid() {
    const grid = document.getElementById("dnaGrid");
    grid.innerHTML = LOCI.map(l => `
        <div class="dna-cell">
            <label for="${l.id}">${l.id}</label>
            <input type="text" id="${l.id}" value="${l.default}" required
                   pattern="[0-9]+(\\.[0-9]+)?\\s*,\\s*[0-9]+(\\.[0-9]+)?"
                   title="Nhập 2 số cách nhau bằng dấu phẩy">
        </div>
    `).join("");
}

function parseDNA(val) {
    const parts = val.split(",").map(s => parseFloat(s.trim()));
    if (parts.length !== 2 || parts.some(isNaN)) {
        throw new Error("Mỗi locus cần đúng 2 allele hợp lệ");
    }
    return parts;
}

function escapeHtml(str) {
    if (!str) return "";
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
}

function showResult(el, html, isError = false) {
    el.hidden = false;
    el.className = "result-box " + (isError ? "error" : "success");
    el.innerHTML = html;
    el.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function submitForm(e) {
    e.preventDefault();
    const btn = document.getElementById("btnSubmit");
    const btnText = btn.querySelector(".btn-text");
    const btnLoading = btn.querySelector(".btn-loading");
    const resultBox = document.getElementById("result");

    btn.disabled = true;
    btnText.hidden = true;
    btnLoading.hidden = false;

    try {
        const dna_data = {};
        for (const l of LOCI) {
            dna_data[l.id] = parseDNA(document.getElementById(l.id).value);
        }

        const payload = {
            ho_ten: document.getElementById("ho_ten").value.trim(),
            loai_tim_kiem: document.getElementById("loai_tim_kiem").value,
            so_dien_thoai: document.getElementById("so_dien_thoai").value.trim(),
            email: document.getElementById("email").value.trim(),
            dia_chi_hien_tai: document.getElementById("dia_chi_hien_tai").value.trim(),
            dia_chi_truoc_day: document.getElementById("dia_chi_truoc_day").value.trim() || null,
            vi_tri_that_lac: document.getElementById("vi_tri_that_lac").value.trim() || null,
            nam_that_lac: document.getElementById("nam_that_lac").value.trim() || null,
            dna_data,
        };

        const res = await fetch("/api/dang-ky-tim-kiem/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await res.json();

        if (!res.ok) {
            const msg = data.detail
                ? (Array.isArray(data.detail) ? data.detail.map(d => d.msg || JSON.stringify(d)).join("<br>") : data.detail)
                : "Có lỗi xảy ra.";
            throw new Error(msg);
        }

        let matchHtml = "";
        if (data.goi_y_phah_he?.length) {
            matchHtml = `
                <div class="match-list">
                    <p><strong>Kết quả khoanh vùng (${data.so_luong_trung_khop_uoc_tinh} hồ sơ):</strong></p>
                    ${data.goi_y_phah_he.map(m => `
                        <div class="match-item">
                            <div class="name">${escapeHtml(m.ho_ten)}</div>
                            <div class="type">${escapeHtml(m.loai_quan_he)}</div>
                            <div class="score">Điểm tin cậy: <strong>${m.diem_tin_cay}</strong></div>
                            ${m.ly_do?.length ? `<ul class="reasons">${m.ly_do.map(r => `<li>${escapeHtml(r)}</li>`).join("")}</ul>` : ""}
                            <div style="margin-top:6px;font-size:0.8rem;color:#047857;">${escapeHtml(m.thong_bao)}</div>
                        </div>
                    `).join("")}
                </div>`;
        } else {
            matchHtml = `<p style="margin-top:12px;">Chưa tìm thấy hồ sơ đạt ngưỡng. Hồ sơ của bạn đã được lưu và sẽ tự động so khớp khi có dữ liệu mới.</p>`;
        }

        showResult(resultBox, `
            <h3>✅ ${escapeHtml(data.status)}</h3>
            <p>Mã hồ sơ (hãy lưu lại):</p>
            <div class="ma-ho-so">${escapeHtml(data.ma_ho_so)}</div>
            <p style="font-size:0.9rem;">${escapeHtml(data.huong_dan || "")}</p>
            ${matchHtml}
            <p style="margin-top:16px;font-size:0.8rem;color:#64748b;">${escapeHtml(data.copyright || "")}</p>
        `);
    } catch (err) {
        showResult(resultBox, `<h3>❌ Không thể gửi hồ sơ</h3><p>${escapeHtml(err.message)}</p>`, true);
    } finally {
        btn.disabled = false;
        btnText.hidden = false;
        btnLoading.hidden = true;
    }
}

async function lookupHoSo() {
    const id = document.getElementById("lookupId").value.trim();
    const box = document.getElementById("lookupResult");
    if (!id) {
        showResult(box, "<p>Vui lòng nhập mã hồ sơ.</p>", true);
        return;
    }
    try {
        const res = await fetch(`/api/tra-cuu/${encodeURIComponent(id)}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Không tìm thấy");
        showResult(box, `
            <h3>Trạng thái hồ sơ</h3>
            <p><strong>Họ tên:</strong> ${escapeHtml(data.ho_ten)}</p>
            <p><strong>Loại tìm kiếm:</strong> ${escapeHtml(data.loai_tim_kiem)}</p>
            <p><strong>Trạng thái:</strong> ${escapeHtml(data.status)}</p>
            <p><strong>Ngày tạo:</strong> ${escapeHtml(data.created_at || "")}</p>
            <p style="margin-top:10px;font-size:0.9rem;">${escapeHtml(data.thong_bao)}</p>
        `);
    } catch (err) {
        showResult(box, `<p>${escapeHtml(err.message)}</p>`, true);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    renderDnaGrid();
    document.getElementById("dnaForm").addEventListener("submit", submitForm);
    document.getElementById("btnLookup").addEventListener("click", lookupHoSo);
});
