import pika
import sys
import time
import os
import config

def check_rabbitmq_connection(amqp_url, max_retries=10, retry_delay=5):
    """
    在一个循环中尝试连接到 RabbitMQ。

    :param amqp_url: RabbitMQ 的连接 URL
    :param max_retries: 最大尝试次数
    :param retry_delay: 每次重试前的等待时间（秒）
    :return: bool, True 表示成功，False 表示失败
    """
    print("--- 开始 RabbitMQ 连接健康检查 ---")

    for attempt in range(1, max_retries + 1):
        print(f"--> 第 {attempt}/{max_retries} 次尝试连接到 RabbitMQ...")
        try:
            # 使用同步的 BlockingConnection
            connection = pika.BlockingConnection(pika.URLParameters(amqp_url))

            # 检查连接是否真的打开了
            if connection.is_open:
                print("[SUCCESS] ==> RabbitMQ 连接已成功建立。")
                connection.close()
                return True

        except pika.exceptions.AMQPConnectionError as e:
            print(f"[FAILURE] ==> 连接失败: {e}")
            if attempt < max_retries:
                print(f"--> 等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
        except Exception as e:
            # 捕获其他可能的异常，例如 URL 格式错误
            print(f"[FATAL] ==> 发生致命错误: {e}")
            # 发生致命错误时，通常没必要重试
            return False

    # 所有尝试结束后仍然失败
    return False

if __name__ == "__main__":
    # 从环境变量中获取 RabbitMQ URL，这是 Docker 中的最佳实践
    # 提供一个默认值，方便在本地直接运行测试
    RABBITMQ_URL = os.getenv('RABBITMQ_URL', config.RABBITMQ_URL)
    
    if not RABBITMQ_URL:
        print("[ERROR] 致命错误: 环境变量 RABBITMQ_URL 未设置。")
        sys.exit(1)

    # 执行连接检查
    if check_rabbitmq_connection(RABBITMQ_URL, 100000, 1):
        print("\n[OK] 健康检查通过。准备启动主应用...")
        sys.exit(0) # 成功退出！
    else:
        print("\n[ERROR] 健康检查失败。在所有尝试后仍无法连接到 RabbitMQ。应用将不会启动。")
        sys.exit(1) # 失败退出！
