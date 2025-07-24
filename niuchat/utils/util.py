import base64
import hashlib
from io import BytesIO, StringIO
import json
from datetime import datetime, timedelta
import aiohttp
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select, update
from config import SECRET_KEY, ALGORITHM
import config
import database
from database import TurUsers, TurVerifyCodes
import random
from fastapi import HTTPException
import schemas
from .llm import get_embedding
from .chromadb_helpers import chroma_format_knowledge_for_prompt, chroma_retrieved_knowledge
# from .milvus_helpers import milvus_format_knowledge_for_prompt, milvus_retrieved_knowledge

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    query = select(TurUsers).where(TurUsers.id == int(user_id))
    user = await database.fetch_one(query)
    if user is None:
        raise credentials_exception
    return user

# 得到登录用户名
async def get_login_username(cookie: str = None):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://learn.turcar.net.cn/getusername.php?cookie=' + cookie) as response:            
            html = await response.text()
            return html




def get_userInfo_from_token(bearer: str):
    output = BytesIO()
    base64.decode(StringIO(bearer), output)
    return json.loads(output.getvalue().decode(encoding="utf-8"))


# 生成密码哈希
def password_hash(password: str):
    m = hashlib.sha256()
    m.update(password.encode('utf-8'))
    return m.hexdigest()


def generate_numeric_code_randint():
    # 生成一个介于 100000 和 999999 之间的随机整数
    code = random.randint(100000, 999999)
    return code

# 调试打印专用
def p(stri: str):
    print("\n" * 2)
    print("❤️" * 30)
    print(stri)
    print("❤️" * 30)
    print("\n" * 2)

# 检查验证码
async def check_verify_code(db, phone_number: str, code: str, purpose: schemas.UserGetVerifyCodePurposeEnum):
    # 检查验证码
    select_stmt = select(
        TurVerifyCodes
    ).where(
        TurVerifyCodes.phone_number == phone_number,
        TurVerifyCodes.purpose == purpose,
        TurVerifyCodes.is_used == False,
        TurVerifyCodes.code == code
    ).order_by(
        TurVerifyCodes.id.desc()
    ).limit(1)
    lastVerifyCode = (await db.execute(select_stmt)).scalar_one_or_none()

    if lastVerifyCode is None:
        raise HTTPException(status_code=429, detail="请先获取验证码")

    # 十分钟内有效
    if lastVerifyCode.created_at < datetime.now() - timedelta(seconds=60 * 10):
        raise HTTPException(status_code=429, detail="验证码已过期")

    # 更新为已使用
    update_stmt = update(TurVerifyCodes).where(
        TurVerifyCodes.id == lastVerifyCode.id
    ).values(
        used_at=datetime.now(),
        is_used=True
    )

    await db.execute(update_stmt)
    await db.commit()


async def get_system_prompt(userquestion: str) -> str:
    # 获取嵌入
    vectors = await get_embedding(userquestion)

    if config.USE_CHROMADB:
        search_results = chroma_retrieved_knowledge(vectors)
        formatted_context = chroma_format_knowledge_for_prompt(search_results)
    else:
        raise
    # else:
    #     search_results = milvus_retrieved_knowledge(vectors)
    #     formatted_context = milvus_format_knowledge_for_prompt(search_results)


    # 定义你的系统提示词和最终的提示词模板
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
    """

    final_prompt = final_prompt_template.format(
        system_prompt=system_prompt,
        context=formatted_context if formatted_context else "无", # 如果上下文为空，明确告知模型
        user_question=userquestion
    )

    return final_prompt
