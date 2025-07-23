from datetime import datetime
import io
from typing import AsyncGenerator, List
from pydantic import BaseModel, Field
import socketio
from sqlalchemy import insert, select, update
import config
from database import AsyncSessionLocal, TurChatHistory, TurChatSessions, TurUsers
from sqlalchemy.ext.asyncio.session import AsyncSession
from openai import AsyncOpenAI
from enum import Enum
import database
import schemas
from utils.utils import get_userInfo_from_token
from utils.milvus_helpers import client as milvusclient, format_knowledge_for_prompt, get_embedding

class RoleEnum(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"

class Message(BaseModel):
    role: RoleEnum
    content: str

class GetTextIn(BaseModel):
    ai_message_id: int = Field(...)
    chat_session_id: int = Field(...)


print(f"TIHS IS LLM_API_KEY: {config.LLM_API_KEY}")
print(f"TIHS IS LLM_BASE_URL: {config.LLM_BASE_URL}")
print(f"TIHS IS LLM_MODEL_NAME: {config.LLM_MODEL_NAME}")


async def llmchat(messages: List[Message]) -> AsyncGenerator[str, None]:
    client = AsyncOpenAI(
        api_key=config.LLM_API_KEY,
        base_url=config.LLM_BASE_URL
    )
    
    stream = await client.chat.completions.create(
        model=config.LLM_MODEL_NAME,
        stream=True,
        messages=messages
    )

    async for event in stream:
        content = event.choices[0].delta.content if event.choices and event.choices[0].delta else None

        if content:
            yield content


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
                    
                    # 插入消息
                    query_stmt = insert(TurChatHistory).values(
                        user_id = userid,
                        chat_session_id = chat_session_id,
                        sender = "user",
                        text = requestData.text,
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

                    # 获取嵌入
                    vectors = get_embedding(requestData.text.strip())

                    retrieved_knowledge = milvusclient.search(
                        collection_name=config.EMBEDDING_COLLECTION_NAME,
                        data=[vectors],
                        limit=3,
                        output_fields=["question", "answer", "category"],
                    )

                    # 使用我们的函数来格式化知识
                    formatted_context = format_knowledge_for_prompt(retrieved_knowledge)

                    # 4. 定义你的系统提示词和最终的提示词模板
                    system_prompt = """你是一个专业的ME Pass钱包客服机器人。
                    你的任务是根据我提供的【参考资料】来回答用户的问题。
                    请严格遵守以下规则：
                    1. 你的回答必须完全基于【参考资料】。
                    2. 如果【参考资料】为空或与问题不相关，你必须明确回答“根据现有资料，我暂时无法回答您的问题，请联系人工客服。”，绝对不能自己编造答案。
                    3. 你的语气应该友好、专业、乐于助人。
                    4. 根据用户的语言回答。
                    """

                    # 提示词模板
                    final_prompt_template = """{system_prompt}

                    【参考资料】
                    {context}

                    【用户问题】
                    {user_question}
                    """

                    # 5. 填充模板，构建最终的完整提示词
                    final_prompt = final_prompt_template.format(
                        system_prompt=system_prompt,
                        context=formatted_context if formatted_context else "无", # 如果上下文为空，明确告知模型
                        user_question=requestData.text.strip()
                    )

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
