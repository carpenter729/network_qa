import streamlit as st
import requests
import time

#页面配置 
st.set_page_config(
    page_title="计算机网络智能问答助手",
    page_icon="🤖",  # 可以使用 emoji 作为图标
    layout="wide",   # 'wide' 或 'centered'
    initial_sidebar_state="expanded" # 'auto', 'expanded', 'collapsed'
)

#后端API的URL
API_URL = "http://127.0.0.1:8000/ask"

#页面标题和介绍
st.title("🤖 计算机网络智能问答助手")
st.markdown("""
欢迎使用计算机网络智能问答助手！本系统基于 **RAG (检索增强生成)** 技术，
能够根据提供的计算机网络知识库来回答您的问题。

**使用说明:**
1.  在下方的聊天框中输入您关于计算机网络的问题。
2.  按回车键提交。
3.  系统将为您生成答案。
""")

st.divider() # 添加一条分割线

# 初始化聊天历史
# 这一步用于在页面刷新时保持对话记录
if "messages" not in st.session_state:
    st.session_state.messages = []

# 展示历史消息
# 遍历 session_state 中的消息并在界面上画出来
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar=message["avatar"]):
        st.markdown(message["content"])

# 用户输入与处理
if question := st.chat_input("请输入您的问题（例如：什么是OSI七层模型？）"):
    
    # 显示用户输入并保存到历史
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(question)
    st.session_state.messages.append({"role": "user", "content": question, "avatar": "🧑‍💻"})

    # 调用API并显示助手回答
    with st.chat_message("assistant", avatar="🤖"):
        try:
            payload = {"question": question}
            
            # 使用 requests 库向后端API发送POST请求
            response = requests.post(API_URL, json=payload, stream=True, timeout=600)

            if response.status_code == 200:
                # 定义生成器，用于 st.write_stream
                def stream_generator():
                    for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                        if chunk:
                            yield chunk
                
                # 使用 write_stream 自动处理流式输出并打字显示
                full_response = st.write_stream(stream_generator())
                
                # 将完整的回答保存到历史，确保刷新后还在
                st.session_state.messages.append({"role": "assistant", "content": full_response, "avatar": "🤖"})

            else:
                st.error(f"请求出错 (状态码: {response.status_code})")
                try:
                    st.write(response.text)
                except:
                    pass

        except requests.exceptions.RequestException as e:
            st.error(f"连接失败: {e}")

#页脚
st.divider()
st.markdown("<footer><p style='text-align: center; color: grey;'>Powered by Streamlit & LangChain</p></footer>",unsafe_allow_html=True)