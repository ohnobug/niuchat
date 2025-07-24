import config

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
    init_mariadb()
