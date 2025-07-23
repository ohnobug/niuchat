# import os
import config
from utils.milvus_helpers import get_embedding
from pymilvus import MilvusClient, DataType, FieldSchema, CollectionSchema

# 初始化milvus数据库
def init_milvusdb():
    # if os.path.exists(config.EMBEDDING_MILVUS_DB_PATH):
    #     print(f"--- 加载milvus缓存: {config.EMBEDDING_MILVUS_DB_PATH} ---")
    #     return

    data_list = [
        {"category": "找回钱包", "question": "如何找回忘记的助记词", "answer": "ME Pass不保存用户的助记词和私钥，无法协助找回。用户需自行备份并保管好助记词和私钥，否则资产将永久丢失。"},
        {"category": "找回钱包", "question": "如何找回已登录的加密钱包", "answer": "登录账户后选择'已有钱包'，点击'开始导入'，输入助记词或私钥手动填写代码。"},
        {"category": "找回钱包", "question": "如何找回已验证的区块链钱包地址", "answer": "登录您的邮箱或手机号，选择'已有钱包'，点击'开始导入'，输入助记词或私钥即可找回账户。"},
        {"category": "找回钱包", "question": "如何找回被遗忘的助记词密码", "answer": "ME Pass不保存用户的助记词和私钥，无法协助找回。用户需自行备份并保管好助记词和私钥，否则资产将永久丢失。"},
        {"category": "找回钱包", "question": "如何恢复钱包", "answer": "登录您的邮箱或手机号，选择'已有钱包'，点击'开始导入'，输入助记词或私钥即可找回账户。"},
        {"category": "找回钱包", "question": "如何找回钱包", "answer": "登录您的邮箱或手机号，选择'已有钱包'，点击'开始导入'，输入助记词或私钥即可找回账户。"},
        {"category": "找回钱包", "question": "如何找回被删除的账户", "answer": "登录您的邮箱或手机号，选择'已有钱包'，点击'开始导入'，输入助记词或私钥即可找回账户。"},
        {"category": "找回钱包", "question": "如何解决登录错误钱包的问题", "answer": "登录您的邮箱或手机号，选择'已有钱包'，点击'开始导入'，输入助记词或私钥即可找回账户。"},
        {"category": "找回账户", "question": "如何找回已注册的账户", "answer": "需点击忘记密码并更改新密码"},
        {"category": "找回账户", "question": "忘记密码如何找回", "answer": "需点击忘记密码并更改新密码"},
        {"category": "冻结账户", "question": "如何找回被冻结的账户", "answer": "请联系人工客服或者是提交工单"},
        {"category": "冻结账户", "question": "如何处理账户被冻结的问题？", "answer": "请联系人工客服或者是提交工单"},
        {"category": "冻结账户", "question": "如何解决临时封号问题？", "answer": "请联系人工客服或者是提交工单"},
        {"category": "冻结账户", "question": "如何解决账号被限制访问的问题？", "answer": "请联系人工客服或者是提交工单"},
        {"category": "注册账户", "question": "如何注册账户", "answer": "欢迎访问Meta Earth，您可以通过官方网站或应用创建新账户"},
        {"category": "注册账户", "question": "如何创建新账户", "answer": "欢迎访问Meta Earth，您可以通过官方网站或应用创建新账户"},
        {"category": "注册账户", "question": "同一用户是否可以注册多个账户？", "answer": "完成账号验证后，无法在ME Pass创建新账户。"},
        {"category": "注册账户", "question": "已通过身份验证的账户是否可以创建新账户？", "answer": "不可以，每个账号只能进行一次身份验证。"},
        {"category": "注册账户", "question": "如何处理已验证地址已存在的问题？", "answer": "完成账号验证后，无法在ME Pass创建新账户。"},
        {"category": "注册账户", "question": "用户是否可以创建多个ME账号", "answer": "不可以，每个账号只能进行一次身份验证。"},
        {"category": "注册账户", "question": "如何注册手机号码", "answer": "欢迎访问Meta Earth，您可以通过官方网站或应用创建新账户"},
        {"category": "注册账户", "question": "无法使用手机号注册", "answer": "请发送ME账号页面截图至客服，以便核实身份"},
        {"category": "邮箱/手机号", "question": "如何修改绑定邮箱", "answer": "请登录账户后，在账户设置中找到邮箱管理部分，点击修改邮箱按钮，按照提示操作即可。"},
        {"category": "邮箱/手机号", "question": "如何更换绑定的邮箱", "answer": "请登录账户后，在账户设置中找到邮箱管理部分，点击修改邮箱按钮，按照提示操作即可。"},
        {"category": "邮箱/手机号", "question": "未收到邮箱验证码", "answer": "请联系人工客服或者是提交工单"},
        {"category": "邮箱/手机号", "question": "无法收到邮箱验证码", "answer": "请联系人工客服或者是提交工单"},
        {"category": "邮箱/手机号", "question": "如何获取验证码", "answer": "验证码将发送至您的邮箱，请注意查收。"},
        {"category": "邮箱/手机号", "question": "输入手机号后未收到验证码", "answer": "请联系人工客服或者是提交工单"},
        {"category": "邮箱/手机号", "question": "更换手机号后无法登录如何处理", "answer": "请联系人工客服或者是提交工单"},
        {"category": "邮箱/手机号", "question": "注册手机号不可用能否重新登录", "answer": "请联系人工客服或者是提交工单"},
        {"category": "邮箱/手机号", "question": "如何更换手机号码以绑定其他钱包", "answer": "请登录账户后，在账户设置中找到手机管理部分，点击修改手机按钮，按照提示操作即可。"},
        {"category": "邮箱/手机号", "question": "无法添加Passkey和电话号码，验证码无法发送，可能的原因是什么？", "answer": "请发送ME账号页面截图至客服，以便核实身份。"},
        {"category": "登录", "question": "如何解决me pass应用无法登录的问题", "answer": "请发送ME账号页面截图至客服，以便核实身份。"},
        {"category": "登录", "question": "退出应用后重新进入需要输入邮箱和密码的原因", "answer": "请发送ME账号页面截图至客服，以便核实身份。"},
        {"category": "登录", "question": "如何解决登录问题？", "answer": "请发送ME账号页面截图至客服，以便核实身份。"},
        {"category": "删除账户", "question": "如何删除账户", "answer": "目前暂不支持删除账户功能。一旦ME账号完成实名认证，该信息将永久记录在区块链上，无法移除。但无需担心，区块链技术安全性高，未经授权无法进行任何交易。"},
        {"category": "删除账户", "question": "如何彻底卸载应用并注销账户", "answer": "目前暂不支持删除账户功能。一旦ME账号完成实名认证，该信息将永久记录在区块链上，无法移除。但无需担心，区块链技术安全性高，未经授权无法进行任何交易。"},
        {"category": "设备绑定", "question": "同一设备是否可以登录多个账户？", "answer": "同一设备无法登录多个账户，除非使用全新未登录过任何ME Pass账户的设备"},
        {"category": "设备绑定", "question": "如何解除设备与账户的绑定？", "answer": "误绑定设备后，当前设备无法登录其他账户，需使用其他未绑定的设备登录该账户。"},
        {"category": "设备绑定", "question": "如何解除已绑定的设备？", "answer": "误绑定设备后，当前设备无法登录其他账户，需使用其他未绑定的设备登录该账户。"},
        {"category": "设备绑定", "question": "设备是否可以绑定多个钱包？", "answer": "每个设备只能绑定一个已验证的钱包。如果设备已绑定钱包，无法再绑定其他钱包。"},
        {"category": "设备绑定", "question": "登录设备异常如何处理？", "answer": "请尝试重启设备并连接WiFi"},
        {"category": "钱包与助记词", "question": "如何获取助记词", "answer": "ME Pass不保存用户的私钥、助记词等私密信息，这些数据加密存储在用户设备上。若遗忘助记词，需自行备份恢复，ME Pass无法协助找回。"},
        {"category": "钱包与助记词", "question": "如何创建钱包", "answer": "您可以通过手动输入助记词来创建钱包，具体步骤包括输入助记词并按照提示操作。"},
        {"category": "钱包与助记词", "question": "如何导入钱包", "answer": "您可以通过手动输入助记词来创建钱包，具体步骤包括输入助记词并按照提示操作。"},
        {"category": "钱包与助记词", "question": "如何正确输入助记词", "answer": "您可以通过手动输入助记词来创建钱包，具体步骤包括输入助记词并按照提示操作。"},
        {"category": "钱包与助记词", "question": "输入助记词后提示已存在如何解决？", "answer": "您可以通过手动输入助记词来创建钱包，具体步骤包括输入助记词并按照提示操作。"},
        {"category": "钱包与助记词", "question": "输入短语后提示无效如何处理", "answer": "请确认您是否拥有助记词，并按照提示输入。"},
        {"category": "钱包与助记词", "question": "如何填写表格中的灰色字段？", "answer": "请按照提供的指示操作，确保正确输入短语。"},
        {"category": "钱包与助记词", "question": "输入助记词错误会导致什么后果？", "answer": "由于无法导入正确的助记词，我们无法恢复您的ME Pass账户。请提供正确的助记词或私钥以进行账户恢复。"},
        {"category": "钱包与助记词", "question": "如何备份助记词", "answer": "请安全存储，如导出到本地设备或安全笔记。丢失后无法协助恢复账户。"},
        {"category": "钱包与助记词", "question": "什么是助记词？", "answer": "助记词是用于加密钱包的备份密钥，由12到24个随机单词组成，可帮助用户在丢失设备时恢复钱包和资金。"},
        {"category": "钱包与助记词", "question": "助记词的作用是什么", "answer": "助记词是用于加密钱包的备份密钥，由12到24个随机单词组成，可帮助用户在丢失设备时恢复钱包和资金。"},
        {"category": "钱包与助记词", "question": "为什么助记词无效？", "answer": "请检查短语是否符合格式要求，如长度、字符限制等。若仍无法解决，请联系客服进一步处理。"},
        {"category": "钱包与助记词", "question": "如何正确保存助记词", "answer": "请安全存储，如导出到本地设备或安全笔记。丢失后无法协助恢复账户。"},
        {"category": "钱包与助记词", "question": "未备份助记词和私钥是否会导致资产丢失？", "answer": "是的，若未备份助记词和私钥，将无法恢复账户，导致资产永久丢失。同时，无法创建新钱包和账户，因为ME账号是唯一的，系统会因身份重复而拒绝。"}
    ]

    try:
        milvus_client = MilvusClient(config.EMBEDDING_MILVUS_DB_PATH)

        schema = CollectionSchema([
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="question", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="answer", dtype=DataType.VARCHAR, max_length=2048),
            FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=config.EMBEDDING_DIMENSION)
        ], description="FAQ知识库")

        # 检查集合是否存在，如果不存在则创建
        if not milvus_client.has_collection(config.EMBEDDING_COLLECTION_NAME):
            print(f"集合 '{config.EMBEDDING_COLLECTION_NAME}' 不存在。正在创建...")
            milvus_client.create_collection(
                collection_name=config.EMBEDDING_COLLECTION_NAME,
                schema=schema,
            )
            print(f"集合 '{config.EMBEDDING_COLLECTION_NAME}' 创建成功。")
        else:
            print(f"集合 '{config.EMBEDDING_COLLECTION_NAME}' 已存在。")

        index_params = milvus_client.prepare_index_params(
            field_name="embedding",      # 指定要索引的字段
            index_type="IVF_FLAT",       # 推荐使用的索引类型
            metric_type="IP",            # 关键：BGE模型使用内积(IP)或余弦相似度
            params={"M": 16, "efConstruction": 256}
        )

        milvus_client.create_index(
            collection_name=config.EMBEDDING_COLLECTION_NAME,
            index_params=index_params
        )

        milvus_client.load_collection(config.EMBEDDING_COLLECTION_NAME)

        # 去重
        existing_questions_in_milvus = set()
        try:
            existing_records = milvus_client.query(
                collection_name=config.EMBEDDING_COLLECTION_NAME,
                filter="",
                output_fields=["question"],
                limit=1000
            )
            for record in existing_records:
                existing_questions_in_milvus.add(record["question"])
            print(f"在Milvus中找到 {len(existing_questions_in_milvus)} 个现有问题。")
        except Exception as e:
            print(f"查询Milvus中现有问题时出错: {e}")

        print("\n开始向Milvus导入数据...")
        inserted_count = 0
        skipped_count = 0

        for item in data_list:
            category = item['category']
            question = item['question']
            answer = item['answer']

            # 检查问题是否已存在于我们现有问题的集合中
            if question in existing_questions_in_milvus:
                print(f"跳过已存在的问题: '{question}'")
                skipped_count += 1
                continue

            try:
                vector = get_embedding(question)
                data_to_insert = [
                    {
                        "question": question,
                        "answer": answer,
                        "category": category,
                        "embedding": vector
                    }
                ]

                insert_result = milvus_client.insert(
                    collection_name=config.EMBEDDING_COLLECTION_NAME,
                    data=data_to_insert
                )
                print(f"成功插入: '{question}'")
                inserted_count += 1

                existing_questions_in_milvus.add(question)
            except Exception as e:
                print(f"处理问题 '{question}' 时出错: {e}")
        print(f"\n数据导入完成。总共插入: {inserted_count} 条，总共跳过 (已存在): {skipped_count} 条")
    except Exception as e:
        print(f"Milvus操作期间发生错误: {e}")
    finally:
        if 'milvus_client' in locals() and milvus_client.has_collection(config.EMBEDDING_COLLECTION_NAME):
            milvus_client.release_collection(config.EMBEDDING_COLLECTION_NAME)
            print(f"集合 '{config.EMBEDDING_COLLECTION_NAME}' 已从内存中释放。")
        if 'milvus_client' in locals():
            milvus_client.close()
            print("Milvus客户端已关闭。")

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
    print("--- 第一次运行：创建数据库 ---")
    create_database_if_not_exists(db_url_to_check_and_create)

    print("\n--- 第二次运行：检查已存在的数据库 ---")
    create_database_if_not_exists(db_url_to_check_and_create)

if __name__ == "__main__":
    init_milvusdb()
    init_mariadb()
