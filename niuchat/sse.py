import sys

__import__('pysqlite3')
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import glob
import logging
from logging.handlers import RotatingFileHandler
import os
import re
from fastapi.responses import JSONResponse
import io
import json
import config
import database
import schemas
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy import select, update
from database import AsyncSessionLocal, TurChatHistory, TurChatSessions, TurUsers, get_db
from utils.util import get_userInfo_from_token
from utils.llm import Message, RoleEnum, llmchat
from utils.chromadb_helpers import chroma_format_knowledge

from fastapi import FastAPI, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordBearer
from sse_starlette.sse import EventSourceResponse

print(f"TIHS IS LLM_API_KEY: {config.LLM_API_KEY}")
print(f"TIHS IS LLM_BASE_URL: {config.LLM_BASE_URL}")
print(f"TIHS IS LLM_MODEL_NAME: {config.LLM_MODEL_NAME}")


# --- 1. 日志和配置 ---
logger = logging.getLogger('my_app_logger')
logger.setLevel(logging.INFO)

# 2. 创建一个 RotatingFileHandler
#    - filename: 日志文件名
#    - maxBytes: 单个文件的最大字节数 (这里是 1MB)
#    - backupCount: 保留的备份文件数量
LOG_BASE_NAME = 'app.log'
LOG_DIRECTORY = "."

handler = RotatingFileHandler(
    os.path.join(LOG_DIRECTORY, LOG_BASE_NAME), 
    maxBytes=1024*1024,
    backupCount=5
)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)


console_handler = logging.StreamHandler()
console_formatter = logging.Formatter('%(levelname)s: %(message)s')
console_handler.setFormatter(console_formatter)

logger.addHandler(handler)
logger.addHandler(console_handler)

# --- Lifespan 管理器 (保持不变) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ASGI startup: Initializing resources...")
    yield
    logger.info("ASGI shutdown: Disposing database engine...")
    if database.engine:
        await database.engine.dispose()
        logger.info("ASGI shutdown: Database engine disposed successfully.")

app = FastAPI(lifespan=lifespan)

# --- 认证 (保持不变) ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        userinfo = get_userInfo_from_token(token)
        async with AsyncSessionLocal() as db:
            if not await db.get(TurUsers, userinfo['user_id']):
                # 不需要显式的 begin()，会话上下文管理器会处理事务
                db.add(TurUsers(id=userinfo['user_id'], phone_number=userinfo['user_id'], password_hash='no password'))
                await db.commit()
        return userinfo
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid credentials: {e}")


