# app/streamlit_app.py
"""Streamlit frontend for Document RAG (supports PPTX, PDF, Text, Images)"""

import os
# Fix OpenMP conflict with some libraries (langchain, etc.)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from src.config import config
from src.deep_research import DeepResearchAgent
from src.rag.chain import RAGChain
from src.server.image_server import ImageServer
from src.logging import log

# Configure page
st.set_page_config(
    page_title="文档 RAG 智能问答",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize RAG chain and image server
if "rag_chain" not in st.session_state:
    try:
        st.session_state.rag_chain = RAGChain()
        log.info("RAGChain initialized (singleton)")

        # 预热LLM连接 - 建立Ollama连接并加载模型
        st.session_state.rag_chain.warmup()

    except Exception as e:
        st.error(f"初始化失败: {e}")
        st.warning("请检查 .env 文件中的 API 配置是否正确")
        st.stop()

if "image_server" not in st.session_state:
    try:
        st.session_state.image_server = ImageServer()
        st.session_state.image_server.start()
        log.info("Image server started")
    except Exception as e:
        st.warning(f"图片服务器启动失败: {e}")

if "research_agent" not in st.session_state:
    try:
        st.session_state.research_agent = DeepResearchAgent(
            service=None
        )
        log.info("DeepResearchAgent initialized")
    except Exception as e:
        st.warning(f"研究代理初始化失败: {e}")


def main():
    """Main application"""
    st.title("文档 RAG 与 Deep Research 工作台")
    st.markdown("支持文档问答与研究任务两种模式，研究模式会输出计划、证据和报告产物。")

    # Sidebar
    with st.sidebar:
        st.header("文档管理")
        mode = st.radio("工作模式", ["问答模式", "研究模式"], key="app_mode")

        # Initialize upload state
        if "uploading_file" not in st.session_state:
            st.session_state.uploading_file = None

        # File uploader (hidden when processing)
        if st.session_state.uploading_file is None:
            uploaded_file = st.file_uploader(
                "上传文档文件",
                type=["pptx", "ppt", "pdf", "txt", "md", "markdown", "log", "text", "jpg", "jpeg", "png", "gif", "bmp", "webp", "tiff"],
                accept_multiple_files=False,
                key="file_uploader"
            )

            if uploaded_file:
                # Save uploaded file
                upload_dir = config.upload_dir
                upload_dir.mkdir(parents=True, exist_ok=True)
                file_path = upload_dir / uploaded_file.name
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getvalue())

                st.session_state.uploading_file = {
                    "name": uploaded_file.name,
                    "path": str(file_path)
                }
                st.rerun()
        else:
            # Show pending file info
            file_info = st.session_state.uploading_file
            st.text(f"📄 {file_info['name']}")

            # Progress status container
            status_container = st.status("待命")

            if st.button("处理文档"):
                # Update progress
                status_container.update(label="解析文档内容", state="running")

                def on_progress(status):
                    status_container.update(label=status.current_step, state="running")

                try:
                    result = st.session_state.rag_chain.load_document(
                        file_info["path"],
                        on_progress=on_progress,
                    )
                    status_container.update(label="完成", state="complete")
                    st.success(f"处理完成！")
                    st.json(result)
                    # Clear upload state after successful processing
                    st.session_state.uploading_file = None
                except Exception as e:
                    status_container.update(label=f"错误: {e}", state="error")
                    st.error(f"处理失败: {e}")

            # Cancel button to clear upload state
            if st.button("取消", type="secondary"):
                st.session_state.uploading_file = None
                st.rerun()

        # Get loaded documents for Q&A settings
        documents = st.session_state.rag_chain.list_documents()

        # Document selector for Q&A
        if documents:
            st.divider()
            st.subheader("文档选择")
            doc_options = [d["file_name"] for d in documents]
            st.session_state.selected_doc = st.selectbox(
                "选择文档", ["所有文档"] + doc_options, key="doc_selector"
            )
            st.session_state.research_docs = st.multiselect(
                "研究模式文档范围",
                options=doc_options,
                default=doc_options,
                key="research_doc_selector",
            )

            # Retrieval weights
            bm25_w = st.slider(
                "BM25 权重",
                min_value=0.0,
                max_value=1.0,
                value=config.bm25_weight,
                step=0.1,
                key="bm25_weight"
            )
            vector_w = st.slider(
                "向量检索权重",
                min_value=0.0,
                max_value=1.0,
                value=config.vector_weight,
                step=0.1,
                key="vector_weight"
            )
            st.caption(f"当前组合: BM25 {bm25_w} + 向量 {vector_w}")

            # Retrieval count
            retrieval_k = st.number_input(
                "检索结果数量",
                min_value=1,
                max_value=20,
                value=config.retrieval_k,
                step=1,
                key="retrieval_k"
            )
            # Update retriever's retrieval_k
            if documents and st.session_state.rag_chain:
                st.session_state.rag_chain.hybrid_retriever.retrieval_k = retrieval_k

            # LLM Temperature
            temperature = st.slider(
                "LLM Temperature",
                min_value=0.0,
                max_value=1.0,
                value=config.llm_temperature,
                step=0.1,
                help="越低回答越确定性越高，越高越有创造性",
                key="temperature"
            )
            st.caption(f"当前 Temperature: {temperature}")

            # Update temperature in LLM
            if documents and st.session_state.rag_chain:
                st.session_state.rag_chain.set_temperature(temperature)

            # Update weights in retriever
            if documents and st.session_state.rag_chain:
                st.session_state.rag_chain.hybrid_retriever.set_weights(bm25_w, vector_w)

        # Clear all
        if st.button("清空所有文档", type="primary"):
            st.session_state.rag_chain.clear()
            st.success("已清空")
            st.rerun()

    # Main content
    if mode == "问答模式":
        render_chat_mode()
    else:
        render_research_mode(documents)


