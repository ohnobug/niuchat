__import__('pysqlite3')
import sys

from utils.llm import Message, RoleEnum, llmchat
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

from datetime import datetime
import io
import json
from typing import List
import socketio
from sqlalchemy import insert, select, update
import config
from database import AsyncSessionLocal, TurChatHistory, TurChatSessions, TurUsers
from sqlalchemy.ext.asyncio.session import AsyncSession
import database
import schemas
from utils.chromadb_helpers import init_chromadb
from utils.util import get_system_prompt, get_userInfo_from_token
import pandas as pd

print(f"TIHS IS LLM_API_KEY: {config.LLM_API_KEY}")
print(f"TIHS IS LLM_BASE_URL: {config.LLM_BASE_URL}")
print(f"TIHS IS LLM_MODEL_NAME: {config.LLM_MODEL_NAME}")

if config.USE_CHROMADB:
    with open("./newqa.xlsx", 'rb') as f:
        df = pd.read_excel(f, index_col=0)
        init_chromadb(datasets=df)

static_files = {
    '/static': './public',
}

mgr = socketio.AsyncAioPikaManager(config.RABBITMQ_URL)
sio = socketio.AsyncServer(
    logger=True,
    engineio_logger=True,
    async_mode='asgi',
    cors_allowed_origins='*',
    client_manager=mgr,
    transports=['websocket']
)

app = socketio.ASGIApp(sio, static_files=static_files)

@sio.on('startup')
async def handle_startup():
     print("ASGI startup signal received.")
     pass

@sio.on('shutdown')
async def handle_shutdown():
    print("ASGI shutdown signal received. Disposing database engine...")
    if  database.engine:
        await database.engine.dispose()
        print("Database engine disposed successfully.")
    else:
        print("Database engine not found or not initialized.")

