__import__('pysqlite3')
import re
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import asyncio
import time
import pandas as pd
from utils.llm import get_embedding
from utils.chromadb_helpers import chroma_format_knowledge
import json # 推荐用json来处理向量的存取

# embedding 函数保持不变
async def embedding(question):
    # 假设 get_embedding 返回的是一个 list of floats
    embedding_vector = await get_embedding(question)
    # 将其转换为JSON字符串以便在Excel中存储
    return json.dumps(embedding_vector)

# --- 【核心修改】: 重构主函数以实现增量更新 ---
async def generate_embedding_save_to_excel():
    """
    读取Excel文件，仅为'embedding'列为空的行生成新的嵌入向量，
    然后将更新后的完整数据保存到新的Excel文件中。
    """
    input_file = "./newqa.xlsx"
    output_file = "newqa_with_embeddings.xlsx"
    
    print(f"--- 开始处理文件: {input_file} ---")
    
    try:
        with open(input_file, 'rb') as f:
            df = pd.read_excel(f, index_col=0)
    except FileNotFoundError:
        print(f"错误: 输入文件 '{input_file}' 未找到。")
        return

    # 确保 'embedding' 列存在，如果不存在则创建它
    if 'embedding' not in df.columns:
        df['embedding'] = None

    # 1. 识别需要生成嵌入的行
    #    - pd.isna() 可以同时检查 None, NaN
    #    - (df['embedding'] == '') 检查空字符串
    rows_to_process = df[pd.isna(df['embedding']) | (df['embedding'] == '')]
    
    if rows_to_process.empty:
        print("所有行都已有嵌入数据，无需处理。脚本结束。")
        # 如果你仍然希望保存一份新文件，可以取消下面这行的注释
        # df.to_excel(output_file)
        return

    print(f"总行数: {len(df)}。已存在嵌入的行数: {len(df) - len(rows_to_process)}。")
    print(f"需要生成嵌入的新行数: {len(rows_to_process)}。")

    # 2. 为需要处理的行创建并发任务
    #    使用 Semaphore 控制并发数量，防止对API造成过大压力
    semaphore = asyncio.Semaphore(20)
    
    async def worker(index, question):
        async with semaphore:
            print(f"[{time.strftime('%H:%M:%S')}] 👷 开始处理索引: {index}")
            result = await embedding(question)
            print(f"[{time.strftime('%H:%M:%S')}] ✅ 完成索引: {index}")
            return index, result

    tasks = [
        worker(index, row.question) 
        for index, row in rows_to_process.iterrows()
    ]

    # 3. 执行任务并收集结果
    if tasks:
        print("\n--- 开始并发生成嵌入向量 ---")
        embedding_results = await asyncio.gather(*tasks)
        print("--- 所有嵌入向量生成完毕 ---")
        
        # 4. 将新生成的结果更新回原始DataFrame中
        #    使用 .loc 访问特定索引的行，这是最高效、最安全的方法
        print("\n--- 正在将新结果更新到DataFrame中 ---")
        for index, new_embedding in embedding_results:
            df.loc[index, 'embedding'] = new_embedding

    # 5. 保存更新后的完整DataFrame到新文件
    try:
        print(f"\n正在将最终结果保存到: {output_file}")
        # 使用 to_excel 保存，它会自动处理写入
        df.to_excel(output_file)
        print("--- 文件保存成功！ ---")
    except Exception as e:
        print(f"错误: 保存到Excel文件时发生错误: {e}")


async def get_knowledge(question):
    embedding_vector = await chroma_format_knowledge(question, 10, 1)
    questions = [item['question'] for item in embedding_vector]
    return "|".join(questions)


