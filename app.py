import datetime
import re
from io import BytesIO

import pandas as pd
import streamlit as st
from docx import Document
from docx.shared import Mm
from docxtpl import DocxTemplate, InlineImage
from openpyxl import load_workbook
from PIL import Image


st.set_page_config(page_title="试验报告自动生成", layout="wide")
st.title("试验报告自动生成系统")


# ============================
# Word 中图片尺寸（毫米）
# A4 横向页扣除常见页边距后的可用区域约为 233 x 159 mm。
# 图片高度控制在 130 mm 左右，给图片下方预留约三行文字空间。
# ============================
LANDSCAPE_IMG_WIDTH_MM = 233
LANDSCAPE_IMG_HEIGHT_MM = 130

# ============================
# 合成参数（像素）
# ============================
LANDSCAPE_CANVAS_WIDTH_PX = 3600
LANDSCAPE_CANVAS_HEIGHT_PX = 2010
ROW_GAP_PX = 34
COL_GAP_PX = 34
CANVAS_PADDING_PX = 70
BG_COLOR = (255, 255, 255)
DELETE_PARAGRAPH_MARKER = "__DELETE_EMPTY_REPORT_POSITION__"

COMMISSION_SHEET_KEYWORD = "试验委托单"
SUPPLEMENT_SHEET_KEYWORD = "所需要信息"

PERSONNEL_OPTIONS = [
    "刘灿",
    "李俊波",
    "谢炎君",
    "赵洪暄",
    "苏哲",
    "赵连征",
    "范宽宇",
    "梁欣语",
    "黄旭",
    "邹宏宇",
    "丁何益",
    "陈天易",
    "周晨",
    "郭帅帅",
    "姜贝贝",
]

REPORT_FIELD_ORDER = [
    "报告编号",
    "试验名称",
    "产品名称",
    "产品型号",
    "产品代号",
    "产品编号",
    "委托单号",
    "送试单位",
    "单位地址",
    "试验日期",
    "接收日期",
    "试验目的",
    "试验项目",
    "样品总数",
    "产品外观",
    "试验标准",
    "试验依据技术文件",
    "试验地点温度",
    "试验地点湿度",
    "试验准备时间",
    "试验地点",
    "试验过程",
    "撤收时间",
    "真空是否满足要求",
    "试验真空度",
    "温度是否满足要求",
    "试验温度",
    "时间是否满足要求",
    "试验保持时间",
    "降温是否满足要求",
    "试验降温速率",
    "升温是否满足要求",
    "试验升温速率",
    "循环是否满足要求",
    "试验循环次数",
    "试验备注",
    "流程控制软件",
    "流程控制版本",
    "测控软件",
    "测控版本",
    "试验技术负责人",
    "试验参加者",
    "真空度曲线",
    *[f"试验温度曲线{i:02d}" for i in range(1, 21)],
    "产品试验前状态",
    "产品试验后状态",
]

AUTO_FROM_COMMISSION_FIELDS = [
    "报告编号",
    "试验名称",
    "产品名称",
    "产品型号",
    "产品代号",
    "产品编号",
    "委托单号",
    "送试单位",
    "单位地址",
    "试验项目",
    "样品总数",
    "试验标准",
    "试验依据技术文件",
]

DATE_FIELDS = ["接收日期", "试验准备时间", "撤收时间"]
DATE_RANGE_FIELDS = ["试验日期"]

MANUAL_TEXT_FIELDS = [
    "试验目的",
    "试验地点温度",
    "试验地点湿度",
    "试验过程",
    "试验真空度",
    "试验温度",
    "试验保持时间",
    "试验降温速率",
    "试验升温速率",
    "试验循环次数",
]

NAME_TEXT_FIELDS = [
    "真空度曲线",
    "产品试验前状态",
    "产品试验后状态",
    *[f"试验温度曲线{i:02d}" for i in range(1, 21)],
]

