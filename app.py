import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import io
import numpy as np
import os
import zipfile

# 页面标题
st.title('希望将省下来的时间用来与你共度，共享这段珍贵的时光。')

# 创建页面导航栏
page = st.sidebar.radio("选择功能", ("结果出图", "高温转低温", "低温转高温"))

# 第一功能区：CSV文件合并与提取信息
if page == "结果出图":
    st.header("CSV文件合并与作图")

    uploaded_files = st.file_uploader("选择多个CSV文件进行合并", accept_multiple_files=True, type=["csv"])

    if uploaded_files:
        grouped_dataframes = {}

        for uploaded_file in uploaded_files:
            df = pd.read_csv(uploaded_file, encoding="GB2312")

            base_name = uploaded_file.name
            group_key = base_name.rstrip('.csv')[-1]

            if group_key not in grouped_dataframes:
                grouped_dataframes[group_key] = []

            grouped_dataframes[group_key].append(df)

        merged_dfs = {}
        for key, df_list in grouped_dataframes.items():
            merged_df = pd.concat(df_list, ignore_index=True)
            merged_dfs[key] = merged_df

        final_df = pd.DataFrame()

        for key, df in merged_dfs.items():
            if final_df.empty:
                final_df = df
            else:
                final_df = pd.merge(final_df, df, on='时间', how='outer', suffixes=('', f'_{key}'))

        st.success("CSV文件已成功合并。")

        # 用户自定义保存路径
        save_path = st.text_input("输入合并后的CSV文件保存路径", value="合并文件.csv")

        merged_csv = io.BytesIO()
        final_df.to_csv(merged_csv, index=False, encoding="GB2312")
        merged_csv.seek(0)

        st.download_button(
            label="下载合并后的CSV文件",
            data=merged_csv,
            file_name=os.path.basename(save_path),
            mime="text/csv"
        )

        config_files = st.file_uploader("上传多个提取信息的配置文件", accept_multiple_files=True, type=["csv"])

        if config_files:
            combined_config_df = pd.DataFrame()

            for config_file in config_files:
                temp_df = pd.read_csv(config_file, encoding="GB2312")
                combined_config_df = pd.concat([combined_config_df, temp_df], ignore_index=True)

            combined_config_df["采样类型"] = combined_config_df["采样类型"].str.replace("黑温", "黑片")
            combined_config_df["提取信息"] = "电源" + combined_config_df["对应电源号"].map(str) + combined_config_df[
                "采样类型"] + "温度"
            new_row = {"提取信息": "时间"}
            combined_config_df = pd.concat([pd.DataFrame(new_row, index=[1]), combined_config_df], ignore_index=True)

            st.success("提取信息配置文件已成功处理。")

            columns_to_extract = combined_config_df['提取信息'].tolist()

            extracted_df = final_df[columns_to_extract]

            extracted_df['时间'] = pd.to_datetime(extracted_df['时间'], errors='coerce')
            extracted_df['时间'] = extracted_df['时间'].dt.strftime('%Y-%m-%d %H:%M:%S')
            extracted_df['时间'] = pd.to_datetime(extracted_df['时间'])
            extracted_df.set_index('时间', inplace=True)

            extracted_csv = io.BytesIO()
            extracted_df.to_csv(extracted_csv, index=True, encoding="GB2312")
            extracted_csv.seek(0)

            save_extracted_path = st.text_input("输入提取信息的CSV文件保存路径", value="信息提取结果.csv")

            st.download_button(
                label="下载提取信息的CSV文件",
                data=extracted_csv,
                file_name=os.path.basename(save_extracted_path),
                mime="text/csv"
            )

            selected_columns = st.multiselect("选择要绘制的列", extracted_df.columns[0:])

            if selected_columns:
                st.write(f"正在生成选中列的折线图...")

                min_time = extracted_df.index.min()
                max_time = extracted_df.index.max()

                start_date = st.date_input("选择开始日期", min_value=min_time.date(), max_value=max_time.date(),
                                           value=min_time.date())
                start_time = st.time_input("选择开始时间", value=min_time.time())
                start_datetime = pd.Timestamp.combine(start_date, start_time)

                end_date = st.date_input("选择结束日期", min_value=min_time.date(), max_value=max_time.date(),
                                         value=max_time.date())
                end_time = st.time_input("选择结束时间", value=max_time.time())
                end_datetime = pd.Timestamp.combine(end_date, end_time)

                if start_datetime > end_datetime:
                    st.error("开始时间不能晚于结束时间。")
                else:
                    filtered_df = extracted_df.loc[start_datetime:end_datetime]

                    line_width = st.slider("选择折线宽度", min_value=1, max_value=10, value=4)
                    marker_size = st.slider("选择标记大小", min_value=1, max_value=20, value=1)
                    axis_font_size = st.slider("选择坐标轴标注字体大小", min_value=10, max_value=30, value=20)
                    legend_font_size = st.slider("选择图例标注字体大小", min_value=10, max_value=30, value=20)

                    # Y轴范围输入
                    y_axis_min = st.text_input("输入Y轴最小值", value=str(filtered_df[selected_columns].min().min()))
                    y_axis_max = st.text_input("输入Y轴最大值", value=str(filtered_df[selected_columns].max().max()))

                    try:
                        y_axis_range = (float(y_axis_min), float(y_axis_max))
                    except ValueError:
                        st.error("请输入有效的Y轴范围。")
                        y_axis_range = (filtered_df[selected_columns].min().min(), filtered_df[selected_columns].max().max())

                    title_text = st.text_input("输入图像标题", value="数据折线图")
                    title_font_size = st.slider("选择标题字体大小", min_value=10, max_value=50, value=25)

                    # 图例内容修改
                    legend_names = st.text_input("输入图例内容（用逗号分隔）", value=",".join(selected_columns))
                    legend_names_list = [name.strip() for name in legend_names.split(",")]

                    num_ticks = 60
                    x_values = np.linspace(0, len(filtered_df) - 1, num_ticks, dtype=int)
                    x_labels = filtered_df.index[x_values].strftime('%Y-%m-%d %H:%M:%S')

                    fig = go.Figure()

                    for column, legend_name in zip(selected_columns, legend_names_list):
                        fig.add_trace(go.Scatter(
                            x=filtered_df.index,
                            y=filtered_df[column],
                            mode='lines+markers',
                            name=legend_name,
                            line=dict(width=line_width),
                            marker=dict(size=marker_size)
                        ))

                    fig.update_layout(
                        title=dict(
                            text=title_text,
                            font=dict(size=title_font_size),
                            x=0.5,  # 将标题居中
                            xanchor='center',
                            y = 0.94
                    ),
                        xaxis_title='',
                        yaxis_title='',
                        xaxis_rangeslider_visible=False,
                        xaxis=dict(
                            tickvals=filtered_df.index[x_values],
                            ticktext=x_labels,
                            tickfont=dict(
                                size=axis_font_size,
                                family="Times New Roman",
                                color='#000000'
                            ),
                            tickformat='%Y-%m-%d %H:%M:%S',
                            titlefont=dict(
                                size=axis_font_size,
                                family="Times New Roman",
                                color='#000000'
                            ),
                            showgrid=False,  # 隐藏横坐标网格线
                        ),
                        yaxis=dict(
                            range=y_axis_range,
                            tickfont=dict(
                                size=axis_font_size,
                                family="Times New Roman",
                                color='#000000'
                            ),
                            titlefont=dict(
                                size=axis_font_size,
                                family="Times New Roman",
                                color='#000000'
                            ),
                            showgrid=True,  # 显示纵坐标网格线
                            gridwidth=1,
                            gridcolor='LightGray'
                        ),
                        legend=dict(
                            orientation="v",  # 垂直方向排列
                            yanchor="middle",  # y 轴锚定到中间
                            y=0.5,  # y 坐标为 0.5 (垂直居中)
                            xanchor="left",  # x 轴锚定到左边
                            x=1.02,
                            font=dict(
                                size=legend_font_size
                            )
                        ),
                        margin=dict(l=100, r=150, t=100, b=100),  # 外边距，增加顶部边距用于标题
                        plot_bgcolor='rgba(255, 255, 255, 1)',  # 背景颜色设置为白色
                        paper_bgcolor='rgba(255, 255, 255, 1)',  # 设置为黑色
                        width=800,  # 图表宽度
                        height=500  # 图表高度
                    )

                    st.plotly_chart(fig, use_container_width=True)



