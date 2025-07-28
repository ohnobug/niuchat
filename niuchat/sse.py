__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import io
import json
import pandas as pd
import config
import database
import schemas
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy import select, update
from database import AsyncSessionLocal, TurChatHistory, TurChatSessions, TurUsers, get_db
from utils.chromadb_helpers import init_chromadb
from utils.util import get_knowledge_prompt, get_userInfo_from_token, get_language_name
from utils.llm import Message, RoleEnum, llmchat

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sse_starlette.sse import EventSourceResponse

print(f"TIHS IS LLM_API_KEY: {config.LLM_API_KEY}")
print(f"TIHS IS LLM_BASE_URL: {config.LLM_BASE_URL}")
print(f"TIHS IS LLM_MODEL_NAME: {config.LLM_MODEL_NAME}")

if config.USE_CHROMADB:
    with open("./newqa.xlsx", 'rb') as f:
        df = pd.read_excel(f, index_col=0)
        init_chromadb(datasets=df)

# --- Lifespan 管理器 (保持不变) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("ASGI startup: Initializing resources...")
    yield
    print("ASGI shutdown: Disposing database engine...")
    if database.engine:
        await database.engine.dispose()
        print("ASGI shutdown: Database engine disposed successfully.")

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
                db.add(TurUsers(id=userinfo['user_id'], phone_number=userinfo['username'], password_hash='no password'))
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

# --- 流式生成器 ---
async def stream_chat_generator(
    chat_session_id: int,
    request_data: schemas.ChatNewmessageIn,
    user_id: int,
    db
) -> AsyncGenerator[str, None]:
    user_question = request_data.text.strip()

    # 1. 准备上下文 (逻辑不变)
    query_stmt = select(TurChatHistory).where(
        TurChatHistory.chat_session_id == chat_session_id,
        TurChatHistory.user_id == user_id
    ).order_by(TurChatHistory.id.asc())
    result = await db.execute(query_stmt)
    history = result.scalars().all()

    chat_context = []
    detected_language = get_language_name(user_question)
    system_prompt = config.LLM_SYSTEM_PROMPT.format(language=detected_language)
    chat_context.append(Message(role=RoleEnum.system, content=system_prompt))

    for chat in history:
        chat_context.append(Message(role=RoleEnum.user if chat.sender == 'user' else RoleEnum.assistant, content=chat.text))

    final_prompt = await get_knowledge_prompt(user_question)
    chat_context.append(Message(role=RoleEnum.user, content=final_prompt))

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

        if content_to_process.startswith("[BUTTON]"):
            payload.update({"type": "button", "title": content_to_process.replace("[BUTTON]", "").strip(), "url": "action_placeholder"})
        elif content_to_process.startswith("[RELATED]"):
            payload.update({"type": "related", "title": content_to_process.replace("[RELATED]", "").strip(), "url": "related_placeholder"})
        elif content_to_process.startswith("[REFERENCE]"):
            parts = [p.strip() for p in content_to_process.replace("[REFERENCE]", "").strip().split('|')]
            payload.update({"type": "reference", "title": parts[0] if parts else "参考", "url": parts[1] if len(parts) > 1 else "url_placeholder"})
        else:
            payload.update({"type": "text", "content": content_to_process})

        yield json.dumps(payload, ensure_ascii=False)
        await asyncio.sleep(0.01)

    try:
        async for token in llmchat(chat_context):
            full_response_buffer.write(token)

            # print(token)

            # 如果是[开头就开始累计
            if token.strip().startswith('['):
                if len(buffer) > 0:
                    async for item in process_buffer(buffer):
                        yield item
                    buffer = ""
                buffer = token.strip()
                continue

            # 一直累计到换行
            if len(buffer) > 0:
                if token == "\n":
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