OPTIONAL_IMAGE_FIELDS = [
    "真空度曲线",
    *[f"试验温度曲线{i:02d}" for i in range(1, 21)],
]

SELECT_FIELD_OPTIONS = {
    "产品外观": ["未发现异常，其它（见照片）", "有异常（见照片）"],
    "试验地点": ["一区试验大厅", "二区试验大厅"],
    "真空是否满足要求": ["满足", "不满足", "不适用"],
    "温度是否满足要求": ["满足", "不满足", "不适用"],
    "时间是否满足要求": ["满足", "不满足", "不适用"],
    "降温是否满足要求": ["满足", "不满足", "不适用"],
    "升温是否满足要求": ["满足", "不满足", "不适用"],
    "循环是否满足要求": ["满足", "不满足", "不适用"],
    "试验备注": [
        "配合客户开展产品性能测试，依托客户地面检测设备开展相关工作，实验室未对该数据的真实性、有效性进行验证，不承担相关责任。",
        "客户自行检测，数据结果由客户自行负责。",
    ],
}

DEVICE_VERSION_OPTIONS = {
    "KM3": {
        "流程控制软件": "KM3流程控制软件",
        "流程控制版本": "Touchvew7.5.1.0",
        "测控软件": "KM3测控软件",
        "测控版本": "dlkw2025-V2.2.1.2.0",
    },
    "KM3L": {
        "流程控制软件": "KM3L流程控制软件",
        "流程控制版本": "ForceContro8.1.0.20",
        "测控软件": "KM3L测控软件",
        "测控版本": "dlkw2025-V2.2.1.0.3",
    },
    "KM5": {
        "流程控制软件": "KM5流程控制软件",
        "流程控制版本": "",
        "测控软件": "KM5测控软件",
        "测控版本": "",
    },
    "BZ1": {
        "流程控制软件": "BZ1流程控制软件",
        "流程控制版本": "Touchvew75.5.1.0",
        "测控软件": "BZ1测控软件",
        "测控版本": "dlkw2025-V2.2.1.0.3",
    },
    "BZ2": {
        "流程控制软件": "BZ2流程控制软件",
        "流程控制版本": "ForceContro8.1.0.20",
        "测控软件": "BZ2测控软件",
        "测控版本": "ForceContro8.1.0.20",
    },
    "CY-1000L-1": {
        "流程控制软件": "CY-1000L-1常压设备控制软件",
        "流程控制版本": "",
        "测控软件": "CY-1000L-1常压设备控制软件",
        "测控版本": "",
    },
    "CY-1000L-2": {
        "流程控制软件": "CY-1000L-2常压设备控制软件",
        "流程控制版本": "",
        "测控软件": "CY-1000L-2常压设备控制软件",
        "测控版本": "",
    },
    "CY-1000L-3": {
        "流程控制软件": "CY-1000L-3常压设备控制软件",
        "流程控制版本": "",
        "测控软件": "CY-1000L-3常压设备控制软件",
        "测控版本": "",
    },
}

IMAGE_EXTENSION_OPTIONS = ["", ".PNG", ".png", ".JPG", ".jpg", ".JPEG", ".jpeg"]


# ============================
# 通用工具
# ============================
def clean_text(value):
    """统一清理 Excel 单元格内容，避免 None、换行和多余空格影响匹配。"""
    if value is None:
        return ""

    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()

    if isinstance(value, datetime.datetime):
        if value.time() == datetime.time(0, 0):
            return value.strftime("%Y-%m-%d")
        return value.strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(value, datetime.date):
        return value.strftime("%Y-%m-%d")

    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s*\n\s*", " / ", text)
    return re.sub(r"[ \t\f\v]+", " ", text).strip()


def has_value(value):
    if value is None:
        return False
    if isinstance(value, list):
        return any(has_value(item) for item in value)
    return clean_text(value) != ""


def compact_label(value):
    return re.sub(r"\s+", "", clean_text(value)).replace("：", ":")