# 第二功能区：高转低
if page == "高温转低温":
    st.header("高温转低温工具")

    uploaded_file = st.file_uploader("上传CSV文件", type="csv")
    column_name = st.text_input("输入要处理的列名", value="")
    save_path_prefix = st.text_input("输入生成文件的路径前缀", value="处理结果")
    decrement_value = st.number_input("设置每次减少的量", min_value=0.01, value=0.1, step=0.01)

    if st.button("开始处理"):
        if uploaded_file is None or not column_name:
            st.error("请上传文件并输入列名。")
        else:
            df = pd.read_csv(uploaded_file, encoding="GB2312")
            file_counter = 2
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zf:
                if column_name not in df.columns:
                    st.error(f"列 '{column_name}' 不存在于文件中")
                else:
                    while df[column_name].max() > 0:
                        df[column_name] = df[column_name].apply(
                            lambda x: max(0, x - decrement_value) if pd.notna(x) else x)
                        csv_buffer = io.BytesIO()
                        df.to_csv(csv_buffer, index=False, encoding="GB2312")
                        csv_buffer.seek(0)
                        new_file_name = f"{save_path_prefix}{file_counter}.csv"
                        zf.writestr(new_file_name, csv_buffer.getvalue())
                        file_counter += 1

            zip_buffer.seek(0)
            st.download_button(
                label="下载所有文件的ZIP压缩包",
                data=zip_buffer,
                file_name=f"{save_path_prefix}_all_files.zip",
                mime="application/zip"
            )

# 第三功能区：标准文件与替换文件生成
if page == "低温转高温":
    st.header("低温转高温")

    standard_file = st.file_uploader("上传标准CSV文件", type="csv", key="standard")
    replace_file = st.file_uploader("上传替换CSV文件", type="csv", key="replace")
    save_path_prefix = st.text_input("输入生成文件的路径前缀", value="处理结果")

    if st.button("开始生成"):
        if standard_file is None or replace_file is None:
            st.error("请上传标准文件和替换文件。")
        else:
            standard_df = pd.read_csv(standard_file, encoding="GB2312")
            replace_df = pd.read_csv(replace_file, encoding="GB2312")

            file_counter = 1
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zf:
                for index, replace_row in replace_df.iterrows():
                    modified_df = standard_df.copy()

                    modified_df.loc[modified_df['控温温度'].notna(), '控温温度'] = replace_row.iloc[0]
                    modified_df['限流值'] = replace_row.iloc[1]

                    csv_buffer = io.BytesIO()
                    modified_df.to_csv(csv_buffer, index=False, encoding="GB2312")
                    csv_buffer.seek(0)
                    new_file_name = f"{save_path_prefix}{file_counter}.csv"
                    zf.writestr(new_file_name, csv_buffer.getvalue())
                    file_counter += 1

            zip_buffer.seek(0)
            st.download_button(
                label="下载所有文件的ZIP压缩包",
                data=zip_buffer,
                file_name=f"{save_path_prefix}_all_files.zip",
                mime="application/zip"
            )
