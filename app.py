import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import io
import numpy  as np

# Streamlit 页面标题
st.title('CSV文件合并与提取信息工具')

# 上传需要合并的CSV文件
uploaded_files = st.file_uploader("选择多个CSV文件进行合并", accept_multiple_files=True, type=["csv"])

if uploaded_files:
    grouped_dataframes = {}

    for uploaded_file in uploaded_files:
        df = pd.read_csv(uploaded_file, encoding="GB2312")

        # 获取文件名，提取分组的关键字
        base_name = uploaded_file.name
        group_key = base_name.rstrip('.csv')[-1]

        if group_key not in grouped_dataframes:
            grouped_dataframes[group_key] = []

        grouped_dataframes[group_key].append(df)

    # 合并每组文件
    merged_dfs = {}
    for key, df_list in grouped_dataframes.items():
        merged_df = pd.concat(df_list, ignore_index=True)
        merged_dfs[key] = merged_df

    # 按时间列相同的行合并成一个文件
    final_df = pd.DataFrame()

    for key, df in merged_dfs.items():
        if final_df.empty:
            final_df = df
        else:
            final_df = pd.merge(final_df, df, on='时间', how='outer', suffixes=('', f'_{key}'))

    # 提示合并完成
    st.success("CSV文件已成功合并。")

    # 将合并的 DataFrame 保存到内存中的二进制流
    merged_csv = io.BytesIO()
    final_df.to_csv(merged_csv, index=False, encoding="GB2312")
    merged_csv.seek(0)

    # 提供下载链接
    st.download_button(
        label="下载合并后的CSV文件",
        data=merged_csv,
        file_name="合并文件.csv",
        mime="text/csv"
    )

    # 上传提取信息的配置文件
    config_files = st.file_uploader("上传多个提取信息的配置文件", accept_multiple_files=True, type=["csv"])

    if config_files:
        # 合并所有配置文件
        combined_config_df = pd.DataFrame()

        for config_file in config_files:
            temp_df = pd.read_csv(config_file, encoding="GB2312")
            combined_config_df = pd.concat([combined_config_df, temp_df], ignore_index=True)

        combined_config_df["采样类型"] = combined_config_df["采样类型"].str.replace("黑温", "黑片")
        combined_config_df["提取信息"] = "电源" + combined_config_df["对应电源号"].map(str) + combined_config_df[
            "采样类型"] + "温度"
        new_row = {"提取信息": "时间"}
        combined_config_df = pd.concat([pd.DataFrame(new_row, index=[1]), combined_config_df], ignore_index=True)

        # 提取信息配置完成提示
        st.success("提取信息配置文件已成功处理。")

        # 读取配置文件
        columns_to_extract = combined_config_df['提取信息'].tolist()

        # 从合并的 DataFrame 中提取指定的列
        extracted_df = final_df[columns_to_extract]

        # 确保时间列为 datetime 格式，并格式化为所需的字符串格式
        extracted_df['时间'] = pd.to_datetime(extracted_df['时间'], errors='coerce')
        extracted_df['时间'] = extracted_df['时间'].dt.strftime('%Y-%m-%d %H:%M:%S')
        extracted_df['时间'] = pd.to_datetime(extracted_df['时间'])
        extracted_df.set_index('时间', inplace=True)

        # 将提取结果保存到内存中的二进制流
        extracted_csv = io.BytesIO()
        extracted_df.to_csv(extracted_csv, index=True, encoding="GB2312")
        extracted_csv.seek(0)

        # 提供下载链接
        st.download_button(
            label="下载提取信息的CSV文件",
            data=extracted_csv,
            file_name="信息提取结果.csv",
            mime="text/csv"
        )

        # 用户选择要绘制的多列
        selected_columns = st.multiselect("选择要绘制的列", extracted_df.columns[1:])

        if selected_columns:
            st.write(f"正在生成选中列的折线图...")

            # 用户选择时间范围
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

            # 确保选择的时间范围有效
            if start_datetime > end_datetime:
                st.error("开始时间不能晚于结束时间。")
            else:
                # 筛选数据范围
                filtered_df = extracted_df.loc[start_datetime:end_datetime]

                # 图表样式设置
                line_width = st.slider("选择折线宽度", min_value=1, max_value=10, value=4)
                marker_size = st.slider("选择标记大小", min_value=1, max_value=20, value=1)
                axis_font_size = st.slider("选择坐标轴标注字体大小", min_value=10, max_value=30, value=20)
                legend_font_size = st.slider("选择图例标注字体大小", min_value=10, max_value=30, value=20)

                # 生成横坐标刻度值和标签
                num_ticks = 60
                x_values = np.linspace(0, len(filtered_df) - 1, num_ticks, dtype=int)
                x_labels = filtered_df.index[x_values].strftime('%Y-%m-%d %H:%M:%S')

                # 生成折线图
                fig = go.Figure()

                for column in selected_columns:
                    fig.add_trace(go.Scatter(
                        x=filtered_df.index,
                        y=filtered_df[column],
                        mode='lines+markers',
                        name=column,
                        line=dict(width=line_width),
                        marker=dict(size=marker_size)
                    ))

                fig.update_layout(
                    title=' ',
                    xaxis_title='时间',
                    yaxis_title='值',
                    xaxis_rangeslider_visible=True,
                    xaxis=dict(
                        tickvals=filtered_df.index[x_values],
                        ticktext=x_labels,
                        tickfont=dict(size=axis_font_size, family="Times New Roman", color='#000000'),
                        tickformat='%Y-%m-%d %H:%M:%S'
                        titlefont=dict(size=axis_font_size, family="Times New Roman", color='#000000')
                    ),
                    yaxis=dict(
                        tickfont=dict(size=axis_font_size,family="Times New Roman", color='#000000')
                        titlefont=dict(size=axis_font_size, family="Times New Roman", color='#000000')
                    ),
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="center",
                        x=0.5,
                        font=dict(size=legend_font_size),
                        title_text=''  # 移除图例标题
                    )
                )

                st.plotly_chart(fig, use_container_width=True)