def to_compact_date(value):
    text = clean_text(value)
    if not text:
        return ""

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            return datetime.datetime.strptime(text[:10], fmt).strftime("%Y%m%d")
        except ValueError:
            continue

    match = re.search(r"(\d{4})\D?(\d{1,2})\D?(\d{1,2})", text)
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}{int(month):02d}{int(day):02d}"
    return text


def normalize_order_number(value):
    text = clean_text(value)
    text = re.sub(r"\s*-\s*", "-", text)
    return re.sub(r"\s+", "", text)


def infer_report_number(order_number):
    order_number = normalize_order_number(order_number)
    if not order_number:
        return ""
    if re.search(r"[A-Za-z]$", order_number):
        return order_number[:-1] + "c"
    return order_number


def infer_product_code(product_number):
    codes = []
    for part in re.split(r"\s*/\s*", clean_text(product_number)):
        code = re.sub(r"[（(].*?[）)]", "", part).strip()
        if code:
            codes.append(code)
    return "，".join(codes)


def infer_sample_count(product_number):
    text = clean_text(product_number)
    if not text:
        return ""

    total = 0
    for part in re.split(r"\s*/\s*", text):
        match = re.search(r"[（(](.*?)[）)]", part)
        if match:
            items = [item for item in re.split(r"[、,，;；\s]+", match.group(1)) if item]
            total += len(items)
        elif clean_text(part):
            total += 1

    return str(total) if total else ""


def infer_test_purpose(context):
    product = "".join(
        item
        for item in [context.get("产品型号", ""), context.get("产品名称", "")]
        if has_value(item)
    )
    test_item = clean_text(context.get("试验项目", ""))

    env_map = {
        "真空热试验": "热真空环境",
        "热真空试验": "热真空环境",
        "热平衡试验": "热平衡环境",
        "振动试验": "振动环境",
        "冲击试验": "冲击环境",
        "高温试验": "高温环境",
        "低温试验": "低温环境",
    }
    environment = env_map.get(test_item, test_item)

    if not product or not environment:
        return ""

    return f"检验{product}承受{environment}的能力，验证产品设计的合理性，暴露产品中元器件、材料和制造工艺的缺陷"


def find_sheet(workbook, keyword):
    for sheet_name in workbook.sheetnames:
        if keyword in sheet_name:
            return workbook[sheet_name]
    return None


def find_value_right(ws, label, max_col_offset=12):
    """在同一行从标签右侧寻找第一个非空值，适配委托单里的合并单元格布局。"""
    target = compact_label(label)

    for row in ws.iter_rows():
        for cell in row:
            if compact_label(cell.value) == target:
                for offset in range(1, max_col_offset + 1):
                    value = ws.cell(cell.row, cell.column + offset).value
                    if has_value(value):
                        return clean_text(value)
    return ""


def find_table_value(ws, header, rows_below=1, max_rows=4):
    """读取“型号/名称/产品编号”等表头下方的值。"""
    target = compact_label(header)

    for row in ws.iter_rows():
        for cell in row:
            if compact_label(cell.value) == target:
                for offset in range(rows_below, rows_below + max_rows):
                    value = ws.cell(cell.row + offset, cell.column).value
                    if has_value(value):
                        return clean_text(value)
    return ""


def read_key_value_sheet(ws):
    """兼容旧的“字段在 A 列、值在 B 列以后”的所需信息 sheet。"""
    context = {}
    key_order = []

    if ws is None:
        return context, key_order

    for row in ws.iter_rows(values_only=True):
        key = clean_text(row[0] if row else "")
        if not key:
            continue

        key_order.append(key)
        values = [clean_text(value) for value in row[1:] if has_value(value)]
        if not values:
            context[key] = ""
        elif len(values) == 1:
            context[key] = values[0]
        else:
            context[key] = values

    return context, key_order


