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
import schemas

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


# 得到token
# def get_token(userInfo: TurUsers):
#     return SimpleCrypto.encrypt(json.dumps({
#         "id": userInfo.id,
#         "phone_number": userInfo.phone_number
#         # "expire": int((datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp())
#     }))



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

    result = await db.execute(update_stmt)
    await db.commit()
