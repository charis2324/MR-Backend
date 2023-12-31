from datetime import datetime, timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.security.utils import get_authorization_scheme_param

from mr_backend.database.db_manager import (
    add_login_code,
    create_user,
    get_user_by_username,
    get_username_if_active,
    update_user_uuid_if_active_and_none,
)

from .models import (
    LoginCode,
    LoginCodeResponse,
    LoginCodeSuccessResponse,
    Token,
    UserCreate,
    UserInDB,
)
from .security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from .utils import generate_random_string

LOGIN_CODE_LENGTH = 6
LOGIN_CODE_MAX_TRIES = 1000
LOGIN_CODE_EXPIRATION_MINUTES = 6

auth_router = APIRouter(prefix="/auth")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

active_login_code = set()


def is_authenticated_user(username, password) -> bool:
    user = get_user_by_username(username)
    if user == None:
        return False
    return verify_password(password, user.hashed_password)


def validate_token(token: str, creds_exception: HTTPException) -> tuple:
    payload = decode_access_token(token)

    if payload is None or payload.get("sub") is None:
        raise creds_exception

    user = get_user_by_username(payload.get("sub"))
    if user is None:
        raise creds_exception

    expiration_datetime = datetime.utcfromtimestamp(payload.get("exp"))
    if datetime.utcnow() > expiration_datetime:
        creds_exception.detail = "Token is expired"
        raise creds_exception

    user_in_db = UserInDB.model_validate(user, from_attributes=True)
    return user_in_db, expiration_datetime


def get_new_token_if_about_to_expire(
    user: dict, expiration_datetime: datetime
) -> Optional[str]:
    # Check if the token is about to expire
    if datetime.utcnow() + timedelta(minutes=60) > expiration_datetime:
        print("Token is about to expire")
        print(f"User: {user}")
        print(f" {type(user)}")
        # If the token is about to expire, create a new token
        new_token = create_access_token({"sub": user["username"]})
        return new_token
    return None


def validate_and_get_refresh_token(token: str, creds_exception: HTTPException) -> dict:
    print(f"validate_and_get_refresh_token token: {token}")
    user_in_db, expiration_datetime = validate_token(token, creds_exception)
    print(f"user_in_db: {user_in_db}")
    print(f"expiration_datetime: {expiration_datetime}")
    new_token = get_new_token_if_about_to_expire(user_in_db, expiration_datetime)

    return {"user": user_in_db, "new_token": new_token}


# def get_current_user(
#     token: Optional[Annotated[str, Depends(oauth2_scheme)]] = Cookie(
#         None, alias="access_token"
#     )
# ) -> dict:
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )
#     print(f"get_current_user token: {token}")
#     userId, _ = validate_token(token, credentials_exception)
#     return userId
async def get_token_from_header_or_cookie(request: Request) -> str:
    authorization: str = request.headers.get("Authorization")
    scheme, param = get_authorization_scheme_param(authorization)
    if scheme.lower() == "bearer":
        return param
    elif "access_token" in request.cookies:
        return request.cookies.get("access_token")
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(token: str = Depends(get_token_from_header_or_cookie)) -> dict:
    print(f"get_current_user token: {token}")
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    userId, _ = validate_token(token, credentials_exception)
    return userId


class UnauthorizedRedirectException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user_update_token_or_redirect(
    token: Optional[Annotated[str, Depends(oauth2_scheme)]] = Cookie(
        None, alias="access_token"
    )
) -> dict:
    return validate_and_get_refresh_token(token, UnauthorizedRedirectException())


def update_token_cookie(response: Response, token):
    response.set_cookie(key="access_token", value=token, httponly=True, path="/")


@auth_router.post("/token", response_model=Token)
def login_for_access_token(
    response: Response, form_data: OAuth2PasswordRequestForm = Depends()
):
    if not is_authenticated_user(form_data.username, form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": form_data.username})
    # Set the access token as a HTTPOnly cookie
    update_token_cookie(response, access_token)
    return {"access_token": access_token, "token_type": "bearer"}


@auth_router.get("/login-code", response_model=LoginCodeResponse)
def get_login_code():
    for _ in range(LOGIN_CODE_MAX_TRIES):
        if (
            login_code := generate_random_string(LOGIN_CODE_LENGTH)
        ) not in active_login_code:
            add_login_code(login_code, LOGIN_CODE_EXPIRATION_MINUTES)
            return LoginCodeResponse(
                login_code=login_code,
                expiration_duration=timedelta(minutes=LOGIN_CODE_EXPIRATION_MINUTES),
            )
    raise HTTPException(
        status_code=400,
        detail="Failed to generate login code.",
    )


@auth_router.post("/login-code/verify", response_model=LoginCodeSuccessResponse)
def verify_login_code(
    current_user: Annotated[UserInDB, Depends(get_current_user)],
    login_code_reponse: LoginCode,
):
    login_code = login_code_reponse.login_code
    user_uuid = current_user.uuid
    is_success = update_user_uuid_if_active_and_none(login_code, user_uuid)
    if not is_success:
        raise HTTPException(status_code=400, detail="Login code is not valid.")
    return LoginCodeSuccessResponse(
        login_code=login_code,
        user_uuid=user_uuid,
        detail="Login code verification succeeded.",
    )


@auth_router.post("/token-with-login-code")
def login_with_login_code_for_access_token(
    response: Response, login_code_reponse: LoginCode
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate login code.",
    )
    login_code = login_code_reponse.login_code
    username = get_username_if_active(login_code)
    if username is None:
        raise credentials_exception
    print(f"Login as {username} from login code.")
    access_token = create_access_token(data={"sub": username})
    update_token_cookie(response, access_token)
    return {"access_token": access_token, "token_type": "bearer"}


@auth_router.get("/logout")
def logout():
    response = RedirectResponse("/login")
    response.delete_cookie("access_token")
    return response


@auth_router.post("/register")
def register(new_user: UserCreate):
    hashed_password = get_password_hash(new_user.password)
    user = create_user(new_user.username, hashed_password)
    if user is None:
        raise HTTPException(status_code=400, detail="Username is already taken")
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "User registered successfully"},
    )