def read_csv_context(data_file):
    data_file.seek(0)
    df = pd.read_csv(data_file, header=None)
    context = {}
    key_order = []

    for _, row in df.iterrows():
        key = clean_text(row.iloc[0])
        if not key:
            continue

        key_order.append(key)
        values = [clean_text(value) for value in row.iloc[1:] if has_value(value)]
        if not values:
            context[key] = ""
        elif len(values) == 1:
            context[key] = values[0]
        else:
            context[key] = values

    return context, key_order


def extract_from_commission_sheet(ws):
    """从“试验委托单（请在此页填写）”自动抽取报告模板常用字段。"""
    context = {
        "试验名称": find_value_right(ws, "试验项目（报告）名称"),
        "委托单号": normalize_order_number(find_value_right(ws, "委托单号")),
        "产品型号": find_table_value(ws, "型号"),
        "产品名称": find_table_value(ws, "名称"),
        "产品编号": find_table_value(ws, "产品编号"),
        "产品尺寸": find_table_value(ws, "尺寸（mm）"),
        "技术状态": find_value_right(ws, "技术状态"),
        "生产单位": find_value_right(ws, "生产单位"),
        "送样方式": find_value_right(ws, "送样方式"),
        "贮存要求": find_value_right(ws, "贮存要求"),
        "报告结论形式": find_value_right(ws, "报告结论形式"),
        "报告提交方式": find_value_right(ws, "报告提交方式"),
        "样品性能测试": find_value_right(ws, "样品性能测试"),
        "产品处置方式": find_value_right(ws, "产品处置方式"),
        "送试单位": find_value_right(ws, "单位名称"),
        "单位地址": find_value_right(ws, "单位地址"),
        "联系人": find_value_right(ws, "联系人"),
        "联系电话": find_value_right(ws, "联系电话"),
        "试验项目": find_value_right(ws, "试验类型"),
        "试验标准": find_value_right(ws, "试验依据标准"),
        "试验依据技术文件": find_value_right(ws, "试验依据技术文件"),
        "试验条件": find_value_right(ws, "试验条件"),
        "特殊要求": find_value_right(ws, "特殊要求"),
    }

    start_date = find_value_right(ws, "预估开始日期")
    end_date = find_value_right(ws, "预估完成日期")
    start_compact = to_compact_date(start_date)
    end_compact = to_compact_date(end_date)

    if start_compact and end_compact:
        context["试验日期"] = f"{start_compact}-{end_compact}"
    elif start_compact:
        context["试验日期"] = start_compact

    context["接收日期"] = start_compact
    context["报告编号"] = infer_report_number(context.get("委托单号", ""))
    context["产品代号"] = infer_product_code(context.get("产品编号", ""))
    context["样品总数"] = infer_sample_count(context.get("产品编号", ""))
    context["试验目的"] = infer_test_purpose(context)

    return {key: value for key, value in context.items() if has_value(value)}


