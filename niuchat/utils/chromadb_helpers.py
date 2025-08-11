import chromadb
import config
from utils.llm import get_embedding

# 连接Milvus
# chromadb_client = chromadb.EphemeralClient()
chromadb_client = chromadb.PersistentClient(path=config.EMBEDDING_CHROMA_DB_PATH)

def chroma_retrieved_knowledge(vectors, n_results=10):
    collection = chromadb_client.get_collection(name=config.EMBEDDING_COLLECTION_NAME)
    retrieved_knowledge = collection.query(
        query_embeddings=[vectors],
        n_results=n_results,
    )

    return retrieved_knowledge


async def chroma_format_knowledge(question: str, n_results=50, threshold: float = 0.5):
    """
    将 ChromaDB 的搜索结果字典格式化为适合 LLM 提示词的字符串。

    Args:
        search_results: 来自 collection.query() 的结果字典。
        n_results: 数量
        threshold: 距离阈值。只保留距离小于此阈值的结果。
                   对于余弦距离(cosine)，值越小代表越相似。通常 0.5 是一个不错的起点。

    Returns:
        一个包含所有符合条件知识点的、格式化好的字符串。
        如果无有效结果，则返回一个空字符串。
    """
    vectors = await get_embedding(question)
    search_results = chroma_retrieved_knowledge(vectors=vectors, n_results=n_results)

    # 检查结果是否有效，以及是否包含必要的数据
    if not search_results or not search_results.get('distances'):
        return ""

    # ChromaDB为每个查询返回一个结果列表，我们处理单个查询（最常见情况）
    distances = search_results['distances'][0]
    metadatas = search_results['metadatas'][0]

    context_parts = []
    # 使用一个独立的计数器，确保参考资料编号是连续的
    knowledge_counter = 0

    # 遍历所有返回的结果
    for i, dist in enumerate(distances):
        # 关键逻辑：如果距离大于阈值，则说明不够相关，跳过
        # 注意：对于距离，值越小越好。
        if dist > threshold:
            continue

        knowledge_counter += 1
        metadata = metadatas[i]
        
        # 从 metadata 中安全地提取信息
        question = metadata.get('original_question', 'N/A')
        answer = metadata.get('answer', 'N/A')
        category = metadata.get('category', 'N/A')
        
        # 构建单个知识点的格式化字符串
        # part = f"参考资料[{knowledge_counter}]:\n- 问题: {question}\n- 回答: {answer}\n"
        part = {
            "question": question,
            "answer": answer
        }
        context_parts.append(part)
    return context_parts
