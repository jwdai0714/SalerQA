# -*- coding: utf-8 -*-
from flask import Flask, render_template, request
from pypdf import PdfReader
import re

app = Flask(__name__)

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

# 載入 PDF 並轉成文字
def load_pdf_text(pdf_path):
    reader = PdfReader(pdf_path)
    text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    # 修正：中間是兩個中文字，卻有空格
    text = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', text)
    # 修正：中文字與中文標點之間的空格
    text = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[，。！？、；：「」])', '', text)
    # 修正：標點符號或括號之後不該換行的地方換行了
    text = re.sub(r'([,、）)])\n(?=\w)', r'\1 ', text)
    # 可選：將多個連續換行縮減為一行
    text = re.sub(r'\n{2,}', '\n', text)
    return text


pdf_text = load_pdf_text("EnergyResource3.pdf")

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
        return "腳架設計考量：\n" + sec if sec else "❌ 找不到「腳架設計考量」。"
    # 13. 現場拍攝問題
    elif any(k in query for k in ["現場拍攝", "無法成像", "成像", "誰可以操作", "核安會", "在宅急症", "拍攝間隔"]):
        sec = grab_section(text, "十三", "現場拍攝問題", "十四", "行李箱")
        return "現場拍攝問題：\n" + sec if sec else "❌ 找不到「現場拍攝問題」。"
    # 14. 行李箱
    elif "行李箱" in query:
        sec = grab_section(text, "十四", "行李箱", "十五", "DR")
        return "行李箱：\n" + sec if sec else "❌ 找不到「行李箱」。"
    # 15. DR
    elif any(k in query for k in ["DR", "防水", "防塵", "耐重", "DR軟體", "DR板", "不帶電腦", "其他品牌"]):
        sec = grab_section(text, "十五", "DR", "十六", "影像判讀")
        return "DR：\n" + sec if sec else "❌ 找不到「DR」。"
    # 16. 影像判讀
    elif any(k in query for k in ["影像判讀", "即時判讀", "GPU", "顯卡"]):
        sec = grab_section(text, "十六", "影像判讀", "十七", "陸方原料")
        return "影像判讀：\n" + sec if sec else "❌ 找不到「影像判讀」。"
    # 17. 陸方原料
    elif any(k in query for k in ["陸方原料", "材料來源", "球管", "大陸製"]):
        sec = grab_section(text, "十七", "陸方原料", "十八", "保固問題")
        return "陸方原料：\n" + sec if sec else "❌ 找不到「陸方原料」。"
    # 18. 保固問題
    elif any(k in query for k in ["保固", "保養", "多久保養", "維修"]):
        sec = grab_section(text, "十八", "保固問題", "十九", "充電")
        return "保固問題：\n" + sec if sec else "❌ 找不到「保固問題」。"
    # 19. 充電（最後一節，沒有下一節標題）
    elif any(k in query for k in ["充電", "續航", "拍幾張", "電池", "電量"]):
        sec = grab_section(text, "十九", "充電")  # 沒有 next_no / next_title，抓到文末
        return "充電：\n" + sec if sec else "❌ 找不到「充電」。"
    elif "價格" in query or "價錢" in query or "費用" in query or "報價" in query:
        return "❓ 此問題請洽業務人員：E-mail:sales@roentxen.com, TEL: 03-6585156 #104 張副總"
    else:
        return "❓ 此問題無法處理，請明確描述問題內容。"

# 首頁
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

# 查詢處理
@app.route("/ask", methods=["POST"])
def ask():
    query = request.form["query"]
    answer = answer_question(pdf_text, query)
    return render_template("index.html", question=query, answer=answer)

if __name__ == "__main__":
    app.run(debug=True)