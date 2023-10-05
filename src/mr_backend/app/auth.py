from typing import Annotated, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from fastapi.responses import Request, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from mr_backend.database.db_manager import get_user_by_username

from .models import Token, UserInDB
from .security import create_access_token, decode_access_token, verify_password

auth_router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def is_authenticated_user(username, password) -> bool:
    user = get_user_by_username(username)
    if user == None:
        return False
    return verify_password(password, user.hashed_password)


def get_current_user(
    token: Optional[Annotated[str, Depends(oauth2_scheme)]] = Cookie(
        None, alias="access_token"
    )
) -> UserInDB:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    username = decode_access_token(token)
    if username is None:
        raise credentials_exception

    user = get_user_by_username(username)
    if user is None:
        raise credentials_exception
    return UserInDB.model_validate(user, from_attributes=True)


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
    response.set_cookie(key="access_token", value=access_token, httponly=True, path="/")
    return {"access_token": access_token, "token_type": "bearer"}