class WschatNamespace(socketio.AsyncNamespace):
    async def on_connect(self, sid, environ, auth):
        bearer = None
        if environ['HTTP_AUTHORIZATION']:
            bearer = environ['HTTP_AUTHORIZATION'].split(' ')[1]
        else:
            if not auth or 'token' not in auth:
                print(f"Connection rejected for {sid}: No auth token provided.")
                # 拒绝连接
                raise socketio.exceptions.ConnectionRefusedError('Authentication failed: token missing')

        try:
            userinfo = get_userInfo_from_token(bearer)
            async with self.session(sid) as session:
                session['user_id'] = userinfo['user_id']
                session['username'] = userinfo['username']
                
                async with AsyncSessionLocal() as db:
                    try:
                        db: AsyncSession = db
                        query_stmt = select(TurUsers).where(TurUsers.id==userinfo['user_id'])
                        queryResult = await db.scalar(query_stmt)
                        if queryResult is None:
                            # 注册用户
                            # passwordh = password_hash("")
                            insert_stmt = insert(TurUsers).values(
                                id=userinfo['user_id'],
                                phone_number=userinfo['username'],
                                password_hash='no password'
                            )

                            await db.execute(insert_stmt)

                            # result.inserted_primary_key[0]
                            await db.commit()
                    except Exception:
                        await db.rollback()
                        raise
                    finally:
                        await db.close()
                
        except socketio.exceptions.ConnectionRefusedError as e:
            print(f"Connection refused for sid {sid}: {e}")
            raise e
        except Exception as e:
            print(f"Authentication process error for sid {sid}: {e}")
            raise socketio.exceptions.ConnectionRefusedError(f'认证过程中发生错误: {e}')

    async def on_disconnect(self, sid, reason):
        print('disconnect ', sid, reason)

    async def on_create_session(self, sid, data):
        """
        创建会话
        args:
            {
                "title": "与小红的对话"
            }

        response: json格式
            {
                "code": 200
                "message": "success",
                "data": {
                    "chat_session_id": 123456
                }
            }
        """
        requestData = schemas.ChatNewsessionIn.model_validate_json(data)

        async with self.session(sid) as session:
            userid = session['user_id']
            async with AsyncSessionLocal() as db:
                try:
                    savetitle = requestData.title
                    if len(requestData.title) > 200:
                        savetitle = requestData.title[:200]

                    # 插入会话
                    query_stmt = insert(TurChatSessions).values(
                        user_id = userid,
                        title = savetitle,
                    )

                    data = await db.execute(query_stmt)
                    chatSessionId = data.inserted_primary_key[0]
                    await db.commit()

                    await self.emit("create_session", schemas.ChatNewsessionOut(
                        code=200,
                        message="success",
                        data=schemas.ChatNewsession(chat_session_id=chatSessionId)
                    ).model_dump_json(), to=sid)
                except Exception:
                    await self.emit("error", {"type": "create_session", "code": 400, "message": "创建会话消息失败"})
                    await db.rollback()
                    raise
                finally:
                    await db.close()


    async def on_send_message(self, sid, data):
        """
        对话得到流式输出
        
        args:
            data: json格式
                {
                    "chat_session_id": 310,
                    "text": "你好咩？"
                }
        """
        try:
            requestData = schemas.ChatNewmessageIn.model_validate_json(data)
        except Exception as e:
            await self.emit("error", e)
            raise

        async with self.session(sid) as session:
            userid = session['user_id']
            
            async with AsyncSessionLocal() as db:
                try:
                    chat_session_id = requestData.chat_session_id
                    userquestion = requestData.text.strip()
                    
                    # 插入消息
                    query_stmt = insert(TurChatHistory).values(
                        user_id = userid,
                        chat_session_id = chat_session_id,
                        sender = "user",
                        text = userquestion,
                    )

                    data = await db.execute(query_stmt)
                    chatMessageId = data.inserted_primary_key[0]

                    # 创建空白消息等待AI回复
                    query_stmt = insert(TurChatHistory).values(
                        user_id = userid,
                        chat_session_id = chat_session_id,
                        sender = "ai",
                        text = "",
                    )

                    data = await db.execute(query_stmt)
                    aiMessageId = data.inserted_primary_key[0]

                    # 回复收到
                    await self.emit("send_message", schemas.ChatNewmessageOut(
                        code=200,
                        message="success",
                        data=schemas.ChatNewmessage(
                            chat_message_id=chatMessageId,
                            ai_message_id=aiMessageId
                        )
                    ).model_dump_json(), to=sid)
                    await db.commit()


                    # 查找该会话的所有历史记录
                    query_stmt = select(
                        TurChatHistory.id, 
                        TurChatHistory.user_id,
                        TurChatHistory.chat_session_id,
                        TurChatHistory.sender,
                        TurChatHistory.text,
                        TurChatHistory.created_at
                    ).where(
                        TurChatHistory.chat_session_id == chat_session_id,
                        TurChatHistory.user_id == userid
                    ).order_by(
                        TurChatHistory.id.asc()
                    )
                    result = await db.execute(query_stmt)

                    history: List[TurChatHistory] = result.mappings().all()            
                    historyLength = len(history)

                    # 整理成上下文提交给大模型
                    chat_context = []

                    # 得到系统提示词并且去知识库找到相关问题作为少知识提示
                    final_prompt = await get_system_prompt(userquestion)
                    chat_context.append(Message(role=RoleEnum.system, content=final_prompt))

                    for key, chat in enumerate(history):
                        # 判断用户提供的id与数据库的id是否对应
                        if chat.text == "" and chat.sender == 'ai' and key == historyLength - 1:
                            if chat.id != aiMessageId:
                                await self.emit('error', {'data': '没找到新建的AI对话记录'}, to=sid)
                                raise
                            continue

                        if chat.sender == 'user':
                            chat_context.append(Message(role=RoleEnum.user, content=chat.text))
                        else:
                            chat_context.append(Message(role=RoleEnum.assistant, content=chat.text))

                    # 流式输出到浏览器
                    text_buffer = io.StringIO()
                    async for eachtoken in llmchat(chat_context):
                        text_buffer.write(eachtoken)
                        await self.emit("stream_out_token", {
                            "chat_session_id": chat_session_id,
                            "ai_message_id": aiMessageId,
                            "token": eachtoken
                        }, to=sid)

                    await self.emit("stream_out_token", {
                        "chat_session_id": chat_session_id,
                        "ai_message_id": aiMessageId,
                        "token": "\x04"
                    }, to=sid)

                    # 更新AI回答到数据库
                    query_stmt = update(TurChatHistory).values(
                        text=text_buffer.getvalue(),
                        created_at=datetime.now()
                    ).where(
                        TurChatHistory.id == aiMessageId,
                        TurChatHistory.sender == "ai",
                        TurChatHistory.user_id == userid
                    )

                    result = await db.execute(query_stmt)
                    await db.commit()
                    
                except Exception:
                    await self.emit("error", {"type": "send_message", "code": 400, "message": "发送消息失败"})
                    await db.rollback()
                    raise
                finally:
                    await db.close()

sio.register_namespace(WschatNamespace('/'))
