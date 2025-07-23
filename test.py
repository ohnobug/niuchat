import config
from utils.milvus_helpers import get_embedding
from utils.milvus_helpers import client as milvusclient
from utils.utils import p


vectors = get_embedding("")

res = milvusclient.search(
    collection_name=config.EMBEDDING_COLLECTION_NAME,
    data=[vectors],
    # filter="subject == 'history'",
    limit=1,
    output_fields=["question", "answer", "category"],
)

def format_knowledge_for_prompt(search_results: list, threshold:float = 0.6) -> str:
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


print(format_knowledge_for_prompt(res))