import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from io import BytesIO
import datetime
from PIL import Image

st.set_page_config(page_title="试验报告自动生成", layout="wide")
st.title("📑 试验报告自动生成")

# ============================
# Word 中图片尺寸（毫米）
# ============================
IMG_WIDTH_MM = 230
IMG_HEIGHT_MM = None   # None = 保持比例

# ============================
# 合成参数（像素）
# ============================
MAX_ROW_WIDTH_PX = 3000
ROW_GAP_PX = 20
BG_COLOR = (255, 255, 255)

# ============================
# 上传文件
# ============================
tpl_file = st.file_uploader("上传 Word 模板（.docx）", type=["docx"])
data_file = st.file_uploader("上传 Excel 数据文件", type=["xlsx", "csv"])
img_files = st.file_uploader(
    "上传图片文件（可多选）",
    type=["jpg", "jpeg", "png","PNG"],
    accept_multiple_files=True
)

# ============================
# 🧩 自
# ============================
def merge_images_auto_wrap(image_files):
    """
    多图自动换行合成
    """
    images = [Image.open(img).convert("RGB") for img in image_files]

    # 统一高度（取最小，避免放大）
    base_height = min(img.height for img in images)

    resized = []
    for img in images:
        ratio = base_height / img.height
        resized.append(img.resize((int(img.width * ratio), base_height)))

    # 分行
    rows = []
    current_row = []
    current_width = 0

    for img in resized:
        if current_width + img.width <= MAX_ROW_WIDTH_PX:
            current_row.append(img)
            current_width += img.width
        else:
            rows.append(current_row)
            current_row = [img]
            current_width = img.width

    if current_row:
        rows.append(current_row)

    # 计算画布尺寸
    total_height = sum(
        max(img.height for img in row) for row in rows
    ) + ROW_GAP_PX * (len(rows) - 1)

    total_width = max(
        sum(img.width for img in row) for row in rows
    )

    canvas = Image.new("RGB", (total_width, total_height), BG_COLOR)

    # 粘贴
    y_offset = 0
    for row in rows:
        x_offset = 0
        row_height = max(img.height for img in row)

        for img in row:
            canvas.paste(img, (x_offset, y_offset))
            x_offset += img.width

        y_offset += row_height + ROW_GAP_PX

    out = BytesIO()
    canvas.save(out, format="JPEG", quality=95)
    out.seek(0)
    return out


if tpl_file and data_file:
    try:
        # ============================
        # 1. Word 模板
        # ============================
        tpl = DocxTemplate(tpl_file)

        # ============================
        # 2. Excel 读取（一行多图）
        # ============================
        if data_file.name.endswith(".csv"):
            df = pd.read_csv(data_file, header=None)
        else:
            df = pd.read_excel(data_file, sheet_name="所需要信息（此页无需填写）", header=None)

        context = {}

        for i in range(len(df)):
            key = str(df.iloc[i, 0]).strip()
            values = df.iloc[i, 1:].dropna().astype(str).tolist()

            if not values:
                context[key] = ""
            elif len(values) == 1:
                context[key] = values[0]
            else:
                context[key] = values

        context["生成时间"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ============================
        # 3. 图片映射
        # ============================
        image_map = {img.name: img for img in img_files} if img_files else {}

        # ============================
        # 4. 图片处理
        # ============================
        for key, val in context.items():

            # 单图
            if isinstance(val, str) and val in image_map:
                context[key] = InlineImage(
                    tpl,
                    image_map[val],
                    width=Mm(IMG_WIDTH_MM)
                )

            # 多图 → 自动换行合成
            elif isinstance(val, list):
                imgs = [image_map[name] for name in val if name in image_map]

                if imgs:
                    merged_img = merge_images_auto_wrap(imgs)

                    context[key] = InlineImage(
                        tpl,
                        merged_img,
                        width=Mm(IMG_WIDTH_MM)
                    )

        # ============================
        # 5. 渲染 Word
        # ============================
        tpl.render(context)

        out_buf = BytesIO()
        tpl.save(out_buf)
        out_buf.seek(0)

        st.success("✅ 报告生成成功（超宽自动换行合成）")

        st.download_button(
            "⬇️ 下载报告",
            data=out_buf,
            file_name=f"试验报告_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    except Exception as e:
        st.error(f"生成失败: {e}")