async def generate_related_save_to_excel():
    """
    读取Excel文件，仅为'embedding'列为空的行生成新的嵌入向量，
    然后将更新后的完整数据保存到新的Excel文件中。
    """
    input_file = "./newqa_with_embeddings.xlsx"
    output_file = "./newqa_with_embeddings.xlsx"

    print(f"--- 开始处理文件: {input_file} ---")
    
    try:
        with open(input_file, 'rb') as f:
            df = pd.read_excel(f, index_col=0)
    except FileNotFoundError:
        print(f"错误: 输入文件 '{input_file}' 未找到。")
        return

    # 确保 'embedding' 列存在，如果不存在则创建它
    if 'related' not in df.columns:
        df['related'] = None

    rows_to_process = df[pd.isna(df['related']) | (df['related'] == '')]
    
    if rows_to_process.empty:
        print("所有行都已有嵌入数据，无需处理。脚本结束。")
        return

    print(f"总行数: {len(df)}。已存在相关问题的行数: {len(df) - len(rows_to_process)}。")
    print(f"需要生成相关问题的新行数: {len(rows_to_process)}。")

    # 2. 为需要处理的行创建并发任务
    #    使用 Semaphore 控制并发数量，防止对API造成过大压力
    semaphore = asyncio.Semaphore(20)
    
    async def worker(index, question):
        async with semaphore:
            print(f"[{time.strftime('%H:%M:%S')}] 👷 开始处理索引: {index}")
            result = await get_knowledge(question)
            print(f"[{time.strftime('%H:%M:%S')}] ✅ 完成索引: {index}")
            return index, result

    tasks = [
        worker(index, row.question) 
        for index, row in rows_to_process.iterrows()
    ]

    # 3. 执行任务并收集结果
    if tasks:
        print("\n--- 开始并发生成嵌入向量 ---")
        embedding_results = await asyncio.gather(*tasks)
        print("--- 所有嵌入向量生成完毕 ---")
        
        # 4. 将新生成的结果更新回原始DataFrame中
        #    使用 .loc 访问特定索引的行，这是最高效、最安全的方法
        print("\n--- 正在将新结果更新到DataFrame中 ---")
        for index, new_embedding in embedding_results:
            df.loc[index, 'related'] = new_embedding

    # 5. 保存更新后的完整DataFrame到新文件
    try:
        print(f"\n正在将最终结果保存到: {output_file}")
        # 使用 to_excel 保存，它会自动处理写入
        df.to_excel(output_file)
        print("--- 文件保存成功！ ---")
    except Exception as e:
        print(f"错误: 保存到Excel文件时发生错误: {e}")


def remove_skill_based_on_row(row):
    """
    接收一整行数据，从 'skills' 列中移除 'question' 列指定的值。
    
    Args:
        row (pd.Series): 代表 DataFrame 的一行。
    
    Returns:
        str: 处理后的 skills 字符串。
    """
    skills_text:str = row['related']
    skill_to_remove = row['question']

    skills_text = skills_text.replace(skill_to_remove, "")
    skills_text = skills_text.replace(skill_to_remove + '？', "")
    skills_text = skills_text.replace("||", "|")
    skills_text = skills_text.replace("？|", "")
    skills_text = re.sub(r'^\|', "", skills_text)

    return skills_text


async def get_knowledge(question):
    embedding_vector = await chroma_format_knowledge(question, 10, 1)
    questions = [item['question'] for item in embedding_vector]
    return "|".join(questions)


async def generate_update_related_save_to_excel():
    """
    读取Excel文件，仅为'embedding'列为空的行生成新的嵌入向量，
    然后将更新后的完整数据保存到新的Excel文件中。
    """
    input_file = "./newqa_with_embeddings.xlsx"
    output_file = "./newqa_with_embeddings.xlsx"

    print(f"--- 开始处理文件: {input_file} ---")
    
    try:
        with open(input_file, 'rb') as f:
            df = pd.read_excel(f, index_col=0)
    except FileNotFoundError:
        print(f"错误: 输入文件 '{input_file}' 未找到。")
        return
    
    # df['related'] = df['related'].apply(process_related_column)
    # df['related'] = df.apply(lambda row: process_related_column(row))
    df['related'] = df.apply(remove_skill_based_on_row, axis=1)
    
    # 5. 保存更新后的完整DataFrame到新文件
    try:
        print(f"\n正在将最终结果保存到: {output_file}")
        # 使用 to_excel 保存，它会自动处理写入
        df.to_excel(output_file)
        print("--- 文件保存成功！ ---")
    except Exception as e:
        print(f"错误: 保存到Excel文件时发生错误: {e}")


async def main():
    question = "质押token"
    result = await chroma_format_knowledge(question, 10, 1)
    print(result)

# 运行主函数
if __name__ == "__main__":
    # 使用 aiorunner 或者直接 asyncio.run
    asyncio.run(main())

