import openai
from pymilvus import MilvusClient
import config

# 连接Milvus
client = MilvusClient(config.EMBEDDING_MILVUS_DB_PATH)

if client.has_collection(config.EMBEDDING_COLLECTION_NAME):
    client.load_collection(config.EMBEDDING_COLLECTION_NAME)

client_openai = openai.OpenAI(
    base_url=config.EMBEDDING_BASE_URL,
    api_key=config.EMBEDDING_API_KEY,
)

def get_embedding(text: str):
    """得到词嵌入

    Args:
        text: 文本
    """
    response_embedding = client_openai.embeddings.create(
        model=config.EMBEDDING_MODEL_NAME,
        input=[text]
    )

    return response_embedding.data[0].embedding



def format_knowledge_for_prompt(search_results: list, threshold:float = 0.8) -> str:
    """
    将 Milvus 的搜索结果列表格式化为适合 LLM 提示词的字符串。

    Args:
        search_results: 来自 milvus_client.search() 的结果列表。

    Returns:
        一个包含所有知识点的、格式化好的字符串。
        如果搜索结果为空，则返回一个空字符串。
    """
    if not search_results:
        return ""

    context_parts = []
    # 循环遍历每一个搜索到的结果
    for i, result in enumerate(search_results):
        if (result[0]['distance'] < threshold):
            continue
        
        # 从结果中提取 'entity' 字典
        entity = result[0].get('entity', {})
        
        # 提取具体字段，使用 .get() 方法以防某些字段缺失
        question = entity.get('question', 'N/A')
        answer = entity.get('answer', 'N/A')
        category = entity.get('category', 'N/A')
        
        # 构建单个知识点的格式化字符串
        # 使用序号 (i+1) 使其更清晰
        part = f"参考资料[{i+1}]:\n- 问题: {question}\n- 回答: {answer}\n- 分类: {category}\n"
        context_parts.append(part)

    # 使用换行符将所有部分拼接在一起
    return "\n".join(context_parts)
