import json
import chromadb
import config
from .llm import get_embedding
import pandas as pd

# 连接Milvus
# chromadb_client = chromadb.EphemeralClient()
chromadb_client = chromadb.PersistentClient(path=config.EMBEDDING_CHROMA_DB_PATH)

def init_chromadb(datasets: pd.DataFrame):
    """
    初始化一个临时的、内存中的ChromaDB数据库，并用FAQ数据填充它。
    """
    try:
        print("--- 初始化临时的ChromaDB客户端 ---")
        # 使用 EphemeralClient，所有数据都将存在于内存中，程序结束时消失
        # client = chromadb.EphemeralClient()
        collection_name = config.EMBEDDING_COLLECTION_NAME

        print(f"正在获取或创建集合: '{collection_name}'")
        collection = chromadb_client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

        # --- ChromaDB的去重逻辑 ---
        # 1. 高效获取集合中所有已存在的ID
        existing_ids = set(collection.get(include=[])['ids'])
        print(f"在ChromaDB中找到 {len(existing_ids)} 个现有条目。")

        # --- 准备批量插入的数据 ---
        # ChromaDB的add方法接收的是分离的列表，而不是字典列表
        ids_to_insert = []
        embeddings_to_insert = []
        metadatas_to_insert = []
        documents_to_insert = [] # documents 字段存储将被嵌入的原始文本

        print("\n开始准备要导入ChromaDB的数据...")
        skipped_count = 0
        
        # 2. 遍历你的数据，只处理不存在的条目
        count = 0
        for item in datasets.itertuples():
            count = count + 1
            # 为每条数据创建一个唯一的、确定的ID
            # 使用 "faq_" 前缀和索引可以确保ID是字符串且唯一
            current_id = f"faq_{item.Index}"

            # print(f"正在处理: {current_id}")

            if current_id in existing_ids:
                # print(f"跳过已存在的条目: ID {current_id}")
                skipped_count += 1
                continue

            # 如果ID不存在，则准备数据进行插入
            question = item.question

            # 准备 ChromaDB 需要的各个部分
            ids_to_insert.append(current_id)
            documents_to_insert.append(question)
            metadatas_to_insert.append({
                "category": item.category,
                "answer": item.answer,
                "original_question": question
            })

            # 计算向量
            if item.embedding:
                vector = json.loads(item.embedding)
            else:
                vector = get_embedding(question)

            embeddings_to_insert.append(vector)

            # --- 批量插入 ---
            # 3. 只有在有新数据时才执行插入操作
            if ids_to_insert and count >= 5000:
                count = 0
                print(f"准备批量插入 {len(ids_to_insert)} 条新数据...")
                collection.add(
                    ids=ids_to_insert,
                    embeddings=embeddings_to_insert,
                    metadatas=metadatas_to_insert,
                    documents=documents_to_insert
                )

                ids_to_insert = []
                embeddings_to_insert = []
                metadatas_to_insert = []
                documents_to_insert = [] # documents 字段存储将被嵌入的原始文本

                print("数据批量插入成功。")

        total = len(datasets)
        print(f"\n数据导入完成。总共插入: {total} 条，总共跳过 (已存在): {skipped_count} 条")
        print(f"集合 '{collection_name}' 中现在的总条目数: {collection.count()}")

        if count != 0 and len(ids_to_insert) > 0:
            print(f"准备批量插入最后部分，共 {len(ids_to_insert)} 条新数据...")
            collection.add(
                ids=ids_to_insert,
                embeddings=embeddings_to_insert,
                metadatas=metadatas_to_insert,
                documents=documents_to_insert
            )
    except Exception as e:
        print(f"ChromaDB操作期间发生错误: {e}")
        # 如果有必要，可以在这里处理异常
    finally:
        print("\n初始化脚本执行完毕。")
        # 对于 EphemeralClient，没有 close() 或 release() 方法，
        # 它会随着Python进程的结束而自动清理。

def chroma_format_knowledge_for_prompt(search_results: dict, threshold: float = 0.5) -> str:
    """
    将 ChromaDB 的搜索结果字典格式化为适合 LLM 提示词的字符串。

    Args:
        search_results: 来自 collection.query() 的结果字典。
        threshold: 距离阈值。只保留距离小于此阈值的结果。
                   对于余弦距离(cosine)，值越小代表越相似。通常 0.5 是一个不错的起点。

    Returns:
        一个包含所有符合条件知识点的、格式化好的字符串。
        如果无有效结果，则返回一个空字符串。
    """
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
        part = f"参考资料[{knowledge_counter}]:\n- 问题: {question}\n- 回答: {answer}\n"
        context_parts.append(part)

    # 如果没有找到任何低于阈值的资料，可以返回提示信息
    if not context_parts:
        return "没有找到相关的参考资料。"

    # 使用换行符将所有部分拼接在一起，并在前后添加空行以优化格式
    return "\n" + "\n".join(context_parts)


def chroma_retrieved_knowledge(vectors):
    collection = chromadb_client.get_collection(name=config.EMBEDDING_COLLECTION_NAME)
    retrieved_knowledge = collection.query(
        query_embeddings=[vectors],
        n_results=3,
    )

    return retrieved_knowledge
