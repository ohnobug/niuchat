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
from utils.util import get_knowledge_prompt, p, get_language_name

# 得到上下文
async def get_chat_context(userquestion):
    chat_context = []
    
    detected_language = get_language_name(userquestion)
    
    # 得到系统提示词
    chat_context.append(Message(role=RoleEnum.system, content=config.LLM_SYSTEM_PROMPT.format(language=detected_language)))

    retrieved_knowledge = await get_knowledge_prompt(userquestion)
    chat_context.append(Message(role=RoleEnum.user, content=retrieved_knowledge))
    return chat_context

async def ai_retun(question):
    chat_context = await get_chat_context(question)
    
    print(chat_context)
    
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
        faqdf = pd.read_excel(f, index_col=0)

    if config.USE_CHROMADB:
        init_chromadb(datasets=faqdf)

    # userquestion = "同一用户是否可以注册多个账户？"
    # final_prompt = await get_knowledge_prompt(userquestion)
    # print(final_prompt)
    # print(await ai_retun(userquestion))

    with open("./真实用户问答.csv", 'rb') as f:
        df = pd.read_csv(f, index_col=0)

    df = df.iloc[:10]
    semaphore = asyncio.Semaphore(100)

    async def worker(task_name, text):
        async with semaphore:
            print(f"开始任务: {task_name}")
            return await ai_retun(text)

    tasks = [
        worker(task_name=f"问题 = {row.question} ID = {row.Index}", text=row.question)
        for row in df.itertuples()
    ]

    llm_results = await asyncio.gather(*tasks)

    df['llm_result'] = llm_results

    save = df.loc[:, ['question', 'answer', 'llm_result']]
    with open("result.json", "wb") as f:
        save.to_json(f, indent=4, force_ascii=False, orient="records")

asyncio.run(test_llm())
