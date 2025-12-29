# 导入必备库
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from dateutil.parser import parse
from plyer import notification  # 桌面弹窗提醒（Windows）
import os

# -------------------------- 第一步：设置工具页面基础配置 --------------------------
st.set_page_config(
    page_title="校园课程表智能提醒工具",  # 页面标题
    page_icon="📚",  # 页面图标（可自定义）
    layout="wide"  # 宽屏显示
)

# 页面标题和说明
st.title("📚 校园课程表智能提醒工具")
st.subheader("解决课程遗忘、迟到问题，提升校园学习效率")
st.divider()  # 分割线

# -------------------------- 第二步：初始化用户课程表（避免首次使用报错） --------------------------
# 若会话中没有课程表，初始化一个空的DataFrame
if 'course_df' not in st.session_state:
    # 定义课程表列名：课程名称、星期、开始时间、结束时间、教室、提醒时间（分钟）
    cols = ['课程名称', '星期', '开始时间', '结束时间', '教室', '课前提醒（分钟）']
    st.session_state.course_df = pd.DataFrame(columns=cols)

# -------------------------- 第三步：实现课程添加功能（手动添加，核心功能1） --------------------------
st.sidebar.title("📝 课程管理")
st.sidebar.subheader("添加新课程")

# 侧边栏输入表单
course_name = st.sidebar.text_input("课程名称", placeholder="如：高等数学")
weekday = st.sidebar.selectbox("星期", options=['周一', '周二', '周三', '周四', '周五', '周六', '周日'])
start_time = st.sidebar.time_input("开始时间")
end_time = st.sidebar.time_input("结束时间")
classroom = st.sidebar.text_input("教室", placeholder="如：教学楼A201")
remind_minutes = st.sidebar.number_input("课前提醒分钟数", min_value=0, max_value=60, value=15)

# 转换时间格式（方便后续计算）
start_time_str = start_time.strftime("%H:%M")
end_time_str = end_time.strftime("%H:%M")

# 添加课程按钮
if st.sidebar.button("✅ 添加课程"):
    # 验证必填项是否为空
    if not course_name or not classroom:
        st.sidebar.warning("课程名称和教室不能为空！")
    else:
        # 新建一行课程数据
        new_course = pd.DataFrame({
            '课程名称': [course_name],
            '星期': [weekday],
            '开始时间': [start_time_str],
            '结束时间': [end_time_str],
            '教室': [classroom],
            '课前提醒（分钟）': [remind_minutes]
        })
        # 将新课程添加到会话中的课程表
        st.session_state.course_df = pd.concat([st.session_state.course_df, new_course], ignore_index=True)
        st.sidebar.success(f"✅ 成功添加课程：{course_name}")

# -------------------------- 第四步：实现课程导入功能（可选，批量添加） --------------------------
st.sidebar.divider()
st.sidebar.subheader("批量导入课程（Excel）")

# 上传Excel文件
uploaded_file = st.sidebar.file_uploader("上传课程表（xlsx格式）", type="xlsx")
if uploaded_file is not None:
    try:
        # 读取上传的Excel文件
        import_df = pd.read_excel(uploaded_file)
        # 验证列名是否匹配
        required_cols = ['课程名称', '星期', '开始时间', '结束时间', '教室', '课前提醒（分钟）']
        if all(col in import_df.columns for col in required_cols):
            # 合并到现有课程表
            st.session_state.course_df = pd.concat([st.session_state.course_df, import_df], ignore_index=True)
            st.sidebar.success("✅ 批量导入课程成功！")
        else:
            st.sidebar.error(f"❌ Excel列名不匹配，需要包含：{required_cols}")
    except Exception as e:
        st.sidebar.error(f"❌ 导入失败：{str(e)}")

# -------------------------- 第五步：实现课程删除功能 --------------------------
st.sidebar.divider()
st.sidebar.subheader("删除课程")

# 选择要删除的课程
course_to_delete = st.sidebar.selectbox("选择要删除的课程", options=st.session_state.course_df['课程名称'].tolist(), placeholder="无课程可删除", index=None)
if st.sidebar.button("🗑️ 删除选中课程"):
    if course_to_delete:
        # 过滤掉选中的课程
        st.session_state.course_df = st.session_state.course_df[st.session_state.course_df['课程名称'] != course_to_delete]
        st.sidebar.success(f"🗑️ 成功删除课程：{course_to_delete}")
    else:
        st.sidebar.warning("❌ 请先选择要删除的课程！")

# -------------------------- 第六步：显示当前所有课程表 --------------------------
st.subheader("📋 我的课程表")
# 若课程表不为空，显示表格；否则提示添加课程
if not st.session_state.course_df.empty:
    st.dataframe(st.session_state.course_df, use_container_width=True)
    # 可选：下载课程表
    csv = st.session_state.course_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 下载课程表（CSV格式）",
        data=csv,
        file_name="我的校园课程表.csv",
        mime="text/csv"
    )
