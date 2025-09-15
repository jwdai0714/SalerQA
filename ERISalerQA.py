from flask import Flask, render_template, request
import re, os
import pdfplumber
from pdf2image import convert_from_path
import pytesseract
from flask import Flask
from pathlib import Path

app = Flask(__name__)
PASSWORD = "ERISaler123Abc"

def grab_section(text, start_no, start_title, next_no=None, next_title=None):
    """
    從 text 取出「第 start_no 節 start_title」到「第 next_no 節 next_title」之前的內容。
    - 若 next_no/next_title 省略，則抓到文末。
    - 允許『十二、』『十二.』『十二 』等標題型式。
    """
    if next_no and next_title:
        pat = rf"{start_no}[、\.\s]*{start_title}\s*([\s\S]+?){next_no}[、\.\s]*{next_title}"
    else:
        pat = rf"{start_no}[、\.\s]*{start_title}\s*([\s\S]+)$"
    m = re.search(pat, text)
    return m.group(1).strip() if m else None



# ======= Windows：請填入你實際的路徑 =======
TESS_PATH   = r"C:\Program Files\Tesseract-OCR\tesseract.exe"          # tesseract.exe
POPLER_BIN  = r"C:\Program Files\poppler-24.08.0\Library\bin"          # 有 bin 的資料夾
# ===========================================

if os.path.exists(TESS_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESS_PATH

def to_halfwidth(s: str) -> str:
    out=[]
    for ch in s:
        o=ord(ch)
        if o==0x3000: o=32
        elif 0xFF01<=o<=0xFF5E: o-=0xFEE0
        out.append(chr(o))
    return "".join(out)

def _normalize(text: str) -> str:
    text = to_halfwidth(text)
    text = re.sub(r'(?<=[A-Za-z0-9])\s+(?=[A-Za-z0-9])', '', text)  # 1 4 / D R → 14 / DR
    text = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', text)
    text = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[，。！？、；：「」])', '', text)
    text = re.sub(r'([,、）)])\n(?=\w)', r'\1 ', text)
    text = re.sub(r'\n{2,}', '\n', text)
    return text

def _ocr_page(pdf_path: str, page_index: int) -> str:
    imgs = convert_from_path(
        pdf_path, dpi=300, first_page=page_index+1, last_page=page_index+1,
        poppler_path=POPLER_BIN if os.path.exists(POPLER_BIN) else None
    )
    if not imgs:
        return ""
    return pytesseract.image_to_string(imgs[0], lang='chi_tra+eng') or ""

def load_pdf_text(pdf_path: Path) -> str:
    print(">>> load_pdf_text: FORCE OCR from section 12 onwards")
    # 1) 先用 pdfplumber 抽字
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for p in pdf.pages:
            pages.append(p.extract_text() or "")
    print(f">>> pdfplumber pages: {len(pages)}")

    # 2) 找「十二」的頁碼，若找不到就從第 1 頁開始
    start_idx = None
    for i, t in enumerate(pages):
        if "十二" in (t or ""):
            start_idx = i
            break
    if start_idx is None:
        start_idx = 0
    print(f">>> force OCR from page index: {start_idx} to {len(pages)-1}")

    # 3) 強制 OCR：從 start_idx 到最後一頁全部 OCR，若 OCR 文字比原文長就覆蓋
    for i in range(start_idx, len(pages)):
        try:
            ocr_txt = _ocr_page(pdf_path, i)
            if len(ocr_txt.strip()) > len((pages[i] or "").strip()):
                pages[i] = ocr_txt
                print(f">>> OCR replaced page {i} (len={len(ocr_txt)})")
            else:
                print(f">>> OCR shorter/empty page {i} (keep original)")
        except Exception as e:
            print(f">>> OCR fail page {i}: {e}")

    text = "\n".join(pages)
    text = _normalize(text)
    print(">>> load_pdf_text: DONE, length =", len(text))
    return text

PDF_PATH = Path(app.root_path) / "EnergyResource3.pdf"
pdf_text = load_pdf_text(PDF_PATH)
print("len(pdf_text) =", len(pdf_text))
CN2AR = {"十二":"12","十三":"13","十四":"14","十五":"15","十六":"16","十七":"17","十八":"18","十九":"19"}

