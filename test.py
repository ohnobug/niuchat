import pandas as pd
import json
import asyncio
import aiohttp
from tqdm import tqdm
from typing import List

# --- 配置区 (已修改为SiliconFlow) ---
INPUT_FILE = './newqa_with_embeddings.xlsx'
OUTPUT_FILE = './newqa_with_embeddings_siliconflow_ok.xlsx'
COLUMN_TO_PROCESS = 'related'
NEW_COLUMN_NAME = 'related_cleaned_sf' # sf for SiliconFlow

# --- SiliconFlow API 配置 ---
# !!! 重要：请在这里填入您自己的SiliconFlow API Key !!!
SILICONFLOW_API_KEY = "sk-jwcnjpikvwlvkqaodhmtqallesmqoxakvfpigazqdjfqkyxo"
SILICONFLOW_API_ENDPOINT = "https://api.siliconflow.cn/v1/chat/completions"
# 您可以使用 Qwen/Qwen2-7B-Instruct，它性价比很高，或者使用更强大的模型
SILICONFLOW_MODEL = "THUDM/GLM-4-9B-0414"

# --- 并发和超时设置 ---
CONCURRENCY_LIMIT = 5 # 云端API可以支持更高的并发
API_TIMEOUT = 120    # API调用超时时间（秒）

# --- 异步调用函数 (已修改为适配SiliconFlow) ---
async def deduplicate_with_siliconflow_async(
    session: aiohttp.ClientSession,
    text: str,
    semaphore: asyncio.Semaphore,
    pbar: tqdm,
    row_index: int
) -> str:
    """
    一个异步函数，调用SiliconFlow API进行语义去重，并实时打印处理结果。
    """
    original_text = text if isinstance(text, str) else ""
    if not original_text.strip():
        pbar.update(1)
        return ""

    try:
        async with semaphore:
            questions = [q.strip() for q in original_text.split('|') if q.strip()]
            if len(questions) <= 1:
                pbar.write(f"\n[行 {row_index + 1}] (无需处理)\n  源  : {original_text}\n  接管: {original_text}")
                return original_text

            # ==========================================================
            # --- **使用之前优化好的Prompt (方案一)** ---
            # ==========================================================
            prompt = f"""# 角色
你是一个严格遵循指令的文本去重工具。

# 任务
对用户提供的【问题文本】进行语义去重。

# 规则
1.  **识别核心意图**: 找出所有意思相同的问句分组。
2.  **保留最佳**: 从每个分组中，只保留一个最简洁、最通用、最完整的问法。
3.  **严格格式**: 将最终保留的所有问题用单个“|”符号连接成一个字符串。你的回答必须且只能是这个字符串，禁止包含任何解释、标题、JSON或额外字符。

# 范例
- 【问题文本】: 如何注册账号|如何注册平台账户|如何创建新账户|如何创建账户|如何自行注册账户|如何注册账号？
- 【你的回答】: 如何注册账号|如何创建新账户

# 开始处理
- 【问题文本】: {original_text}
- 【你的回答】:
"""
            # ==========================================================

            # --- 构建请求头和请求体 ---
            headers = {
                'Authorization': f'Bearer {SILICONFLOW_API_KEY}',
                'Content-Type': 'application/json'
            }
            payload = {
                "model": SILICONFLOW_MODEL,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1024, # 限制最大输出长度
                "temperature": 0.0 # 设置为0以获得最确定性的输出
            }

            async with session.post(SILICONFLOW_API_ENDPOINT, headers=headers, json=payload, timeout=API_TIMEOUT) as response:
                response.raise_for_status() # 如果HTTP状态码是4xx或5xx，则抛出异常
                response_json = await response.json()

                # --- 解析SiliconFlow (OpenAI兼容) 的响应 ---
                if not response_json.get('choices'):
                    raise ValueError("API响应中缺少 'choices' 字段")

                processed_text = response_json['choices'][0]['message']['content'].strip()

                if not processed_text:
                    raise ValueError("模型返回了空内容")

                pbar.write(f"\n[行 {row_index + 1}]\n  源  : {original_text}\n  接管: {processed_text}")
                return processed_text

    except Exception as e:
        error_message = f"处理失败 -> {type(e).__name__}: {e}"
        pbar.write(f"\n[行 {row_index + 1}]\n  源  : {original_text}\n  接管: [{error_message}]")
        return original_text
    finally:
        pbar.update(1)


# --- 主程序 (已修改) ---
async def main():
    # --- API Key 检查 ---
    if SILICONFLOW_API_KEY == "YOUR_SILICONFLOW_API_KEY" or not SILICONFLOW_API_KEY:
        print("错误：请在脚本顶部的 SILICONFLOW_API_KEY 变量中填入您真实的API密钥。")
        return

    try:
        df = pd.read_excel(INPUT_FILE)
    except FileNotFoundError:
        print(f"错误：输入文件 '{INPUT_FILE}' 未找到。")
        return

    if COLUMN_TO_PROCESS not in df.columns:
        print(f"错误: 文件中未找到 '{COLUMN_TO_PROCESS}' 列。")
        return

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    print("\n" + "="*20 + f" 开始使用 SiliconFlow ({SILICONFLOW_MODEL}) 进行实时处理 " + "="*20)
    print("注意：输出顺序取决于任务完成速度，可能不是严格的行号顺序。\n")

    with tqdm(total=len(df), desc=f"并发处理中") as pbar:
        # aiohttp建议为每个程序只创建一个ClientSession
        async with aiohttp.ClientSession() as session:
            tasks = [
                deduplicate_with_siliconflow_async(session, row[COLUMN_TO_PROCESS], semaphore, pbar, index)
                for index, row in df.iterrows()
            ]
            results = await asyncio.gather(*tasks)

    df[NEW_COLUMN_NAME] = results

    try:
        print(f"\n\n--- 所有行处理完成，正在将结果保存到: {OUTPUT_FILE} ---")
        df.to_excel(OUTPUT_FILE, index=False)
        print("--- 文件保存成功！ ---")
    except Exception as e:
        print(f"错误：保存文件时发生异常: {e}")

if __name__ == "__main__":
    asyncio.run(main())