else:
    st.info("暂无课程数据，请通过侧边栏添加课程～")

st.divider()

# -------------------------- 第七步：核心AI提醒功能（自动检测+实时提醒） --------------------------
st.subheader("🔔 课程实时提醒")

# 定义星期映射（方便将中文星期转换为数字，匹配当前日期）
weekday_map = {
    '周一': 0, '周二': 1, '周三': 2, '周四': 3, '周五': 4, '周六': 5, '周日': 6
}
# 获取当前时间
now = datetime.now()
current_weekday = now.weekday()  # 当前星期（0=周一，6=周日）
current_time = now.strftime("%H:%M")  # 当前时间（时:分）
current_datetime = now  # 当前完整时间

# 遍历课程表，检测是否需要提醒
remind_list = []  # 存储需要提醒的课程
current_course_list = []  # 存储正在进行的课程
upcoming_course_list = []  # 存储待上课程

# 若课程表不为空，进行检测
if not st.session_state.course_df.empty:
    for idx, row in st.session_state.course_df.iterrows():
        # 获取课程信息
        course_name = row['课程名称']
        course_weekday = row['星期']
        course_start_str = row['开始时间']
        course_end_str = row['结束时间']
        course_classroom = row['教室']
        remind_mins = row['课前提醒（分钟）']

        # 转换课程星期为数字
        course_weekday_num = weekday_map.get(course_weekday, -1)
        if course_weekday_num == -1:
            continue  # 无效星期，跳过

        # 1. 检测是否是今天的课程（星期匹配）
        if course_weekday_num == current_weekday:
            # 转换课程开始/结束时间为datetime格式（方便时间计算）
            course_start = parse(f"{now.date()} {course_start_str}")
            course_end = parse(f"{now.date()} {course_end_str}")
            # 计算提醒时间（课程开始时间 - 提醒分钟数）
            remind_time = course_start - timedelta(minutes=remind_mins)

            # 2. 检测是否需要触发提醒（当前时间在提醒时间之后，且课程未开始）
            if remind_time <= current_datetime < course_start:
                remind_list.append({
                    '课程名称': course_name,
                    '教室': course_classroom,
                    '开始时间': course_start_str,
                    '结束时间': course_end_str
                })
                # 触发桌面弹窗提醒（Windows系统有效）
                try:
                    notification.notify(
                        title="📢 课程提醒",
                        message=f"课程：{course_name}\n教室：{course_classroom}\n开始时间：{course_start_str}\n请提前准备！",
                        timeout=10  # 弹窗显示10秒
                    )
                except:
                    # 若桌面提醒失败，在页面显示提示
                    pass

            # 3. 检测是否是正在进行的课程（当前时间在课程开始和结束之间）
            if course_start <= current_datetime <= course_end:
                current_course_list.append({
                    '课程名称': course_name,
                    '教室': course_classroom,
                    '结束时间': course_end_str
                })

            # 4. 检测是否是待上课程（今天的课程，且未开始）
            if current_datetime < course_start:
                upcoming_course_list.append({
                    '课程名称': course_name,
                    '教室': course_classroom,
                    '开始时间': course_start_str,
                    '剩余时间': (course_start - current_datetime).total_seconds() // 60  # 剩余分钟数
                })

# -------------------------- 第八步：页面展示提醒信息 --------------------------
# 显示正在进行的课程
if current_course_list:
    st.warning("📌 正在进行的课程：")
    for course in current_course_list:
        st.write(f"✅ 课程名称：{course['课程名称']} | 教室：{course['教室']} | 结束时间：{course['结束时间']}")
else:
    st.info("📌 目前无正在进行的课程")

st.divider()

# 显示需要提醒的课程
if remind_list:
    st.error("🔔 紧急提醒！即将开始的课程：")
    for course in remind_list:
        st.write(f"✅ 课程名称：{course['课程名称']} | 教室：{course['教室']} | 开始时间：{course['开始时间']}")
else:
    st.success("🔔 暂无需要紧急提醒的课程")

st.divider()

# 显示待上课程
if upcoming_course_list:
    st.subheader("📅 今日待上课程")
    # 按开始时间排序
    upcoming_course_list.sort(key=lambda x: x['开始时间'])
    for course in upcoming_course_list:
        st.write(f"✅ 课程名称：{course['课程名称']} | 教室：{course['教室']} | 开始时间：{course['开始时间']} | 剩余时间：{int(course['剩余时间'])} 分钟")
else:
    st.info("📅 今日暂无待上课程")