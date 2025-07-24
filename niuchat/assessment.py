import sys
import asyncio
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from utils.llm import get_embedding
import pandas as pd

# 相似度阈值，高于或等于此值则认为通过
SIMILARITY_THRESHOLD = 0.9 

async def calculate_async_similarity(sentence1: str, sentence2: str) -> float:
    """
    异步获取两个句子的词嵌入，并计算它们的余弦相似度。
    """
    print("正在并发获取两个句子的词嵌入...", file=sys.stderr)
    
    # 使用 asyncio.gather 来并发执行两个异步任务，提高效率
    embeddings_list = await asyncio.gather(
        get_embedding(sentence1),
        get_embedding(sentence2)
    )
    
    embedding1 = np.array(embeddings_list[0]).reshape(1, -1)
    embedding2 = np.array(embeddings_list[1]).reshape(1, -1)
    
    # 计算余弦相似度
    similarity_score = cosine_similarity(embedding1, embedding2)[0][0]
    
    return similarity_score

async def main():
    """
    主异步函数，负责解析参数和驱动整个流程。
    """
    with open("result.json", 'rb') as f:
        df = pd.read_json(f)

    for item in df.itertuples():
        standard_answer = item.answer
        generated_answer = item.llm_result
        
        # 调用异步函数来计算分数
        score = await calculate_async_similarity(standard_answer, generated_answer)
        
        # # 打印详细信息，这些信息会在 promptfoo 的结果中显示
        print(f"标准答案: {standard_answer}")
        print(f"生成答案: {generated_answer}")
        print(f"计算出的语义相似度分数: {score:.4f}")

    async def apply(row):
        standard_answer = row.answer
        generated_answer = row.llm_result
        
        # 调用异步函数来计算分数
        score = await calculate_async_similarity(standard_answer, generated_answer)

        # # # 打印详细信息，这些信息会在 promptfoo 的结果中显示
        # print(f"标准答案: {standard_answer}")
        # print(f"生成答案: {generated_answer}")
        # print(f"计算出的语义相似度分数: {score:.4f}")
        return score

    tasks = [apply(row) for row in df.itertuples()]

    results = await asyncio.gather(*tasks)
    df['consine_similarity_score'] = results
    df.to_json("result_consine.json", indent=4, force_ascii=False, orient="records")

if __name__ == "__main__":
    # 使用 asyncio.run() 来启动异步主函数
    asyncio.run(main())
    # with open("result_consine.json", 'rb') as f:
    #     df = pd.read_json(f)

    # df.to_excel("result_consine.xlsx")