import sys

__import__('pysqlite3')
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
from pymysql import OperationalError
import sqlalchemy
import json
import config
import pandas as pd
import chromadb
from utils.llm import get_embedding
import asyncio

# 初始化mariadb
def init_mariadb():
    """
    主函数，用于初始化数据库和表。
    """
    def database_exists(url: str) -> bool:
        """检查给定的 MariaDB/MySQL 数据库是否存在。"""
        try:
            engine = sqlalchemy.create_engine(url)
            with engine.connect():
                return True
        except OperationalError as e:
            if e.orig and e.orig.args[0] == 1049: # Unknown database
                return False
            raise


    def create_database(url: str):
        """如果数据库不存在，则创建它。"""
        if database_exists(url):
            print(f"数据库 '{sqlalchemy.make_url(url).database}' 已存在，跳过创建。")
            return

        print(f"数据库 '{sqlalchemy.make_url(url).database}' 不存在，开始创建...")
        parsed_url = sqlalchemy.make_url(url)
        db_name_to_create = parsed_url.database
        server_url = parsed_url.set(database="")
      
        try:
            engine = sqlalchemy.create_engine(server_url)
            with engine.connect() as connection:
                create_db_command = sqlalchemy.text(f"CREATE DATABASE IF NOT EXISTS `{db_name_to_create}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                connection.execute(create_db_command)
                # 在 SQLAlchemy 2.0+ 中，DDL 语句通常会自动提交
            print(f"数据库 '{db_name_to_create}' 创建成功。")
        except Exception as e:
            print(f"创建数据库失败。请检查用户权限和连接信息。")
            print(f"错误: {e}")
            raise

    
    def execute_sql_file(url: str):
        """读取并执行指定的 SQL 文件来创建表。"""
        print("开始从文件 './new_version_tur.sql' 执行 SQL 脚本...")
        try:
            with open('./new_version_tur.sql', 'r', encoding='utf-8') as f:
                sql_commands = f.read().split(';')

            engine = sqlalchemy.create_engine(url)
            with engine.connect() as connection:
                # 开启事务，确保所有语句要么全部成功，要么全部失败
                with connection.begin(): 
                    for command in sql_commands:
                        if command.strip() and not command.strip().startswith('--'):
                            connection.execute(sqlalchemy.text(command))
            print("SQL 脚本执行成功。")
        except FileNotFoundError:
            print("错误: SQL 文件 './new_version_tur.sql' 未找到。")
            raise
        except Exception as e:
            print(f"执行 SQL 脚本时发生错误: {e}")
            raise

    
    # --- 核心逻辑：检查并初始化表 ---
    def check_and_initialize_tables(url: str):
        """
        检查所需的核心表是否存在，如果都不存在，则执行 SQL 文件进行初始化。
        """
        required_tables = {'tur_chat_history', 'tur_chat_sessions', 'tur_users'}
        print(f"正在检查数据库 '{sqlalchemy.make_url(url).database}' 中是否已存在核心表...")

        try:
            engine = sqlalchemy.create_engine(url)
            inspector = sqlalchemy.inspect(engine)
            existing_tables = set(inspector.get_table_names())

            # 检查 required_tables 中的任何一个是否存在于数据库中
            # `isdisjoint` 会在两个集合没有共同元素时返回 True
            if required_tables.isdisjoint(existing_tables):
                print("核心表 'tur_chat_history', 'tur_chat_sessions', 'tur_users' 均不存在。")
                # 调用函数执行 SQL 文件
                execute_sql_file(url)
            else:
                # 找出哪些表已存在
                found_tables = required_tables.intersection(existing_tables)
                print(f"检测到已存在的表: {', '.join(found_tables)}。跳过 SQL 脚本执行。")

        except Exception as e:
            print(f"检查表是否存在时发生错误: {e}")
            raise


    # --- 执行流程 ---
    # 1. 构建数据库连接URL
    db_url = f"mysql+pymysql://{config.DB_USER}:{config.DB_PASSWORD}@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}"
    print("--- 启动数据库初始化流程 ---")
    try:
        # 2. 确保数据库本身存在
        create_database(db_url)
        # 3. 检查表是否存在，并根据情况决定是否执行SQL文件
        check_and_initialize_tables(db_url)
        print("\n--- 数据库初始化流程完成 ---")
    except Exception as e:
        print(f"\n初始化流程因错误而终止: {e}")



async def init_chromadb(datasets: pd.DataFrame):
    chromadb_client = chromadb.PersistentClient(path=config.EMBEDDING_CHROMA_DB_PATH)
    """
    初始化一个临时的、内存中的ChromaDB数据库，并用FAQ数据填充它。
    """
    try:
        print("--- 初始化临时的ChromaDB客户端 ---")
        # 使用 EphemeralClient，所有数据都将存在于内存中，程序结束时消失
        # client = chromadb.EphemeralClient()
        collection_name = config.EMBEDDING_COLLECTION_NAME

        print(f"正在获取或创建集合: '{collection_name}'")
        collection = chromadb_client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

        # --- ChromaDB的去重逻辑 ---
        # 1. 高效获取集合中所有已存在的ID
        existing_ids = set(collection.get(include=[])['ids'])
        print(f"在ChromaDB中找到 {len(existing_ids)} 个现有条目。")

        # --- 准备批量插入的数据 ---
        # ChromaDB的add方法接收的是分离的列表，而不是字典列表
        ids_to_insert = []
        embeddings_to_insert = []
        metadatas_to_insert = []
        documents_to_insert = [] # documents 字段存储将被嵌入的原始文本

        print("\n开始准备要导入ChromaDB的数据...")
        skipped_count = 0
        
        # 2. 遍历你的数据，只处理不存在的条目
        count = 0
        for item in datasets.itertuples():
            count = count + 1
            # 为每条数据创建一个唯一的、确定的ID
            # 使用 "faq_" 前缀和索引可以确保ID是字符串且唯一
            current_id = f"faq_{item.Index}"

            # print(f"正在处理: {current_id}")

            if current_id in existing_ids:
                # print(f"跳过已存在的条目: ID {current_id}")
                skipped_count += 1
                continue

            # 如果ID不存在，则准备数据进行插入
            question = item.question

            # 准备 ChromaDB 需要的各个部分
            ids_to_insert.append(current_id)
            documents_to_insert.append(question)
            
            urls = []
            if item.url != "":
                try:
                    j = json.loads(item.url)
                    urls = []
                    for i in j:
                        urls.append(f"[REFERENCE] [{i['title']}]({i['url']})")
                except:
                    urls = []

            related = [f"[RELATED] {i}" for i in item.related.split("|") if i != ""]

            metadatas_to_insert.append({
                # "category": item.category,
                "original_question": question,
                "answer": item.answer,
                "urls": "\n".join(urls),
                "related": "\n".join(related)
            })

            # 计算向量
            if pd.notna(item.embedding) and isinstance(item.embedding, str) and item.embedding.strip():
                try:
                    vector = json.loads(item.embedding)
                except json.JSONDecodeError:
                    print(f"警告: ID {current_id} 的 embedding 格式错误，将重新计算。")
                    vector = await get_embedding(question)
            else:
                vector = await get_embedding(question)

            embeddings_to_insert.append(vector)

            # --- 批量插入 ---
            # 3. 只有在有新数据时才执行插入操作
            if ids_to_insert and count >= 5000:
                count = 0
                collection.add(
                    ids=ids_to_insert,
                    embeddings=embeddings_to_insert,
                    metadatas=metadatas_to_insert,
                    documents=documents_to_insert
                )
                print(f"数据批量插入{len(ids_to_insert)}条数据成功。")
                ids_to_insert = []
                embeddings_to_insert = []
                metadatas_to_insert = []
                documents_to_insert = [] # documents 字段存储将被嵌入的原始文本

        total = len(datasets)
        print(f"\n数据导入完成。总共插入: {total} 条，总共跳过 (已存在): {skipped_count} 条")
        print(f"集合 '{collection_name}' 中现在的总条目数: {collection.count()}")

        if count != 0 and len(ids_to_insert) > 0:
            print(f"准备批量插入最后部分，共 {len(ids_to_insert)} 条新数据...")
            collection.add(
                ids=ids_to_insert,
                embeddings=embeddings_to_insert,
                metadatas=metadatas_to_insert,
                documents=documents_to_insert
            )
    except Exception as e:
        print(related)
        print(item)
        print(f"ChromaDB操作期间发生错误: {e}")
        # 如果有必要，可以在这里处理异常
    finally:
        print("\n初始化脚本执行完毕。")
        # 对于 EphemeralClient，没有 close() 或 release() 方法，
        # 它会随着Python进程的结束而自动清理。


if __name__ == "__main__":
    init_mariadb()

    with open("./newqa_with_embeddings.xlsx", 'rb') as f:
        df = pd.read_excel(f, index_col=0)
        asyncio.run(init_chromadb(datasets=df))
