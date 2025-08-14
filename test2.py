import sys
import pandas as pd
import requests
import json
import numpy as np
from typing import List, Optional

# --- 1. 配置 ---
# 请根据您的实际情况修改这些配置
EXCEL_FILE_PATH = 'newqa_with_embeddings.xlsx'  # <-- 修改为您Excel文件的路径
OLLAMA_MODEL = 'bge-m3:latest'         # <-- 修改为您在Ollama中使用的模型名 (例如 bge, nomic-embed-text)
OLLAMA_API_URL = "http://localhost:11434/api/embeddings"
SIMILARITY_THRESHOLD = 0.98                # <-- 相似度阈值，高于此值的将被过滤

# --- 2. 与 Ollama 通信的函数 ---

# 建立一个缓存来存储已经计算过的向量，避免重复请求API，提高效率
embedding_cache = {}

def get_embedding(text: str) -> Optional[List[float]]:
    """
    通过调用Ollama API获取单个文本的向量嵌入。
    """
    if text in embedding_cache:
        return embedding_cache[text]
    
    try:
        payload = {"model": OLLAMA_MODEL, "prompt": text}
        response = requests.post(OLLAMA_API_URL, json=payload)
        response.raise_for_status()  # 如果请求失败 (例如 404, 500), 则抛出异常
        
        embedding = response.json().get('embedding')
        embedding_cache[text] = embedding # 存入缓存
        return embedding
    except requests.exceptions.RequestException as e:
        print(f"Error calling Ollama API for text '{text}': {e}")
        return None
    except json.JSONDecodeError:
        print(f"Error decoding JSON from Ollama API response for text '{text}'. Response: {response.text}")
        return None

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """
    计算两个向量之间的余弦相似度。
    """
    vec1 = np.array(v1)
    vec2 = np.array(v2)
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

# --- 3. 核心处理逻辑 ---

def process_and_filter_related(row) -> str:
    """
    处理DataFrame的单行数据，过滤掉与'question'过于相似的'related'短语。
    """
    question = row['question']
    related_str = row['related']

    # 如果question或related为空，则直接返回空字符串
    if not isinstance(question, str) or not isinstance(related_str, str) or not related_str.strip():
        return ""

    # 获取主问题的向量
    question_vec = get_embedding(question)
    if not question_vec:
        print(f"Skipping row due to embedding failure for question: '{question}'")
        return "" # 如果获取失败，则跳过

    kept_phrases = []
    # 分割、去重并处理每一个相关短语
    related_phrases = related_str.split('|')
    
    for phrase in related_phrases:
        phrase = phrase.strip()
        if not phrase:
            continue

        # 获取相关短语的向量
        phrase_vec = get_embedding(phrase)
        if not phrase_vec:
            print(f"Skipping phrase '{phrase}' due to embedding failure.")
            continue # 如果获取失败，则跳过该短语

        # 计算相似度
        similarity = cosine_similarity(question_vec, phrase_vec)

        # 如果相似度低于阈值，则保留
        if similarity < SIMILARITY_THRESHOLD:
            kept_phrases.append(phrase)


    # 将保留的短语重新用'|'连接
    result = "|".join(kept_phrases)
    
    current_index = row.name
    print(f"[{current_index}] 源：{related_str}  => 去掉：{question} => 剩下：{result}")
    
    return result

# --- 4. 主程序 ---

if __name__ == "__main__":
    try:
        # 读取Excel文件
        df = pd.read_excel(EXCEL_FILE_PATH)

        print(f"Successfully loaded Excel file: {EXCEL_FILE_PATH}")
    except FileNotFoundError:
        print(f"Error: The file '{EXCEL_FILE_PATH}' was not found.")
        print("---")
        # 如果文件不存在，则使用您图片中的数据创建一个示例DataFrame以供演示
        print("Creating a sample DataFrame based on the image for demonstration...")
        data = {
            'question': ['如何注册账户', '如何创建新账户', '同一用户是否可以注册多个账户', '无法使用手机号注册'],
            'related': ['如何注册账号|如何创建新账户', '如何开通新帐户|如何创建新帐户', '是否可以为同一用户创建多个账户|是否可以注册多个帐号|同一用户是否可以注册多个帐号', '请发送ME账号页面截图至客服|注册手机号不可用能否重新登录']
        }
        df = pd.DataFrame(data)
    
    
    # 检查Ollama服务是否可达
    try:
        requests.get("http://localhost:11434", timeout=3)
        print(f"Ollama server is accessible. Using model: '{OLLAMA_MODEL}'")
    except requests.exceptions.ConnectionError:
        print("\nFATAL ERROR: Could not connect to Ollama server at http://localhost:11434.")
        print("Please ensure Ollama is running before executing this script.")
        exit()

    print(f"\nProcessing data with similarity threshold: {SIMILARITY_THRESHOLD}")
    print("This may take some time depending on the amount of data...\n")
    
    # 应用处理函数到每一行，并将结果存入新列'processed_related'
    df['processed_related'] = df.apply(process_and_filter_related, axis=1)

    # 显示结果
    print("\n--- Processing Complete ---")
    
    # 为了更好地在终端显示，选择特定列并转换为字符串
    result_display = df[['question', 'related', 'processed_related']].copy()
    print(result_display.to_string())

    # (可选) 保存结果到新的Excel文件
    output_filename = 'processed_output.xlsx'
    df.to_excel(output_filename, index=False)
    print(f"\nResults saved to '{output_filename}'")
