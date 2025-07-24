import io
import json
import re
import os
import pandas as pd

def find_matches_in_file(file_path, pattern):
    """
    读取文件内容，并使用给定的正则表达式查找所有匹配项。

    参数:
    file_path (str): 要读取的文件的路径。
    pattern (str): 用于搜索的正则表达式模式。
    """
    # 检查文件是否存在
    if not os.path.exists(file_path):
        print(f"错误：文件 '{file_path}' 不存在。")
        return

    try:
        # 打开并读取整个文件内容
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        # 使用 re.findall 查找所有非重叠的匹配项
        # (?s) 标志也可以通过 re.DOTALL 传入
        matches = re.findall(pattern, content, flags=re.DOTALL)

        # 检查是否找到了匹配项
        results_list = []
        if matches:
            print(f"在文件 '{file_path}' 中成功找到 {len(matches)} 个匹配项：\n")
            # 逐个打印找到的匹配项
            for i, match in enumerate(matches, 1):
                try:
                    json_string = f"{{\n{match.strip()}\n}}"

                    obj = json.loads(json_string)
                    conversation_data = obj['raw_conversation']

                    # 提取并格式化问题
                    user_messages = conversation_data.get('user_messages', [])
                    question_texts = [msg.get('text', '') for msg in user_messages]
                    formatted_question = '\n'.join(q for q in question_texts if q)

                    # 提取并格式化答案
                    agent_messages = conversation_data.get('agent_messages', [])
                    answer_texts = [msg.get('text', '') for msg in agent_messages]
                    formatted_answer = ""

                    if not answer_texts:
                        formatted_answer = "[未找到客服回答]"
                    elif len(answer_texts) == 1:
                        formatted_answer = answer_texts[0]
                    else:
                        # 使用列表推导式和 join，高效地构建多答案字符串
                        answer_lines = [f"answer{i}: {text}" for i, text in enumerate(answer_texts, 1)]
                        formatted_answer = '\n\n'.join(answer_lines)

                    # --- 3. 将格式化好的问答对作为一个字典追加到列表中 ---
                    if formatted_question: # 只添加有问题的条目
                        qa_dict = {
                            "question": formatted_question,
                            "answer": formatted_answer
                        }
                        results_list.append(qa_dict)

                except (json.JSONDecodeError, KeyError) as e:
                    # 如果单个片段处理失败，打印错误并继续处理下一个
                    print(f"处理某个对话片段时发生错误，已跳过: {e}")
                    continue
                # break
        else:
            print(f"在文件 '{file_path}' 中没有找到任何匹配项。")
            print("请检查您的正则表达式或文件内容是否正确。")

        # print(results_list)
    except Exception as e:
        print(f"处理文件时发生错误: {e}")

    return results_list

# --- 主程序 ---
if __name__ == "__main__":
    # # 1. 请将 'your_file.jsonl' 替换为您的实际文件名
    # #    确保该文件与此 Python 脚本在同一目录下，或者提供完整路径。
    # target_file = 'faq_standard.json' 

    # # 2. 这是您提供的正则表达式
    # #    注意：使用了原始字符串 (r'...') 来避免反斜杠问题
    # regex_pattern = r'("raw_conversation":\s*{.*?\n\s*\]\s*})'

    # # 3. 执行查找函数
    # result = find_matches_in_file(target_file, regex_pattern)
    
    # df = pd.DataFrame(result)
    # with open("真实用户问答.csv", 'wb') as f:
    #     df.to_csv(f)

    # with open("真实用户问答.csv", 'rb') as f:
    #     df = pd.read_csv(f)
    # df.drop_duplicates(subset=['answer'])
    pass