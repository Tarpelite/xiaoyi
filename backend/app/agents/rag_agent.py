"""
RAG Agent 模块
==============

基于研报知识库的检索增强生成 Agent

支持两种模式：
1. 远程模式（默认）：调用 xiaoyi-rag-service
2. 本地模式：使用本地 RAG 服务（向后兼容）
"""

from typing import Dict, Any, List, Optional, Generator
from openai import OpenAI

from app.core.config import settings


class RAGAgent:
    """研报知识库 RAG Agent"""

    def __init__(self, api_key: str, use_remote: bool = True):
        """
        初始化 RAG Agent

        Args:
            api_key: DeepSeek API Key
            use_remote: 是否使用远程研报服务（默认 True）
        """
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        self.use_remote = use_remote
        self._report_client = None
        self._local_service = None

    @property
    def report_client(self):
        """获取远程研报服务客户端"""
        if self._report_client is None:
            from app.data.sources import get_report_client
            self._report_client = get_report_client(settings.report_service_url)
        return self._report_client

    @property
    def local_service(self):
        """获取本地 RAG 服务（向后兼容）"""
        if self._local_service is None:
            try:
                from app.rag import get_rag_service
                self._local_service = get_rag_service()
            except Exception:
                self._local_service = None
        return self._local_service

    def search_reports(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        搜索相关研报内容

        Args:
            query: 用户查询
            top_k: 返回结果数量

        Returns:
            检索结果列表，包含内容、来源、页码等
        """
        if self.use_remote:
            return self._search_remote(query, top_k)
        else:
            return self._search_local(query, top_k)

    def _search_remote(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """使用远程服务搜索"""
        import asyncio
        
        async def _async_search():
            results = await self.report_client.search_reports(
                query=query,
                top_k=top_k,
                use_rerank=True,
            )
            return results
        
        # 在新的事件循环中运行
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果已有事件循环在运行，创建新任务
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _async_search())
                    results = future.result()
            else:
                results = asyncio.run(_async_search())
        except RuntimeError:
            results = asyncio.run(_async_search())
        
        # 转换为统一格式
        formatted_results = []
        for r in results:
            formatted_results.append({
                "content": r.content,
                "file_name": r.file_name,
                "page_number": r.page_number,
                "score": r.rerank_score or r.score,
                "doc_id": r.doc_id,
                "chunk_id": r.chunk_id,
            })
        
        return formatted_results

    def _search_local(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """使用本地服务搜索（向后兼容）"""
        if not self.local_service:
            print("[RAGAgent] 本地 RAG 服务不可用")
            return []
        
        results = self.local_service.search(query, top_k=top_k, use_hybrid=True)

        formatted_results = []
        for r in results:
            formatted_results.append({
                "content": r.content,
                "file_name": r.file_name,
                "page_number": r.page_number,
                "score": r.score,
                "doc_id": r.doc_id
            })

        return formatted_results

    async def search_reports_async(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        异步搜索研报（推荐在异步环境中使用）
        
        Args:
            query: 用户查询
            top_k: 返回结果数量
            
        Returns:
            检索结果列表
        """
        if not self.use_remote:
            # 本地模式在线程中执行
            import asyncio
            return await asyncio.to_thread(self._search_local, query, top_k)
        
        results = await self.report_client.search_reports(
            query=query,
            top_k=top_k,
            use_rerank=True,
        )
        
        formatted_results = []
        for r in results:
            formatted_results.append({
                "content": r.content,
                "file_name": r.file_name,
                "page_number": r.page_number,
                "score": r.rerank_score or r.score,
                "doc_id": r.doc_id,
                "chunk_id": r.chunk_id,
            })
        
        return formatted_results

    def generate_answer(
        self,
        query: str,
        retrieved_docs: List[Dict[str, Any]],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        基于检索结果生成回答

        Args:
            query: 用户问题
            retrieved_docs: 检索到的文档列表
            conversation_history: 对话历史

        Returns:
            生成的回答文本
        """
        # 构建上下文
        context = self._build_context(retrieved_docs)

        system_prompt = """你是专业的行业研究分析师。基于提供的研报内容回答用户问题。

要求：
1. 回答必须基于提供的研报内容，不要编造信息
2. 如果研报内容不足以回答问题，请明确说明
3. 在回答中引用来源，格式如：[来源: xxx.pdf, 第X页]
4. 保持专业、客观的分析风格
5. 如果涉及数据或预测，需标注时效性"""

        prompt = f"""## 用户问题
{query}

## 相关研报内容
{context}

请基于以上研报内容回答用户问题。"""

        messages = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            messages.extend(conversation_history[-5:])

        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.3,
            max_tokens=1500,
        )

        return response.choices[0].message.content

    def generate_answer_stream(
        self,
        query: str,
        retrieved_docs: List[Dict[str, Any]],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Generator[str, None, None]:
        """
        流式生成回答

        Args:
            query: 用户问题
            retrieved_docs: 检索到的文档列表
            conversation_history: 对话历史

        Yields:
            文本片段
        """
        context = self._build_context(retrieved_docs)

        system_prompt = """你是专业的行业研究分析师。基于提供的研报内容回答用户问题。

要求：
1. 回答必须基于提供的研报内容，不要编造信息
2. 如果研报内容不足以回答问题，请明确说明
3. 在回答中引用来源，格式如：[来源: xxx.pdf, 第X页]
4. 保持专业、客观的分析风格
5. 如果涉及数据或预测，需标注时效性"""

        prompt = f"""## 用户问题
{query}

## 相关研报内容
{context}

请基于以上研报内容回答用户问题。"""

        messages = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            messages.extend(conversation_history[-5:])

        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.3,
            max_tokens=1500,
            stream=True
        )

        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def answer_with_rag(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        完整的 RAG 问答流程

        Args:
            query: 用户问题
            conversation_history: 对话历史
            top_k: 检索结果数量

        Returns:
            包含答案和来源的字典
        """
        # 1. 检索相关文档
        retrieved_docs = self.search_reports(query, top_k=top_k)

        # 2. 生成回答
        answer = self.generate_answer(query, retrieved_docs, conversation_history)

        # 3. 提取来源信息
        sources = self._extract_sources(retrieved_docs)

        return {
            "answer": answer,
            "sources": sources,
            "retrieved_count": len(retrieved_docs)
        }

    def answer_with_rag_stream(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        top_k: int = 5
    ) -> Generator[Dict[str, Any], None, None]:
        """
        流式 RAG 问答流程

        Args:
            query: 用户问题
            conversation_history: 对话历史
            top_k: 检索结果数量

        Yields:
            包含类型和内容的字典
        """
        # 1. 检索相关文档
        retrieved_docs = self.search_reports(query, top_k=top_k)

        # 发送检索结果信息
        sources = self._extract_sources(retrieved_docs)
        yield {
            "type": "sources",
            "data": {
                "sources": sources,
                "retrieved_count": len(retrieved_docs)
            }
        }

        # 2. 流式生成回答
        for chunk in self.generate_answer_stream(query, retrieved_docs, conversation_history):
            yield {
                "type": "text_delta",
                "data": {"delta": chunk}
            }

    def _build_context(self, retrieved_docs: List[Dict[str, Any]]) -> str:
        """构建检索上下文"""
        if not retrieved_docs:
            return "未找到相关研报内容。"

        context_parts = []
        for i, doc in enumerate(retrieved_docs, 1):
            context_parts.append(f"""### 文档 {i}
来源: {doc['file_name']}, 第 {doc['page_number']} 页
相关度: {doc['score']:.3f}

{doc['content']}
""")

        return "\n---\n".join(context_parts)

    def _extract_sources(self, retrieved_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """提取来源信息"""
        sources = []
        seen = set()

        for doc in retrieved_docs:
            key = (doc['file_name'], doc['page_number'])
            if key not in seen:
                seen.add(key)
                sources.append({
                    "file_name": doc['file_name'],
                    "page_number": doc['page_number'],
                    "score": doc['score']
                })

        return sources