def render_chat_mode():
    """Render the original Q&A UI."""
    st.header("智能问答")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            # Extract and render images separately, then render remaining markdown
            import re
            content = message["content"]

            # Find all image placeholders: ![desc](url)
            img_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'

            # Split content by images
            parts = []
            last_end = 0
            for match in re.finditer(img_pattern, content):
                # Add text before this image
                if match.start() > last_end:
                    parts.append(('text', content[last_end:match.start()]))
                # Add image
                desc = match.group(1)
                url = match.group(2)
                parts.append(('image', url, desc))
                last_end = match.end()

            # Add remaining text
            if last_end < len(content):
                parts.append(('text', content[last_end:]))

            # Render - use containers for better layout
            for part in parts:
                if part[0] == 'text':
                    if part[1].strip():
                        st.markdown(part[1])
                else:
                    try:
                        st.image(part[1], caption=part[2])
                    except Exception:
                        # Fallback: show as markdown if st.image fails
                        st.markdown(f"![{part[2]}]({part[1]})")

    # Get selected document from sidebar (default to None for all docs)
    selected_doc = st.session_state.get("selected_doc")
    file_name = None if not selected_doc or selected_doc == "所有文档" else selected_doc

    if prompt := st.chat_input("输入您的问题..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate response (non-streaming for better image rendering)
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                try:
                    result = st.session_state.rag_chain.ask(prompt, file_name=file_name)
                    st.markdown(result.answer)

                    # Show sources
                    if result.sources:
                        with st.expander("参考来源"):
                            for source in result.sources:
                                pages = source["pages"]
                                if isinstance(pages, list):
                                    pages_str = f"{min(pages)}-{max(pages)}"
                                else:
                                    pages_str = str(pages)
                                st.text(
                                    f"📄 {source['file_name']} - 第 {pages_str} 页"
                                )

                except Exception as e:
                    st.error(f"回答失败: {e}")
                    return

            # Save assistant message
            st.session_state.messages.append(
                {"role": "assistant", "content": result.answer}
            )


def render_research_mode(documents):
    """Render the deep research task UI."""
    st.header("Deep Research")
    st.caption("输入一个研究任务，系统会生成计划、证据文件和 Markdown 报告。")
    st.caption(f"当前研究运行时: `{st.session_state.research_agent.runtime_mode}`")

    if "latest_research_result" not in st.session_state:
        st.session_state.latest_research_result = None

    selected_documents = st.session_state.get("research_docs", [])
    if documents and not selected_documents:
        st.info("研究模式默认使用全部已处理文档。也可以在左侧手动选择部分文档。")

    col1, col2 = st.columns([2, 1])

    with col1:
        task = st.text_area(
            "研究任务",
            value=(
                "请总结这些文档中与故障诊断相关的核心方法，"
                "整理成一份带来源的研究报告。"
            ),
            height=140,
            key="research_task_input",
        )

    with col2:
        output_mode = st.selectbox(
            "输出类型",
            options=["研究报告", "培训讲义", "对比分析"],
            key="research_output_mode",
        )

    run_disabled = not documents
    if st.button("开始研究", type="primary", disabled=run_disabled):
        try:
            with st.spinner("正在生成研究计划、收集证据并撰写报告..."):
                result = st.session_state.research_agent.run(
                    task=task,
                    selected_documents=selected_documents,
                    output_mode=output_mode,
                )
                st.session_state.latest_research_result = result
            st.success("研究任务完成")
        except Exception as e:
            st.error(f"研究任务执行失败: {e}")

    result = st.session_state.latest_research_result
    if not result:
        return

    plan_col, evidence_col, report_col = st.columns([1, 1, 2])

    with plan_col:
        st.subheader("研究计划")
        st.caption(f"实际执行路径: `{result.execution_mode}`")
        if result.execution_note:
            st.info(result.execution_note)
        for todo in result.todos:
            st.markdown(f"- `{todo.status}` {todo.content}")
        st.divider()
        st.subheader("质量检查")
        st.markdown(result.quality_summary)

    with evidence_col:
        st.subheader("产物文件")
        for artifact in result.artifacts:
            st.markdown(f"- **{artifact.label}**")
            st.code(artifact.path)

    with report_col:
        st.subheader("最终报告")
        st.markdown(result.final_report)


if __name__ == "__main__":
    main()