def _section_regex(no_cn: str, title_kw: str) -> str:
    no_ar = CN2AR.get(no_cn, no_cn)              # 十二 -> 12
    title_kw = re.escape(title_kw)
    return rf"(?:第\s*)?(?:{no_cn}|{no_ar})[、\.\s]*{title_kw}\S{{0,12}}"

def grab_section(text, start_no, start_title, next_no=None, next_title=None):
    start_pat = _section_regex(start_no, start_title)
    if next_no and next_title:
        end_pat = _section_regex(next_no, next_title)
        pat = rf"{start_pat}\s*([\s\S]+?){end_pat}"
    else:
        pat = rf"{start_pat}\s*([\s\S]+)$"
    m = re.search(pat, text, flags=re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None

def extract_sentences(text, kw):
    pat = rf"[^\n。]*{re.escape(kw)}[^\n。]*[。]?"
    hits = re.findall(pat, text, flags=re.IGNORECASE)
    seen, out = set(), []
    for h in hits:
        h = h.strip()
        if h and h not in seen:
            seen.add(h); out.append(h)
    return out


for k in ["十二","腳架設計考量","十三","現場拍攝問題","十四","行李箱","十五","DR","十六","影像判讀","十九","充電"]:
    print(k, "→", ("YES" if k in pdf_text else "NO"))

# 問答邏輯
def answer_question(text, query):
    query = query.strip().lower()
    if "英文" in query and "公司" in query:
        match = re.search(r"能資國際股份有限公司（([A-Za-z ,\.]+)）", text)
        return f"公司英文名稱：{match.group(1)}" if match else "❌ 找不到公司英文名稱。"
    elif "成立" in query or "創立" in query:
        match = re.search(r"成立時間[:：\s]?([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日)", text)
        return f"成立時間：{match.group(1)}" if match else "❌ 找不到成立時間。"
    elif "資本" in query:
        match = re.search(r"實收資本額[:：\s]?([^\n]+)", text)
        return f"實收資本額：{match.group(1)}" if match else "❌ 找不到資本資訊。"
    elif "董事長" in query or "負責人" in query:
        match = re.search(r"(負責人|董事長)[:：\s]?([^\n]+)", text)
        return f"{match.group(1)}：{match.group(2)}" if match else "❌ 找不到負責人資訊。"
    elif "員工" in query or "人數" in query:
        match = re.search(r"員工人數[:：]?\s*約?\s*([^\n]+)", text)
        return f"員工人數：約 {match.group(1)}" if match else "❌ 找不到員工人數資訊。"
    elif "地址" in query or "地點" in query:
        match = re.search(r"地址[:：]?\s*([^\n]+)", text)
        return f"公司地址：{match.group(1)}" if match else "❌ 找不到地址資訊。"
    elif "基本資料" in query or "公司概況" in query:
        match = re.search(r"一[、.\s]*公司概況\s*(.+?)二[、.\s]*營業項目", text, re.DOTALL)
        return "能資公司基本資料：\n" + match.group(1).strip() if match else "❌ 找不到公司概況內容。"
    elif "認證" in query or "證照" in query:
        # 抓取帶有年份 + 認證字樣 的完整句子
        matches = re.findall(r"(20[0-9]{2}年[^\n。]*(?:TFDA|FDA|ISO\s?13485|GMP|QMS)[^\n。]*[。])", text)
        matches = list(dict.fromkeys(matches))  # 去重複
        return "認證紀錄：\n" + "\n".join(matches) if matches else "❌ 無法找到認證紀錄。"
    elif "產品" in query and ("特色" in query or "規格" in query):
        match = re.search(r"五、產品規格與特徵(.+?)六、應用場景", text, re.DOTALL)
        return "產品規格與特徵：\n" + match.group(1).strip() if match else "❌ 找不到產品規格與特徵。"
    elif "應用" in query and ("場景" in query or "環境" in query):
        match = re.search(r"六、應用場景與實證案例(.+?)七、AI智慧醫療", text, re.DOTALL)
        return "應用場景與環境：\n" + match.group(1).strip() if match else "❌ 找不到應用場景內容。"
    elif "環境" in query or ("待遇" in query or "薪資" in query or "薪水" in query):
        return """能資公司工作環境與待遇資訊（非公開文件資料，以下為推估）：\n• 員工人數少，扁平化組織，溝通效率高\n• 位於新竹生醫園區，工作環境乾淨明亮\n• 以技術研發為主軸，研發人員為核心團隊\n• 依職務不同，月薪約落在35,000~70,000元不等\n• 員工具備跨領域整合能力，研發自由度高\n• 福利方面提供勞健保、特休、專案獎金與彈性工時\n※ 若需進一步精確薪資與職缺資訊，建議查詢 104 職缺或聯繫人資部門。"""
    elif any(k in query for k in ["能資軟體", "開發軟體", "辨識軟體", "肺炎", "肺部疾病", "病徵", "肺不張", "肺氣腫", "心臟肥大", "covid", "肺結核"]):
        match = re.search(r"十一[、.\s]*AI軟體\s*([\s\S]+?)十二[、.\s]*其他狀況", text)
        if match:
            content = match.group(1).replace('\n', ' ').strip()
            # 用正規表示式，在每個 (1)(2)... 前加換行
            content = re.sub(r"\(\d\)", lambda m: "\n" + m.group(0), content)
            return "✅ AI軟體資訊：" + content
        else:
            return "❌ 找不到 AI 軟體相關資訊。"
    elif "軟體" in query or "AI" in query:
        match = re.search(r"七、AI智慧醫療整合系統(.+?)八、技術貢獻", text, re.DOTALL)
        return "軟體系統：\n" + match.group(1).strip() if match else "❌ 無法找到軟體資訊。"
    elif "技術貢獻" in query or "產業貢獻" in query:
        match = re.search(r"八[、.\s]*技術貢獻與產業價值\s*([\s\S]*)九、獲獎", text)
        return "能資公司技術貢獻與產業價值：\n" + match.group(1).strip() if match else "❌ 無法找到技術貢獻內容。"
    elif "技術" in query or "核心技術" in query or "技術亮點" in query:
        match = re.search(r"四、核心技術亮點\s*(.*?)五、產品規格與特徵", text, re.S)
        return "能資公司核心技術亮點：\n" + match.group(1).strip() if match else "❌ 無法找到核心技術亮點內容。"
    elif "產品" in query:
        match = re.search(r"五、產品規格與特徵(.+?)六、應用場景", text, re.DOTALL)
        return "產品規格與特徵：\n" + match.group(1).strip() if match else "❌ 找不到產品規格與特徵。"
    elif "經營理念" in query or "宗旨" in query or "目標" in query:
        return """能資公司經營理念（推估自公司概況）：\n以奈米碳管 X 光技術為核心，結合 AI 與遠距診療、在宅醫療應用，致力於改善醫療可近性、提升偏鄉與緊急醫療效率，並建立台灣自主醫療設備研發供應鏈。"""
    elif "獎" in query or "得獎" in query or "獲獎" in query:
        match = re.search(r"九[、.\s]*獲獎\s*(.+?)十[、.\s]*醫學影像上傳流程", text, re.DOTALL)
        return "能資公司獲獎紀錄：\n" + match.group(1).strip() if match else "❌ 找不到獲獎紀錄內容。"
    elif any(k in query for k in
             ["無線上傳", "有線上傳", "影像上傳", "影像傳輸", "電腦影像", "影像傳回", "筆電", "院內", "PACS", "無線傳輸", "有線傳輸"]):
        match = re.search(r"十[、.\s]*醫學影像上傳流程\s*([\s\S]+?)十一[、.\s]*AI軟體", text)
        return "醫學影像上傳流程：\n" + match.group(1).strip() if match else "❌ 找不到醫學影像上傳流程內容。"
    elif "歷史" in query or "沿革" in query or "發展" in query:
        match = re.search(r"三[、.\s]*歷史沿革與技術發展\s*(.+?)四[、.\s]*核心技術亮點", text, re.DOTALL)
        return "公司歷史沿革與技術發展：\n" + match.group(1).strip() if match else "❌ 找不到公司歷史資料。"
    # 12. 腳架設計考量
    elif any(k in query for k in ["腳架", "腳架設計", "腳架晃", "床很軟", "放不進去"]):
        sec = grab_section(text, "十二", "腳架設計考量", "十三", "現場拍攝問題")
        if sec:
            return "腳架設計考量：\n" + sec
        hits = re.findall(r"[^\n。]*腳架[^\n。]*[。]?", text, flags=re.IGNORECASE)
        hits = [h.strip() for h in dict.fromkeys(hits) if h.strip()]
        return ("腳架設計考量（關鍵字擷取）：\n" + "\n".join(hits)) if hits else "❌ 找不到「腳架設計考量」。"

    # 13. 現場拍攝問題
    elif any(k in query for k in ["現場拍攝", "無法成像", "成像", "誰可以操作", "核安會", "在宅急症", "拍攝間隔"]):
        sec = grab_section(text, "十三", "現場拍攝問題", "十四", "行李箱")
        if sec:
            return "現場拍攝問題：\n" + sec
        hits = re.findall(r"[^\n。]*現場拍攝[^\n。]*[。]?", text, flags=re.IGNORECASE)
        hits = [h.strip() for h in dict.fromkeys(hits) if h.strip()]
        return ("現場拍攝問題（關鍵字擷取）：\n" + "\n".join(hits)) if hits else "❌ 找不到「現場拍攝問題」。"

    # 14. 行李箱
    elif "行李箱" in query:
        sec = grab_section(text, "十四", "行李箱", "十五", "DR")
        if sec:
            return "行李箱：\n" + sec
        hits = re.findall(r"[^\n。]*行李箱[^\n。]*[。]?", text, flags=re.IGNORECASE)
        hits = [h.strip() for h in dict.fromkeys(hits) if h.strip()]
        return ("行李箱（關鍵字擷取）：\n" + "\n".join(hits)) if hits else "❌ 找不到「行李箱」。"

    # 15. DR（只處理 DR，本分支不含防塵/防水）
    elif any(k in query.upper() for k in ["DR", "DR軟體", "DR板", "DR 系統"]):
        sec = grab_section(text, "十五", "DR", "十六", "影像判讀")  # ← 注意終點是十六
        if sec:
            return "DR：\n" + sec
        hits = re.findall(r"[^\n。]*DR[^\n。]*[。]?", text, flags=re.IGNORECASE)
        hits = [h.strip() for h in dict.fromkeys(hits) if h.strip()]
        return ("DR（關鍵字擷取）：\n" + "\n".join(hits)) if hits else "❌ 找不到「DR」。"

    # 規格屬性（防塵/防水/耐重/IP…）——與 DR 分開
    elif any(k in query for k in ["防塵", "防水", "耐重", "ip", "耐撞", "跌落", "承重"]):
        spec = re.search(r"五[、.\s]*產品規格與特徵\s*([\s\S]+?)六[、.\s]*應用場景", text, flags=re.DOTALL)
        for kw in ["防塵", "防水", "耐重", "ip", "耐撞", "跌落", "承重"]:
            if kw in query:
                target_kw = kw;
                break
        if spec:
            hits = re.findall(rf"[^\n。]*{re.escape(target_kw)}[^\n。]*[。]?", spec.group(1), flags=re.IGNORECASE)
            hits = [h.strip() for h in dict.fromkeys(hits) if h.strip()]
            if hits:
                label = target_kw.upper() if target_kw == "ip" else target_kw
                return f"產品規格（{label}）：\n" + "\n".join(hits)
        # 章節找不到就全文件補搜
        hits = re.findall(rf"[^\n。]*{re.escape(target_kw)}[^\n。]*[。]?", text, flags=re.IGNORECASE)
        hits = [h.strip() for h in dict.fromkeys(hits) if h.strip()]
        label = target_kw.upper() if target_kw == "ip" else target_kw
        return (f"相關敘述（{label}）：\n" + "\n".join(hits)) if hits else f"❌ 找不到與「{label}」相關的敘述。"

    # 16. 影像判讀
    elif any(k in query for k in ["影像判讀", "即時判讀", "gpu", "顯卡"]):
        sec = grab_section(text, "十六", "影像判讀", "十七", "陸方原料")
        if sec:
            return "影像判讀：\n" + sec
        hits = re.findall(r"[^\n。]*影像判讀[^\n。]*[。]?", text, flags=re.IGNORECASE)
        hits = [h.strip() for h in dict.fromkeys(hits) if h.strip()]
        return ("影像判讀（關鍵字擷取）：\n" + "\n".join(hits)) if hits else "❌ 找不到「影像判讀」。"

    # 17. 陸方原料
    elif any(k in query for k in ["陸方原料", "材料來源", "球管", "大陸製"]):
        sec = grab_section(text, "十七", "陸方原料", "十八", "保固問題")
        if sec:
            return "陸方原料：\n" + sec
        hits = re.findall(r"[^\n。]*陸方原料[^\n。]*[。]?", text, flags=re.IGNORECASE)
        hits = [h.strip() for h in dict.fromkeys(hits) if h.strip()]
        return ("陸方原料（關鍵字擷取）：\n" + "\n".join(hits)) if hits else "❌ 找不到「陸方原料」。"

    # 18. 保固問題
    elif any(k in query for k in ["保固", "保養", "多久保養", "維修"]):
        sec = grab_section(text, "十八", "保固問題", "十九", "充電")
        if sec:
            return "保固問題：\n" + sec
        hits = re.findall(r"[^\n。]*保固[^\n。]*[。]?", text, flags=re.IGNORECASE)
        hits = [h.strip() for h in dict.fromkeys(hits) if h.strip()]
        return ("保固問題（關鍵字擷取）：\n" + "\n".join(hits)) if hits else "❌ 找不到「保固問題」。"

    # 19. 充電（最後一節）
    elif any(k in query for k in ["充電", "續航", "拍幾張", "電池", "電量"]):
        sec = grab_section(text, "十九", "充電")
        if sec:
            return "充電：\n" + sec
        hits = re.findall(r"[^\n。]*充電[^\n。]*[。]?", text, flags=re.IGNORECASE)
        hits = [h.strip() for h in dict.fromkeys(hits) if h.strip()]
        return ("充電（關鍵字擷取）：\n" + "\n".join(hits)) if hits else "❌ 找不到「充電」。"


    elif "價格" in query or "價錢" in query or "費用" in query or "報價" in query:
        return "❓ 此問題請洽業務人員：E-mail:sales@roentxen.com, TEL: 03-6585156 #104 張副總"
    else:
        return "❓ 此問題無法處理，請明確描述問題內容。"


# === 登入頁面 ===
@app.route("/", methods=["GET", "POST"])
def login_and_qa():
    if request.method == "POST":
        password = request.form.get("password")
        if password == PASSWORD:
            # 密碼正確 → 直接顯示 Q&A 頁面
            query = request.form.get("query")
            if query:  # 使用者已經輸入問題
                answer = answer_question(pdf_text, query)
                return render_template("index.html", question=query, answer=answer)
            return render_template("index.html")  # 顯示 Q&A 表單
        else:
            return render_template("login.html", error="❌ 密碼錯誤")
    return render_template("login.html")  # 初始畫面顯示登入

@app.route("/ask", methods=["POST"])
def ask():
    query = request.form["query"]
    answer = answer_question(pdf_text, query)
    return render_template("index.html", question=query, answer=answer)

@app.route("/_debug_pages")
def _debug_pages():
    lengths = []
    with pdfplumber.open(PDF_PATH) as pdf:
        for i, p in enumerate(pdf.pages):
            t = p.extract_text() or ""
            lengths.append(f"page {i}: len={len(t)}")
    return "<br>".join(lengths)

def grab_section(text, start_no, start_title, next_no=None, next_title=None):
    """
    從 text 取出「第 start_no 節 start_title」到「第 next_no 節 next_title」之前的內容。
    - 若 next_no/next_title 省略，則抓到文末。
    - 允許『十二、』『十二.』『十二 』等標題型式。
    """
    if next_no and next_title:
        pat = rf"{start_no}[、\.\s]*{start_title}\s*([\s\S]+?){next_no}[、\.\s]*{next_title}"
    else:
        pat = rf"{start_no}[、\.\s]*{start_title}\s*([\s\S]+)$"
    m = re.search(pat, text)
    return m.group(1).strip() if m else None


if __name__ == "__main__":
    app.run(debug=True)