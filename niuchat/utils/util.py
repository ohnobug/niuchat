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
import database
from database import TurUsers, TurVerifyCodes
import random
from fastapi import HTTPException
import config
import schemas
from .llm import get_embedding
import pycountry
from langdetect import detect, LangDetectException
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


def get_language_name(text: str, default_lang: str = 'English') -> str:
    """
    检测输入文本的语言，并返回该语言的英文全称。
    
    例如:
    "Hello world" -> "English"
    "你好世界" -> "Chinese"
    "Bonjour le monde" -> "French"
    "Hola mundo" -> "Spanish"

    参数:
    text (str): 需要检测语言的文本字符串。
    default_lang (str): 如果检测失败或文本为空，返回的默认语言名称。

    返回:
    str: 检测到的语言的英文名称。
    """
    # 确保文本不为空
    if not text or not text.strip():
        return default_lang

    try:
        # 1. 使用 langdetect 检测语言代码
        lang_code = detect(text)
        
        # 2. 使用 pycountry 将语言代码转换为语言对象
        # langdetect 对中文的检测结果可能是 'zh-cn', 'zh-tw'，但 pycountry 需要两位代码 'zh'
        if lang_code.startswith('zh'):
            lang_code = 'zh'
            
        language = pycountry.languages.get(alpha_2=lang_code)
        
        # 3. 返回语言的官方英文名称
        if language:
            # 对于中文，直接返回 'Chinese' 可能更通用
            if language.name == 'Chinese':
                return 'Chinese'
            return language.name
        else:
            return default_lang
            
    except LangDetectException:
        # 如果 langdetect 无法可靠地检测出语言 (例如文本太短或太模糊)
        # print(f"Warning: Could not detect language for text: '{text[:50]}...'. Defaulting to {default_lang}.")
        return default_lang
    except Exception as e:
        # 捕获其他潜在错误
        # print(f"An unexpected error occurred during language detection: {e}")
        return default_lang