# --- API 接口 ---
@app.post("/chat/sessions", response_model=schemas.ChatNewsessionOut)
async def create_chat_session(
    request_data: schemas.ChatNewsessionIn,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    user_id = current_user['user_id']
    savetitle = request_data.title[:200]

    new_session = TurChatSessions(
        user_id=user_id,
        title=savetitle,
        llm_model_name=config.LLM_MODEL_NAME,
        me_smart_customer_service_version=config.ME_SMART_CUSTOMER_SERVICE_VERSION
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)

    chat_session_id = new_session.id

    return schemas.ChatNewsessionOut(
        code=200, message="success",
        data=schemas.ChatNewsession(
            chat_session_id=chat_session_id,
            llm_model_name=config.LLM_MODEL_NAME,
            me_smart_customer_service_version=config.ME_SMART_CUSTOMER_SERVICE_VERSION
        )
    )

async def knowledge_insert(chat_context: list, knowledge_list:list = []):
    """
    少样本提示
    """
    for item in knowledge_list:
        question = item['related']
        urls = item['urls']
        
        chat_context.append(Message(role=RoleEnum.user, content=f"【参考资料】{item['answer']}\n\n【用户问题】{item['question']}"))
        chat_context.append(Message(role=RoleEnum.assistant, content=f"{item['answer']}\n{urls}\n{question}"))

    chat_context.append(Message(role=RoleEnum.user, content=f"可以讲个笑话吗？"))
    chat_context.append(Message(role=RoleEnum.assistant, content=f"对不起，不可以哦。"))


# --- 流式生成器 ---
async def stream_chat_generator(
    chat_session_id: int,
    request_data: schemas.ChatNewmessageIn,
    user_id: int,
    db
) -> AsyncGenerator[str, None]:
    try:
        user_question = request_data.text.strip()

        # 1. 准备上下文 (逻辑不变)
        query_stmt = select(TurChatHistory).where(
            TurChatHistory.chat_session_id == chat_session_id,
            TurChatHistory.user_id == user_id
        ).order_by(TurChatHistory.id.asc())
        result = await db.execute(query_stmt)
        history = result.scalars().all()

        chat_context = []
        # detected_language = get_language_name(user_question)
        system_prompt = config.LLM_SYSTEM_PROMPT
        
        # logger.info("-" * 50)
        # logger.info(system_prompt)
        # logger.info("-" * 50)
        
        # 系统提示词
        chat_context.append(Message(role=RoleEnum.system, content=system_prompt))

        # 从知识库中查询出来的知识
        knowledge_list = await chroma_format_knowledge(question=user_question, n_results=config.CHROMADB_MAXIMUM_QUERY_RESULT, threshold=config.CHROMADB_QUERY_THRESHOLD)

        await knowledge_insert(chat_context, knowledge_list)

        for chat in history:
            chat_context.append(Message(role=RoleEnum.user if chat.sender == 'user' else RoleEnum.assistant, content=chat.text))

        # 用户提出的问题
        chat_context.append(Message(role=RoleEnum.user, content=user_question))

        logger.info("-" * 80)
        logger.info(chat_context)
        logger.info("-" * 80)

        # 2. 保存用户消息和AI消息占位符 (逻辑不变)
        user_message = TurChatHistory(user_id=user_id, chat_session_id=chat_session_id, sender="user", text=user_question)
        ai_message_stub = TurChatHistory(user_id=user_id, chat_session_id=chat_session_id, sender="ai", text="")
        db.add(user_message)
        db.add(ai_message_stub)
        await db.flush()
        ai_message_id = ai_message_stub.id

        # 3. 实时流式处理和状态驱动解析
        buffer = ""
        full_response_buffer = io.StringIO()
        message_id_counter = 0

        # 辅助函数，用于处理和发送缓冲区内容
        async def process_buffer(current_buffer: str):        
            nonlocal message_id_counter

            content_to_process = current_buffer.strip()
            # print(f"-----------{content_to_process}-----------")

            if not content_to_process:
                return

            message_id_counter += 1
            payload = {"session": str(chat_session_id), "id": message_id_counter}

            # 联系人工客服按钮
            if content_to_process.startswith("[BUTTON]"):
                payload.update({"type": "button", "title": content_to_process.replace("[BUTTON]", "").strip(), "url": "/mecs/person/service"})
            # 相关问题
            elif content_to_process.startswith("[RELATED]"):
                payload.update({"type": "related", "title": content_to_process.replace("[RELATED]", "").strip()})
            # 参考链接
            elif content_to_process.startswith("[REFERENCE]"):
                print(content_to_process)
                pattern = r'\[(.*?)\]\s+?\[(.*?)\]\((.*)'
                match = re.search(pattern, content_to_process)
                if match:
                    token_text = match.group(2)
                    url = match.group(3)
                    payload.update({"type": "reference", "title": token_text, "url": f"/mecs/web?url={url}"})
            else:
                payload.update({"type": "text", "content": content_to_process})

            yield json.dumps(payload, ensure_ascii=False)
            await asyncio.sleep(0.01)

        logger.info(chat_context)

        try:
            async for token in llmchat(chat_context):
                
                print(token)
                
                full_response_buffer.write(token)

                # 如果是[开头就开始累计
                if token.strip().startswith('['):
                    # if len(buffer) > 0:
                    #     async for item in process_buffer(buffer):
                    #         yield item
                    #     buffer = ""
                    buffer += token
                    continue

                # 一直累计到换行
                if len(buffer) > 0:
                    if "\n" in token:
                        async for item in process_buffer(buffer):
                            yield item
                        buffer = ""
                    else:
                        buffer += token
                    continue

                # 正常token输出
                async for item in process_buffer(token):
                    yield item

            # 最后一个buffer的处理
            if len(buffer) > 0:
                async for item in process_buffer(buffer):
                    yield item

            yield "[DONE]"

        except Exception as e:
            error_message = f"LLM请求失败: {e}"
            error_payload = {"session": str(chat_session_id), "id": message_id_counter + 1, "type": "error", "content": error_message}
            logger.error(error_payload)

            # 修改点: 直接 yield 错误的 JSON 字符串
            yield json.dumps(error_payload, ensure_ascii=False)
            # 修改点: 直接 yield '[DONE]' 字符串
            yield "[DONE]"

            await db.execute(update(TurChatHistory).values(text=error_message).where(TurChatHistory.id == ai_message_id))
            await db.commit()
            return


        # 4. 异步更新数据库中的完整AI响应 (逻辑不变)
        full_response_text = full_response_buffer.getvalue()
        await db.execute(update(TurChatHistory).values(text=full_response_text).where(TurChatHistory.id == ai_message_id))
        await db.commit()
        await db.close()
    except Exception as e:
        print(e)
    finally:
        await db.close()


@app.post("/chat/stream")
async def send_message_and_stream(
    request_data: schemas.ChatNewmessageIn,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    user_id = current_user['user_id']
    chat_session_id = request_data.chat_session_id

    session_obj = await db.get(TurChatSessions, chat_session_id)
    if not session_obj or session_obj.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问此会话")

    generator = stream_chat_generator(chat_session_id, request_data, user_id, db)
    return EventSourceResponse(generator, media_type="text/event-stream")


@app.get("/logs", response_class=JSONResponse)
def list_logs():
    """
    列出所有可用的日志文件。
    FastAPI 会自动将 Python 列表转换为 JSON 响应。
    """
    try:
        log_files = [os.path.basename(f) for f in glob.glob(os.path.join(LOG_DIRECTORY, f'{LOG_BASE_NAME}*'))]
        # 对文件进行排序，app.log 在最前面
        log_files.sort(key=lambda x: int(x.split('.')[-1]) if x.split('.')[-1].isdigit() else -1)
        return log_files
    except Exception as e:
        # FastAPI 中，推荐使用 HTTPException 来处理错误
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/logs/latest", response_class=Response)
def get_latest_log():
    """
    获取最新日志文件的内容 (即 app.log)，作为纯文本返回。
    """
    # 直接复用下面的函数
    return get_log_by_filename(LOG_BASE_NAME)


@app.get("/logs/{filename}", response_class=Response)
def get_log_by_filename(filename: str):
    """
    获取指定日志文件的内容，并作为纯文本字符串返回。
    """
    # 安全性检查，防止路径遍历攻击
    if not re.match(r'^app\.log(\.\d+)?$', filename):
        raise HTTPException(status_code=400, detail="不合法的文件名。")

    filepath = os.path.join(LOG_DIRECTORY, filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"文件 {filename} 未找到。")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 直接使用 FastAPI 的 Response 对象，并指定 media_type
        return Response(content=content, media_type="text/plain")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取文件时发生错误: {str(e)}")


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
