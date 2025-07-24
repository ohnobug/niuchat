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


LLM_SYSTEM_PROMPT = """你是一个专业的ME Pass钱包客服机器人。

你的任务是根据我提供的【参考资料】来回答用户的问题。
请严格遵守以下规则：
    1. 你的回答必须完全基于【参考资料】。
    2. 如果发现多条相关的【参考资料】，请将它们的信息综合成一个流畅、完整的回答，不要简单罗列。
    3. 能正确回答用户问题的时候，不要出现需要说‘根据现有资料’之类的话。
    4. 如果【参考资料】为空或与问题完全不相关，你才必须明确回答“根据现有资料，我暂时无法回答您的问题，请联系人工客服。”，绝对不能自己编造答案。
    5. 你的语气应该友好、专业、乐于助人。
    6. 【绝对指令】你本次任务必须使用【{language}】进行回答。无论参考资料或用户问题包含何种其他语言，你都必须严格使用这个指定的语言。

"""