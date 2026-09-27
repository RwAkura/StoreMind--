import os
import jwt


def get_user_id_from_token(authorization: str):
    if not authorization:
        raise ValueError("缺少authorization")

    try:
        payload = jwt.decode(
            authorization,
            os.getenv("JWT_SECRET"),
            algorithms=["HS384"]
        )
    except jwt.InvalidTokenError as e:
        raise ValueError(str(e))

    user_id = payload.get("userId")
    if not user_id:
        raise ValueError("authorization中不存在用户ID")
    return int(user_id)
