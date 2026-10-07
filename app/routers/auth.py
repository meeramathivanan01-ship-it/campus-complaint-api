import logging

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import TokenResponse, UserCreate, UserLogin, UserResponse
from app.security import create_access_token


router = APIRouter()
logger = logging.getLogger(__name__)
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserCreate, db: Session = Depends(get_db)) -> User:
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user is not None:
        logger.warning("User registration rejected: duplicate email")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )

    user = User(
        name=user_data.name,
        email=user_data.email,
        password=password_context.hash(user_data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("User registration succeeded (user_id=%s)", user.id)
    return user


@router.post("/login", response_model=TokenResponse)
def login_user(credentials: UserLogin, db: Session = Depends(get_db)) -> dict[str, str]:
    user = db.query(User).filter(User.email == credentials.email).first()
    if user is None or not password_context.verify(credentials.password, user.password):
        logger.warning("User login failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    logger.info("User login succeeded (user_id=%s)", user.id)
    return {
        "access_token": create_access_token(user.id, user.role),
        "token_type": "bearer",
    }
import logging