def build_context_from_excel(data_file):
    data_file.seek(0)
    workbook = load_workbook(data_file, data_only=True)

    commission_ws = find_sheet(workbook, COMMISSION_SHEET_KEYWORD) or workbook.worksheets[0]
    supplement_ws = find_sheet(workbook, SUPPLEMENT_SHEET_KEYWORD)

    context = extract_from_commission_sheet(commission_ws)
    supplement_context, _ = read_key_value_sheet(supplement_ws)
    key_order = list(REPORT_FIELD_ORDER)

    # 自动抽取结果优先；如果旧委托单仍带有“所需要信息”sheet，只把它作为可选补充值。
    for key, value in supplement_context.items():
        if not has_value(context.get(key)):
            context[key] = value

    for key in key_order:
        context.setdefault(key, "")

    for key in context:
        if key not in key_order:
            key_order.append(key)

    context["生成时间"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if "生成时间" not in key_order:
        key_order.append("生成时间")

    return context, key_order, commission_ws.title, supplement_ws.title if supplement_ws else ""


def build_initial_context(data_file):
    if data_file.name.lower().endswith(".csv"):
        context, key_order = read_csv_context(data_file)
        return context, key_order, "CSV", ""

    return build_context_from_excel(data_file)


def context_to_editor_rows(context, template_vars, key_order):
    keys = []
    for key in key_order:
        if key not in keys:
            keys.append(key)

    for key in template_vars:
        if key not in keys:
            keys.append(key)

    for key in context:
        if key not in keys:
            keys.append(key)

    return pd.DataFrame(
        [
            {
                "序号": index,
                "字段": key,
                "内容": "、".join(context[key]) if isinstance(context.get(key), list) else clean_text(context.get(key)),
            }
            for index, key in enumerate(keys, start=1)
        ]
    )


def editor_rows_to_context(df):
    context = {}
    for _, row in df.iterrows():
        key = clean_text(row.get("字段"))
        if key:
            context[key] = clean_text(row.get("内容"))
    return context


def uploaded_file_signature(*files):
    parts = []
    for file in files:
        if file is None:
            parts.append(("none", 0))
            continue
        parts.append((file.name, getattr(file, "size", 0)))
    return tuple(parts)


def ensure_editor_cache(context, template_vars, key_order, data_signature):
    """同一份上传文件只初始化一次表格，避免编辑内容被 Streamlit 重跑覆盖。"""
    if st.session_state.get("data_signature") != data_signature:
        st.session_state["data_signature"] = data_signature
        st.session_state.pop("context_editor", None)
        st.session_state["editor_df"] = context_to_editor_rows(context, template_vars, key_order)

    if "editor_df" not in st.session_state:
        st.session_state["editor_df"] = context_to_editor_rows(context, template_vars, key_order)

    return st.session_state["editor_df"]


def update_editor_value(field, value):
    if "editor_df" not in st.session_state:
        return

    df = st.session_state["editor_df"].copy()
    mask = df["字段"] == field
    if mask.any():
        df.loc[mask, "内容"] = clean_text(value)
    else:
        df.loc[len(df)] = {
            "序号": len(df) + 1,
            "字段": field,
            "内容": clean_text(value),
        }
    st.session_state["editor_df"] = df


def split_people(value):
    text = clean_text(value)
    if not text:
        return []
    return [item.strip() for item in re.split(r"[、,，;；\s]+", text) if item.strip()]


def parse_date_for_input(value):
    text = clean_text(value)
    if not text:
        return None

    match = re.search(r"(\d{4})\D?(\d{1,2})\D?(\d{1,2})", text)
    if not match:
        return None

    year, month, day = match.groups()
    try:
        return datetime.date(int(year), int(month), int(day))
    except ValueError:
        return None


def parse_date_range_for_input(value):
    text = clean_text(value)
    if not text:
        return None

    matches = re.findall(r"(\d{4})\D?(\d{1,2})\D?(\d{1,2})", text)
    if not matches:
        return None

    dates = []
    for year, month, day in matches[:2]:
        try:
            dates.append(datetime.date(int(year), int(month), int(day)))
        except ValueError:
            return None

    if len(dates) == 1:
        dates.append(dates[0])
    return tuple(dates)


def format_date_value(value):
    if isinstance(value, tuple):
        if len(value) == 2:
            start, end = value
            if start and end:
                return f"{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}"
        return ""

    if isinstance(value, list):
        return format_date_value(tuple(value))

    if isinstance(value, datetime.datetime):
        return value.strftime("%Y%m%d")

    if isinstance(value, datetime.date):
        return value.strftime("%Y%m%d")

    return clean_text(value)


def current_context_from_editor():
    return editor_rows_to_context(st.session_state.get("editor_df", pd.DataFrame(columns=["字段", "内容"])))


# ============================
# 图片处理
# ============================
def make_a4_landscape_image(image_files):
    """多图合成为适配 A4 横向页面的图片，优先横向排布，放不下再换行。"""
    images = [Image.open(img).convert("RGB") for img in image_files]
    if not images:
        return None

    max_w = LANDSCAPE_CANVAS_WIDTH_PX - CANVAS_PADDING_PX * 2
    max_h = LANDSCAPE_CANVAS_HEIGHT_PX - CANVAS_PADDING_PX * 2

    best_layout = None
    max_cols = min(len(images), 6)
    for cols in range(max_cols, 0, -1):
        rows = (len(images) + cols - 1) // cols
        cell_w = (max_w - COL_GAP_PX * (cols - 1)) / cols
        cell_h = (max_h - ROW_GAP_PX * (rows - 1)) / rows
        scale = min(
            min(cell_w / img.width, cell_h / img.height)
            for img in images
        )
        score = scale * (1 + cols * 0.05)
        if best_layout is None or score > best_layout["score"]:
            best_layout = {
                "cols": cols,
                "rows": rows,
                "cell_w": cell_w,
                "cell_h": cell_h,
                "scale": scale,
                "score": score,
            }

    cols = best_layout["cols"]
    rows = best_layout["rows"]
    cell_w = best_layout["cell_w"]
    cell_h = best_layout["cell_h"]
    scale = best_layout["scale"]

    resized = [
        img.resize(
            (max(1, int(img.width * scale)), max(1, int(img.height * scale))),
            Image.LANCZOS,
        )
        for img in images
    ]

    canvas = Image.new("RGB", (LANDSCAPE_CANVAS_WIDTH_PX, LANDSCAPE_CANVAS_HEIGHT_PX), BG_COLOR)
    grid_w = cols * cell_w + (cols - 1) * COL_GAP_PX
    grid_h = rows * cell_h + (rows - 1) * ROW_GAP_PX
    start_x = int((LANDSCAPE_CANVAS_WIDTH_PX - grid_w) / 2)
    start_y = int((LANDSCAPE_CANVAS_HEIGHT_PX - grid_h) / 2)

    for index, img in enumerate(resized):
        row = index // cols
        col = index % cols
        cell_x = start_x + int(col * (cell_w + COL_GAP_PX))
        cell_y = start_y + int(row * (cell_h + ROW_GAP_PX))
        x = cell_x + int((cell_w - img.width) / 2)
        y = cell_y + int((cell_h - img.height) / 2)
        canvas.paste(img, (x, y))

    out = BytesIO()
    canvas.save(out, format="JPEG", quality=95)
    out.seek(0)
    return out


def split_image_names(value, image_map):
    if isinstance(value, list):
        names = [clean_text(item) for item in value]
    else:
        text = clean_text(value)
        if not text:
            return []
        names = [item.strip() for item in re.split(r"[、,，;；\n]+", text) if item.strip()]

    return [name for name in names if name in image_map]


def render_images_in_context(context, tpl, image_files):
    image_map = {img.name: img for img in image_files} if image_files else {}

    for key, value in list(context.items()):
        image_names = split_image_names(value, image_map)
        if not image_names:
            if key in OPTIONAL_IMAGE_FIELDS:
                context[key] = f"{DELETE_PARAGRAPH_MARKER}{key}"
            continue

        images = []
        for name in image_names:
            image_map[name].seek(0)
            images.append(image_map[name])

        merged_img = make_a4_landscape_image(images)
        if merged_img is not None:
            context[key] = InlineImage(tpl, merged_img, width=Mm(LANDSCAPE_IMG_WIDTH_MM))

    return context


def remove_marked_paragraphs(doc, marker=DELETE_PARAGRAPH_MARKER):
    paragraphs = list(doc.paragraphs)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                paragraphs.extend(cell.paragraphs)

    removed_count = 0
    for paragraph in paragraphs:
        if marker in paragraph.text:
            element = paragraph._element
            parent = element.getparent()
            if parent is not None:
                parent.remove(element)
                removed_count += 1

    return removed_count


# ============================
# 上传文件
# ============================
tpl_file = st.file_uploader("上传 Word 报告模板（.docx）", type=["docx"])
data_file = st.file_uploader("上传试验委托单（只需要填写页，.xlsx）", type=["xlsx"])
img_files = st.file_uploader(
    "上传报告图片（可多选，文件名需与字段内容一致）",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True,
)


if tpl_file and data_file:
    try:
        tpl_file.seek(0)
        tpl = DocxTemplate(tpl_file)
        template_vars = sorted(tpl.get_undeclared_template_variables())

        context, key_order, commission_sheet_name, supplement_sheet_name = build_initial_context(data_file)
        for key in template_vars:
            context.setdefault(key, "")

        st.success(f"已从“{commission_sheet_name}”自动抽取委托单信息。")
        if supplement_sheet_name:
            st.caption(f"“{supplement_sheet_name}”仅作为补充来源，自动抽取不到的字段才会读取它。")

        data_signature = uploaded_file_signature(tpl_file, data_file)
        editor_df = ensure_editor_cache(context, template_vars, key_order, data_signature)

        extracted_fields = [
            *AUTO_FROM_COMMISSION_FIELDS,
            "产品尺寸",
            "技术状态",
            "生产单位",
            "送样方式",
            "贮存要求",
            "报告结论形式",
            "报告提交方式",
            "样品性能测试",
            "产品处置方式",
            "联系人",
            "联系电话",
            "试验条件",
            "特殊要求",
        ]
        extracted_preview = editor_df[editor_df["字段"].isin(extracted_fields)]
        with st.expander("从委托单自动带入的信息", expanded=False):
            st.dataframe(extracted_preview, hide_index=True, use_container_width=True)

        with st.expander("按填写要求补充信息", expanded=True):
            tabs = st.tabs(["基本信息", "填写", "曲线名称"])

            with tabs[0]:
                st.subheader("日期")
                date_context = current_context_from_editor()
                range_cols = st.columns(2)
                for field in DATE_RANGE_FIELDS:
                    current_range = parse_date_range_for_input(date_context.get(field))
                    start_current = current_range[0] if current_range else None
                    end_current = current_range[1] if current_range else None
                    start_date = range_cols[0].date_input(
                        f"{field}开始",
                        value=start_current,
                        format="YYYY-MM-DD",
                        key=f"date_start_{field}",
                    )
                    end_date = range_cols[1].date_input(
                        f"{field}结束",
                        value=end_current,
                        format="YYYY-MM-DD",
                        key=f"date_end_{field}",
                    )
                    update_editor_value(field, format_date_value((start_date, end_date)))

                single_cols = st.columns(3)
                for index, field in enumerate(DATE_FIELDS):
                    current = parse_date_for_input(date_context.get(field))
                    selected_date = single_cols[index % 3].date_input(
                        field,
                        value=current,
                        format="YYYY-MM-DD",
                        key=f"date_{field}",
                    )
                    update_editor_value(field, format_date_value(selected_date))

                st.subheader("选择")
                option_context = current_context_from_editor()
                option_cols = st.columns(3)
                for index, (field, options) in enumerate(SELECT_FIELD_OPTIONS.items()):
                    current = clean_text(option_context.get(field))
                    option_list = list(options)
                    if current and current not in option_list:
                        option_list.insert(0, current)
                    selected = option_cols[index % 3].selectbox(
                        field,
                        options=option_list,
                        index=option_list.index(current) if current in option_list else 0,
                        key=f"select_{field}",
                    )
                    update_editor_value(field, selected)

                st.subheader("设备选择")
                device_context = current_context_from_editor()
                current_device = "KM3L"
                flow_name = clean_text(device_context.get("流程控制软件"))
                for device in DEVICE_VERSION_OPTIONS:
                    if flow_name.startswith(device):
                        current_device = device
                        break

                device = st.selectbox(
                    "设备",
                    options=list(DEVICE_VERSION_OPTIONS.keys()),
                    index=list(DEVICE_VERSION_OPTIONS.keys()).index(current_device),
                    key="select_device_version",
                )
                for field, value in DEVICE_VERSION_OPTIONS[device].items():
                    update_editor_value(field, value)

                device_df = pd.DataFrame(
                    [
                        {"字段": field, "内容": value}
                        for field, value in DEVICE_VERSION_OPTIONS[device].items()
                    ]
                )
                st.dataframe(device_df, hide_index=True, use_container_width=True)

                st.subheader("人员")
                people_context = current_context_from_editor()
                leader_current = clean_text(people_context.get("试验技术负责人"))
                leader_options = list(PERSONNEL_OPTIONS)
                if leader_current and leader_current not in leader_options:
                    leader_options.insert(0, leader_current)
                leader = st.selectbox(
                    "试验技术负责人",
                    options=leader_options,
                    index=leader_options.index(leader_current) if leader_current in leader_options else 0,
                    key="select_试验技术负责人",
                )
                update_editor_value("试验技术负责人", leader)

                participant_current = split_people(people_context.get("试验参加者"))
                participant_options = list(PERSONNEL_OPTIONS)
                for name in participant_current:
                    if name not in participant_options:
                        participant_options.insert(0, name)
                participants = st.multiselect(
                    "试验参加者",
                    options=participant_options,
                    default=[name for name in participant_current if name in participant_options],
                    key="multi_试验参加者",
                )
                update_editor_value("试验参加者", "、".join(participants))

            with tabs[1]:
                text_context = current_context_from_editor()
                text_cols = st.columns(3)
                for index, field in enumerate(MANUAL_TEXT_FIELDS):
                    current = clean_text(text_context.get(field))
                    value = text_cols[index % 3].text_area(
                        field,
                        value=current,
                        height=90 if field in ["试验目的", "试验过程"] else 68,
                        key=f"text_{field}",
                    )
                    update_editor_value(field, value)

            with tabs[2]:
                name_context = current_context_from_editor()
                name_cols = st.columns(4)
                for index, field in enumerate(NAME_TEXT_FIELDS):
                    current = clean_text(name_context.get(field))
                    value = name_cols[index % 4].text_input(
                        field,
                        value=current,
                        key=f"name_{field}",
                    )
                    update_editor_value(field, value)

        editor_df = st.session_state["editor_df"]
        edited_df = st.data_editor(
            editor_df,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            disabled=["序号", "字段"],
            column_config={
                "序号": st.column_config.NumberColumn("序号", width="small"),
                "字段": st.column_config.TextColumn("字段", width="medium"),
                "内容": st.column_config.TextColumn("内容", width="large"),
            },
            key="context_editor",
        )
        st.session_state["editor_df"] = edited_df

        edited_context = editor_rows_to_context(edited_df)
        missing_keys = [
            key
            for key in template_vars
            if not has_value(edited_context.get(key))
            and not key.startswith("试验温度曲线")
            and key != "真空度曲线"
        ]
        if missing_keys:
            st.warning("以下模板字段还没有内容：" + "、".join(missing_keys))

        if st.button("生成报告", type="primary"):
            tpl_file.seek(0)
            tpl = DocxTemplate(tpl_file)
            render_context = render_images_in_context(edited_context, tpl, img_files)

            tpl.render(render_context)

            out_buf = BytesIO()
            tpl.save(out_buf)
            out_buf.seek(0)

            doc = Document(out_buf)
            removed_positions = remove_marked_paragraphs(doc)
            out_buf = BytesIO()
            doc.save(out_buf)
            out_buf.seek(0)

            if removed_positions:
                st.success(f"报告生成成功，已删除 {removed_positions} 个空曲线位置。")
            else:
                st.success("报告生成成功。")
            st.download_button(
                "下载报告",
                data=out_buf,
                file_name=f"试验报告_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

    except Exception as e:
        st.error(f"生成失败：{e}")
