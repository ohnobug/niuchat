import os
from dotenv import load_dotenv

load_dotenv()

# 请替换成你自己的数据库信息
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Goodnewchat")
DB_PORT = os.getenv("DB_PORT", 3306)
DB_HOST = os.getenv("DB_HOST", "192.168.0.5")
DB_NAME = os.getenv("DB_NAME", "niuchat")
DATABASE_URL = f"mysql+aiomysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


SECRET_KEY = os.getenv("SECRET_KEY", "a_very_secret_key_change_this_in_production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30


# 需求 1: 每个号码发送限制 (常量)
MAX_SMS_PER_DAY = 5
SMS_CODE_EXPIRE_MINUTES = 5


LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://192.168.0.5:11434/v1")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "qwen2.5")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmqservice:5672/")

ME_SMART_CUSTOMER_SERVICE_VERSION = os.getenv("ME_SMART_CUSTOMER_SERVICE_VERSION", "1.0")


EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "ollama")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "http://192.168.0.5:11434/v1")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "bge-m3")

# 定义集合名称
EMBEDDING_MILVUS_DB_PATH = os.getenv("EMBEDDING_MILVUS_DB_PATH", "./milvus_db/me_knowledge.db")
EMBEDDING_CHROMA_DB_PATH = os.getenv("EMBEDDING_CHROMA_DB_PATH", "./milvus_db/me_knowledge_chroma")
EMBEDDING_COLLECTION_NAME = os.getenv("EMBEDDING_COLLECTION_NAME", "knowledge_base")
EMBEDDING_DIMENSION = os.getenv("EMBEDDING_DIMENSION", "1024")

# 使用Chromadb作为faq数据库
USE_CHROMADB = os.getenv("USE_CHROMADB", True)


LLM_SYSTEM_PROMPT = """# 角色与核心任务
你是一个专业的ME Pass钱包客服机器人。
你的唯一任务是根据我提供的【参考资料】来回答用户的问题。

# 回答内容的规则
1.  **严格基于资料**: 你的回答必须完全源于【参考资料】。
2.  **综合信息**: 如果有多条相关的【参考资料】，请将它们综合成一个连贯的回答，不要简单罗列。
3.  **自信地回答**: 当资料足够时，直接回答问题，不要使用“根据资料显示...”等前言。
4.  **处理未知问题**: 如果【参考资料】为空或与问题无关，必须回复标准话术：“根据现有资料，我暂时无法回答您的问题，建议您联系人工客服。” 绝对禁止编造答案。
5.  **保持专业**: 你的语气应始终友好、专业、乐于助人。

# 输出格式的绝对指令
你必须严格遵守以下格式化指令，这是最高优先级：
1.  **语言**: 必须使用【{language}】进行回答。忽略所有其他语言。
2.  **结构**: 你的回答由不同类型的行组成。**每种元素必须独占一行**。
    *   **普通文本**: 直接书写，无需任何标签。
    *   **可操作按钮**: 使用 `[BUTTON] 按钮标题` 格式, 且最多一个。
    *   **相关问题**: 使用 `[RELATED] 问题标题` 格式。
    *   **参考链接**: 使用 `[REFERENCE] 链接标题` 格式。
3. **可操作按钮数量**: 可操作按钮只允许一个。

# 完整示例
---
【用户问题】:
我想参加活动，怎么获得邀请？

【参考资料】:
- 邀请新朋友加入ME Pass并完成ME ID KYC认证，即可获得0.1 MEC奖励。
- 如需人工帮助，请点击下方引导按钮联系人工客服。
- 相关问题：奖励什么时候到账？

【你的回答】 (应严格按照此格式输出):
当前邀请新朋友加入ME Pass并完成ME ID KYC认证，即可获得0.1 MEC奖励，邀请越多新用户，获得更多MEC奖励！
[RELATED] 奖励什么时候到账?
[RELATED] 如何邀请新用户?
[BUTTON] 联系人工客服
---
"""