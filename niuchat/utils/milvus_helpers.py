import json
from pymilvus import CollectionSchema, DataType, FieldSchema, MilvusClient
import config
from utils.llm import get_embedding

# 连接Milvus
client = MilvusClient(config.EMBEDDING_MILVUS_DB_PATH)

# 初始化milvus数据库
def init_milvusdb(milvus_client, datasets):
    try:
        # milvus_client = MilvusClient(config.EMBEDDING_MILVUS_DB_PATH)

        schema = CollectionSchema([
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="question", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="answer", dtype=DataType.VARCHAR, max_length=2048),
            FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=config.EMBEDDING_DIMENSION)
        ], description="FAQ知识库")

        # 检查集合是否存在，如果不存在则创建
        if not milvus_client.has_collection(config.EMBEDDING_COLLECTION_NAME):
            print(f"集合 '{config.EMBEDDING_COLLECTION_NAME}' 不存在。正在创建...")
            milvus_client.create_collection(
                collection_name=config.EMBEDDING_COLLECTION_NAME,
                schema=schema,
            )
            print(f"集合 '{config.EMBEDDING_COLLECTION_NAME}' 创建成功。")
        else:
            print(f"集合 '{config.EMBEDDING_COLLECTION_NAME}' 已存在。")

        index_params = milvus_client.prepare_index_params(
            field_name="embedding",      # 指定要索引的字段
            index_type="IVF_FLAT",       # 推荐使用的索引类型
            metric_type="IP",            # 关键：BGE模型使用内积(IP)或余弦相似度
            params={"M": 16, "efConstruction": 256}
        )

        milvus_client.create_index(
            collection_name=config.EMBEDDING_COLLECTION_NAME,
            index_params=index_params
        )

        milvus_client.load_collection(config.EMBEDDING_COLLECTION_NAME)

        # 去重
        existing_questions_in_milvus = set()
        try:
            existing_records = milvus_client.query(
                collection_name=config.EMBEDDING_COLLECTION_NAME,
                filter="",
                output_fields=["question"],
                limit=1000
            )
            for record in existing_records:
                existing_questions_in_milvus.add(record["question"])
            print(f"在Milvus中找到 {len(existing_questions_in_milvus)} 个现有问题。")
        except Exception as e:
            print(f"查询Milvus中现有问题时出错: {e}")

        print("\n开始向Milvus导入数据...")
        inserted_count = 0
        skipped_count = 0

        for item in datasets:
            category = item['category']
            question = item['question']
            answer = item['answer']

            # 检查问题是否已存在于我们现有问题的集合中
            if question in existing_questions_in_milvus:
                print(f"跳过已存在的问题: '{question}'")
                skipped_count += 1
                continue

            try:
                vector = get_embedding(question)
                data_to_insert = [
                    {
                        "question": question,
                        "answer": answer,
                        "category": category,
                        "embedding": vector
                    }
                ]

                milvus_client.insert(
                    collection_name=config.EMBEDDING_COLLECTION_NAME,
                    data=data_to_insert
                )
                print(f"成功插入: '{question}'")
                inserted_count += 1

                existing_questions_in_milvus.add(question)
            except Exception as e:
                print(f"处理问题 '{question}' 时出错: {e}")
        print(f"\n数据导入完成。总共插入: {inserted_count} 条，总共跳过 (已存在): {skipped_count} 条")
    except Exception as e:
        print(f"Milvus操作期间发生错误: {e}")
    # finally:
    #     if 'milvus_client' in locals() and milvus_client.has_collection(config.EMBEDDING_COLLECTION_NAME):
    #         milvus_client.release_collection(config.EMBEDDING_COLLECTION_NAME)
    #         print(f"集合 '{config.EMBEDDING_COLLECTION_NAME}' 已从内存中释放。")
    #     if 'milvus_client' in locals():
    #         milvus_client.close()
    #         print("Milvus客户端已关闭。")

# with open("./faq.json", 'rb') as f:
#     DATALIST = json.loads(f.read())
#     init_milvusdb(milvus_client=client, datasets=DATALIST)

def milvus_format_knowledge_for_prompt(search_results: list, threshold:float = 0.8) -> str:
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

def milvus_retrieved_knowledge(vectors):
    retrieved_knowledge = client.search(
        collection_name=config.EMBEDDING_COLLECTION_NAME,
        data=[vectors],
        limit=3,
        output_fields=["question", "answer", "category"],
    )

    return retrieved_knowledge
