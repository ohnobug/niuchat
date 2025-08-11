import sys
__import__('pysqlite3')
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import sqlite3
import json
import config
import pandas as pd
import chromadb
from utils.llm import get_embedding
import asyncio

# 初始化mariadb
def init_mariadb():
    import sqlalchemy
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.engine.url import make_url
    from sqlalchemy import text

    def database_exists(url: str) -> bool:
        """
        更简洁地检查给定的 MariaDB/MySQL 数据库是否存在。
        """
        try:
            engine = sqlalchemy.create_engine(url)
            with engine.connect():
                # 连接成功意味着数据库存在
                pass
            return True
        except OperationalError as e:
            # 错误码 1049 表示 "Unknown database"
            if e.orig and e.orig.args[0] == 1049:
                return False
            # 其他错误（如密码错误）则重新抛出
            raise

    def database_create_tables(url: str):
        print("Executing SQL from file: ./new_version_tur.sql")

        # 1. 读取整个 SQL 文件
        with open('./new_version_tur.sql', 'r', encoding='utf-8') as f:
            # 使用 split(';') 来分割语句
            sql_commands = f.read().split(';')

        engine = sqlalchemy.create_engine(url)
        with engine.connect() as connection:
            # 2. 循环执行每一条分割后的 SQL 命令
            for command in sql_commands:
                # 过滤掉注释和分割后产生的空字符串
                if command.strip() and not command.strip().startswith('--'):
                    try:
                        connection.execute(text(command))
                    except Exception as e:
                        print(f"Error executing command: {command.strip()}")
                        print(f"Error: {e}")
                        # 如果你希望遇到错误就停止，可以在这里 raise e
            
            # SQLAlchemy 2.0+ 默认是 "commit as you go"，
            # 但如果你的事务块需要显式提交，可以保留这行
            connection.commit() 
        print("SQL script executed successfully.")


    def create_database_if_not_exists(url: str):
        """
        检查数据库是否存在，如果不存在，则创建它。

        :param url: 目标数据库的完整连接字符串。
                    例如: "mysql+pymysql://user:pass@host/new_db"
        """
        # 首先，使用我们的辅助函数进行检查
        if database_exists(url):
            print(f"Database at '{url}' already exists.")
            return

        print(f"Database at '{url}' not found. Proceeding to create it...")

        # 从原始 URL 中解析出数据库名和其他组件
        parsed_url = make_url(url)
        db_name_to_create = parsed_url.database

        # 创建一个连接到服务器本身的 URL (不指定数据库)
        # 这对于执行 CREATE DATABASE 至关重要
        server_url = parsed_url.set(database="")
      
        try:
            # 使用有权限创建数据库的用户连接到服务器
            engine = sqlalchemy.create_engine(server_url)

            with engine.connect() as connection:
                # 使用 `CREATE DATABASE IF NOT EXISTS` 是最佳实践，可以防止竞争条件
                # 使用反引号 ` ` 来安全地处理数据库名，以防它是保留关键字或包含特殊字符
                # 注意: CREATE DATABASE 通常不能使用绑定参数，所以我们直接格式化
                # 但因为我们是从 URL 中解析的，所以这里是安全的。
                # 对于 DDL 语句，有些数据库驱动需要你提交事务
                create_db_command = text(f"CREATE DATABASE IF NOT EXISTS `{db_name_to_create}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                connection.execute(create_db_command)

                # 创建表
                database_create_tables(url=url)

            print(f"Database '{db_name_to_create}' created successfully.")

        except OperationalError as e:
            print(f"Could not create database. Please check user permissions and connection details.")
            print(f"Error: {e}")
            raise
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            raise


    ROOT_USER=config.DB_USER
    ROOT_PASSWORD=config.DB_PASSWORD
    HOST=config.DB_HOST
    DB_NAME=config.DB_NAME
    DB_PORT=config.DB_PORT
    db_url_to_check_and_create = f"mysql+pymysql://{ROOT_USER}:{ROOT_PASSWORD}@{HOST}:{DB_PORT}/{DB_NAME}"

    # --- 运行示例 ---
    print("--- 创建MariaDB数据库 ---")
    create_database_if_not_exists(db_url_to_check_and_create)

    print("\n--- 检查MariaDB是否已存在 ---")
    create_database_if_not_exists(db_url_to_check_and_create)


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
            metadatas_to_insert.append({
                "category": item.category,
                "answer": item.answer,
                "original_question": question
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
        print(f"ChromaDB操作期间发生错误: {e}")
        # 如果有必要，可以在这里处理异常
    finally:
        print("\n初始化脚本执行完毕。")
        # 对于 EphemeralClient，没有 close() 或 release() 方法，
        # 它会随着Python进程的结束而自动清理。


if __name__ == "__main__":
    init_mariadb()

    with open("./newqa.xlsx", 'rb') as f:
        df = pd.read_excel(f, index_col=0)
        asyncio.run(init_chromadb(datasets=df))