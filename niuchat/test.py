__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import asyncio
import io
import time
import pandas as pd
import config
from utils.chromadb_helpers import init_chromadb
from utils.llm import Message, RoleEnum, get_embedding, llmchat
from utils.util import get_system_prompt, p

# 得到上下文
async def get_chat_context(userquestion):
    chat_context = []
    final_prompt = await get_system_prompt(userquestion)
    chat_context.append(Message(role=RoleEnum.system, content=final_prompt))
    chat_context.append(Message(role=RoleEnum.user, content=userquestion))
    return chat_context

async def ai_retun(question):
    chat_context = await get_chat_context(question)
    text_buffer = io.StringIO()
    async for eachtoken in llmchat(chat_context):
        text_buffer.write(eachtoken)
    return text_buffer.getvalue()

async def embedding(question):
    embedding = await get_embedding(question)
    return embedding

# 全量构建嵌入保存的excel
async def generate_embedding_save_to_excel():
    with open("./newqa.xlsx", 'rb') as f:
        df = pd.read_excel(f, index_col=0)

    # 1. 创建一个 Semaphore 对象，它持有 pool_size 个许可证
    semaphore = asyncio.Semaphore(20)
    
    # 2. 创建一个“工人”协程，它会先获取许可证再执行任务
    async def worker(task_name, text):
        # async with 会自动获取和释放 semaphore
        async with semaphore:
            # 此时，我们保证了最多只有 pool_size 个 worker 在同时执行下面的代码
            print(f"[{time.strftime('%H:%M:%S')}] 🔑 {task_name}: 已获得许可证，进入工作区")
            return await embedding(text)

    tasks = [
        worker(f"任务: {row.Index}", row.question) 
        for row in df.itertuples() 
    ]

    # 4. 使用 asyncio.gather 并发运行所有“工人”任务
    embedding_results = await asyncio.gather(*tasks)

    # 5. 将结果赋值给新列
    df['embedding'] = embedding_results

    with open("newqa3.xlsx", "wb") as r:
        df.to_excel(r)

# 测试大语言模型
async def test_llm():
    with open("./newqa.xlsx", 'rb') as f:
        df = pd.read_excel(f, index_col=0)

    if config.USE_CHROMADB:
        init_chromadb(datasets=df)

    df = df.iloc[:10]
    semaphore = asyncio.Semaphore(20)

    async def worker(task_name, text):
        async with semaphore:
            print(f"开始任务：{task_name}")
            return await ai_retun(text)
    
    tasks = [
        worker(task_name=f"问题 = {row.question}", text=row.question)
        for row in df.itertuples()
    ]

    llm_results = await asyncio.gather(*tasks)

    df['llm_result'] = llm_results
    
    print(df.loc[:, ['question', 'answer', 'llm_result']])

    
asyncio.run(test_llm())
