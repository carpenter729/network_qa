import streamlit as st
import requests
import time
import os
#页面配置 
st.set_page_config(
    page_title="计算机网络智能问答助手",
    page_icon="🤖",  # 可以使用 emoji 作为图标
    layout="wide",   # 'wide' 或 'centered'
    initial_sidebar_state="expanded" # 'auto', 'expanded', 'collapsed'
)

# 后端API的URL
# 解释：os.getenv 尝试读取环境变量 "API_URL"。
# 如果在 Docker 里，我们会设置这个变量指向后端容器。
# 如果在本地直接跑，找不到这个变量，就默认使用 "http://127.0.0.1:8000/ask"
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

# 侧边栏：用户系统
with st.sidebar:
    st.title("👤 用户登录/注册")
    st.info("首次输入为注册，后续为登录")
    st.markdown("输入用户名以保存对话记录")
    
   # 增加密码输入框
    username_input = st.text_input("用户名", placeholder="例如: admin")
    password_input = st.text_input("密码", type="password", placeholder="请输入密码") # type="password" 会显示星号
    
    if st.button("提交"):
        if username_input and password_input:
            try:
                # 发送用户名和密码给后端
                payload = {"username": username_input, "password": password_input}
                resp = requests.post(f"{API_URL}/login", json=payload)
                
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state["user_id"] = data["user_id"]
                    st.session_state["username"] = data["username"]
                    st.session_state["messages"] = []
                    st.success(f"{data.get('message', '欢迎')}！")
                    st.rerun()
                elif resp.status_code == 401:
                    st.error("❌ 密码错误，请重试。")
                else:
                    st.error(f"登录失败: {resp.text}")
            except Exception as e:
                st.error(f"无法连接服务器: {e}")
        else:
            st.warning("请输入用户名和密码")

    # 显示当前登录状态
    if "username" in st.session_state:
        st.divider()
        st.write(f"🟢 当前用户: **{st.session_state['username']}**")
        if st.button("退出登录"):
            # 清除状态
            for key in ["user_id", "username", "messages"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()



# --- 主界面逻辑 ---
st.title("🤖 计算机网络智能问答助手")

# 1. 强制登录检查
if "user_id" not in st.session_state:
    st.info("👋 请先在左侧侧边栏输入用户名登录，即可开始对话并保存记录。")
    st.stop() # 停止运行后续代码

# 2. 加载历史记录 (仅当本地列表为空且已登录时加载一次)
if "messages" not in st.session_state:
    st.session_state.messages = []

# 为了防止每次刷新都请求数据库，我们可以加一个标志位，或者简单判断列表为空时去取
if len(st.session_state.messages) == 0:
    try:
        hist_resp = requests.get(f"{API_URL}/history/{st.session_state['user_id']}")
        if hist_resp.status_code == 200:
            st.session_state.messages = hist_resp.json()
    except:
        pass

# 3. 渲染聊天历史
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 4. 处理新消息
if prompt := st.chat_input("请输入您的问题..."):
    # A. 显示并保存用户提问
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    # 后台异步保存到数据库
    requests.post(f"{API_URL}/save_message", json={
        "user_id": st.session_state["user_id"], "role": "user", "content": prompt
    })

    # B. 生成并保存助手回答
    with st.chat_message("assistant"):
        try:
            # 请求流式回答
            response = requests.post(f"{API_URL}/ask", json={"question": prompt}, stream=True)
            
            def stream_generator():
                for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                    if chunk: yield chunk
            
            # 实时显示
            full_response = st.write_stream(stream_generator())
            
            # C. 回答完成后，保存到历史和数据库
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            requests.post(f"{API_URL}/save_message", json={
                "user_id": st.session_state["user_id"], "role": "assistant", "content": full_response
            })
            
        except Exception as e:
            st.error(f"生成回答时出错: {e}")

#页脚
st.divider()
st.markdown("<footer><p style='text-align: center; color: grey;'>Powered by Streamlit & LangChain</p></footer>",unsafe_allow_html=True)