from datetime import datetime, timedelta
from gzip import compress, decompress
from io import BytesIO
from typing import List, Optional, Tuple
from uuid import uuid4

from icecream import ic
from joblib import dump, load
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    create_engine,
    event,
)
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import joinedload, relationship, sessionmaker
from sqlalchemy.sql import func
from trimesh import Trimesh

from mr_backend.app.models import TaskStatusEnum
from mr_backend.state import active_login_codes

from .db_scheduler import scheduler

# Define the SQLAlchemy's Base model to maintain catalog of classes and tables
Base = declarative_base()


class GenerationTask(Base):
    __tablename__ = "tasks"

    task_id = Column(String, ForeignKey("model_info.uuid"), primary_key=True)
    # model_uuid = Column(String, ForeignKey("model_info.uuid"))
    user_uuid = Column(String, ForeignKey("users.uuid"), nullable=False)
    prompt = Column(String, nullable=False)
    guidance_scale = Column(Float)
    estimated_duration = Column(Float)  # This is timedelta in seconds
    actual_duration = Column(Float)
    status = Column(Enum(TaskStatusEnum), index=True)
    created_at = Column(DateTime(timezone=False), default=datetime.now, index=True)
    completed_at = Column(DateTime(timezone=False), index=True)
    model_info = relationship(
        "ModelInfo", back_populates="generation_task", uselist=False
    )
    user = relationship("User", back_populates="tasks")


class ModelObj(Base):
    __tablename__ = "model_objs"

    uuid = Column(String, ForeignKey("model_info.uuid"), primary_key=True)
    trimesh = Column(LargeBinary)
    model_info = relationship("ModelInfo", back_populates="model_obj", uselist=False)


class ModelPreview(Base):
    __tablename__ = "model_previews"

    uuid = Column(String, ForeignKey("model_info.uuid"), primary_key=True)
    preview_file = Column(LargeBinary)
    preview_file_type = Column(String)
    status = Column(Enum(TaskStatusEnum))
    created_at = Column(DateTime(timezone=False), default=datetime.now, index=True)
    model_info = relationship(
        "ModelInfo", back_populates="model_preview", uselist=False
    )


class ModelInfo(Base):
    __tablename__ = "model_info"

    uuid = Column(String, primary_key=True)
    name = Column(String)
    user_uuid = Column(String, ForeignKey("users.uuid"), index=True)
    description = Column(String)
    scale_type = Column(Integer)
    scale_x = Column(Float)
    scale_y = Column(Float)
    scale_z = Column(Float)
    source = Column(String)
    model_preview = relationship(
        "ModelPreview", back_populates="model_info", uselist=False
    )
    model_obj = relationship("ModelObj", back_populates="model_info", uselist=False)
    generation_task = relationship(
        "GenerationTask", back_populates="model_info", uselist=False
    )
    user = relationship("User", back_populates="model_infos")


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}
    uuid = Column(String, primary_key=True)
    username = Column(String, unique=True)
    hashed_password = Column(String)
    created_at = Column(DateTime(timezone=False), default=datetime.now)
    model_infos = relationship("ModelInfo", back_populates="user")
    tasks = relationship("GenerationTask", back_populates="user")
    login_codes = relationship("LoginCode", back_populates="user")


class LoginCode(Base):
    __tablename__ = "login_code"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, index=True)
    user_uuid = Column(String, ForeignKey("users.uuid"), index=True)
    created_at = Column(DateTime(timezone=False))
    expire_at = Column(DateTime(timezone=False))
    is_active = Column(Boolean)
    user = relationship("User", back_populates="login_codes")


# Initialize the database
engine = create_engine("sqlite:///main_storage.db?check_same_thread=False", echo=False)
Base.metadata.create_all(engine)


SessionLocal = sessionmaker(bind=engine)


def get_all_active_login_codes_set(_):
    global active_login_codes
    print("Getting all active code.")
    db = SessionLocal()
    active_codes = db.query(LoginCode).filter(LoginCode.is_active == True).all()
    db.close()
    active_login_codes.replace({code.code for code in active_codes})
    ic(active_login_codes)


def check_and_schedule_codes(session):
    # Query active LoginCode instances
    active_codes = session.query(LoginCode).filter(LoginCode.is_active == True).all()

    for login_code in active_codes:
        if datetime.now() >= login_code.expire_at:
            # If the code is expired, update is_active to False
            login_code.is_active = False
        else:
            # If the code is not expired, schedule a job to deactivate it at expire_at
            scheduler.add_job(
                deactivate_code,
                "date",
                run_date=login_code.expire_at,
                args=[login_code.id],
            )

    # Commit any changes made during the session
    session.commit()


event.listen(SessionLocal, "after_commit", get_all_active_login_codes_set)


def get_username_if_active(code: str):
    db = SessionLocal()

    # Query the database for the LoginCode record with the given code
    login_code = db.query(LoginCode).join(User).filter(LoginCode.code == code).first()

    if login_code and login_code.is_active:
        # If the LoginCode record exists and is_active is True, store user.username
        username = login_code.user.username
    else:
        # If the LoginCode record does not exist or is not active, store None
        username = None
    db.close()

    return username


def update_user_uuid_if_active_and_none(code: str, new_user_uuid: str) -> bool:
    db = SessionLocal()

    # Query the database for the LoginCode record with the given code
    login_code = db.query(LoginCode).filter(LoginCode.code == code).first()

    if login_code and login_code.is_active and login_code.user_uuid is None:
        # If the LoginCode record exists, is_active is True, and user_uuid is None
        # Update user_uuid
        login_code.user_uuid = new_user_uuid
        db.commit()
        db.close()
        return True
    db.close()
    return False


def add_login_code(login_code: str, expire_duration_in_minutes: int):
    db = SessionLocal()
    try:
        expire_at = datetime.now() + timedelta(minutes=expire_duration_in_minutes)
        new_login_code = LoginCode(
            code=login_code,
            created_at=datetime.now(),
            expire_at=expire_at,
            is_active=True,
        )
        db.add(new_login_code)
        db.commit()
        generated_id = new_login_code.id
        # tell the scheduler to deactivate the code.
        scheduler.add_job(
            deactivate_code, "date", run_date=expire_at, args=[generated_id]
        )
    except:
        generated_id = None
        print("Failed to add login code.")
    finally:
        db.close()
    return generated_id


def deactivate_code(login_code_id: int):
    db = SessionLocal()
    login_code = db.query(LoginCode).get(login_code_id)
    if login_code:
        login_code.is_active = False
        db.commit()
    db.close()


def db_startup():
    # Run it once at start.
    session = SessionLocal()
    check_and_schedule_codes(session)
    session.close()


# Run it once at start.
db_startup()


def get_models_info(skip: int, limit: int) -> Tuple[Optional[List[ModelInfo]], int]:
    with SessionLocal() as db:
        try:
            total_rows = db.query(ModelInfo).count()
            models = (
                db.query(ModelInfo)
                .options(joinedload(ModelInfo.user))
                .offset(skip)
                .limit(limit)
                .all()
            )
            # Create a new list of dictionaries, each containing model information and the associated username
            models_with_username = []
            for model in models:
                model_dict = model.__dict__
                model_dict["username"] = model.user.username
                models_with_username.append(model_dict)

            return models_with_username, total_rows
        except Exception as e:
            print(f"An error occurred: {e}")
            return None, total_rows


def create_model_info(
    uuid: str,
    user_uuid: str,
    source: str,
    name: str = "",
    description: str = "",
    scale_type: int = 1,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    scale_z: float = 1.0,
):
    db = SessionLocal()
    new_model_info = ModelInfo(
        uuid=uuid,
        name=name,
        user_uuid=user_uuid,
        description=description,
        scale_type=scale_type,
        scale_x=scale_x,
        scale_y=scale_y,
        scale_z=scale_z,
        source=source,
    )

    db.add(new_model_info)
    db.commit()
    db.refresh(new_model_info)
    db.close()
    return new_model_info


def create_model_info_from_task(task_id: str):
    db = SessionLocal()
    # Retrieve the task
    task = db.query(GenerationTask).filter(GenerationTask.task_id == task_id).first()

    if task is not None:
        # Create a new ModelInfo object
        new_model_info = ModelInfo(
            uuid=task_id,
            name=task.prompt,
            user_uuid=task.user_uuid,
            scale_type=1,
            scale_x=1,
            scale_y=1,
            scale_z=1,
            source="AI",
        )

        # Add the new ModelInfo object to the session
        db.add(new_model_info)

        # Commit the session to write the changes to the database
        db.commit()
        db.close()
        return new_model_info
    else:
        db.close()
        return None


def get_model_preview_status(uuid: str):
    db = SessionLocal()
    model_preview = db.query(ModelPreview).filter(ModelPreview.uuid == uuid).first()
    db.close()
    if model_preview is not None:
        return model_preview.status
    else:
        return None


def get_task_user_uuid(task_id: str):
    db = SessionLocal()
    task = db.query(GenerationTask).filter(GenerationTask.task_id == task_id).first()
    db.close()
    if task is not None:
        return task.user_uuid
    else:
        return None


def create_user(username: str, hashed_password: str) -> User | None:
    db = SessionLocal()
    # Create a new user instance
    user = User(
        uuid=str(uuid4()),
        username=username,
        hashed_password=hashed_password,
    )
    try:
        # Add the new user to the session and commit
        db.add(user)
        db.commit()
    except IntegrityError:
        db.rollback()
        db.close()
        return None
    # Refresh the user instance to get any server-populated columns, then return it
    db.refresh(user)
    db.close()
    return user


def get_user_by_username(username):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).one()
        return user
    except:
        return None
    finally:
        db.close()


def add_task(
    task_id: str,
    user_uuid: str,
    prompt: str,
    guidance_scale: float,
    estimated_duration: timedelta,
):
    db = SessionLocal()

    # Create a new task
    task = GenerationTask(
        task_id=task_id,
        user_uuid=user_uuid,
        prompt=prompt,
        guidance_scale=guidance_scale,
        estimated_duration=estimated_duration.total_seconds(),
        status=TaskStatusEnum.waiting,
    )
    db.add(task)
    db.commit()
    db.close()


def finish_task(task_id: str, actual_duration: timedelta):
    db = SessionLocal()

    # Get the task
    task = db.query(GenerationTask).filter(GenerationTask.task_id == task_id).first()
    if task:
        # Update the actual duration and completed_at
        task.actual_duration = actual_duration.total_seconds()
        task.completed_at = datetime.now()  # Set completed_at to the current time
        task.status = TaskStatusEnum.completed
        db.commit()

    db.close()


def get_task_status(task_id: str):
    db = SessionLocal()
    # Get the task
    task = db.query(GenerationTask).filter(GenerationTask.task_id == task_id).first()
    if task:
        status = task.status
    else:
        status = None

    db.close()

    return status


def get_waiting_tasks_count():
    db = SessionLocal()

    # Count tasks with status 'waiting'
    waiting_count = (
        db.query(func.count())
        .filter(GenerationTask.status == TaskStatusEnum.waiting)
        .scalar()
    )

    db.close()

    return waiting_count


def get_actual_durations(n: int):
    db = SessionLocal()

    # Query for 'n' most recent tasks' actual durations
    durations = (
        db.query(GenerationTask.actual_duration)
        .filter(GenerationTask.actual_duration.isnot(None))
        .order_by(GenerationTask.completed_at.desc())
        .limit(n)
        .all()
    )

    db.close()

    # Unpack durations from result tuples and return as a list
    return [duration[0] for duration in durations]


def update_task_status(task_id: str, new_status: TaskStatusEnum):
    db = SessionLocal()

    try:
        # Get the task
        task = db.query(GenerationTask).filter(GenerationTask.task_id == task_id).one()

        # Update the status
        task.status = new_status

        # Commit the changes
        db.commit()

    except NoResultFound:
        print(f"No task found with id {task_id}")

    finally:
        db.close()


def get_earliest_waiting_task():
    db = SessionLocal()

    try:
        # Query for the task with the earliest 'created_at' and 'waiting' status
        task = (
            db.query(GenerationTask)
            .filter(GenerationTask.status == TaskStatusEnum.waiting)
            .order_by(GenerationTask.created_at)
            .first()
        )

        # Return the task, or None if no task was found
        return task

    except Exception as e:
        print(f"An error occurred: {str(e)}")

    finally:
        db.close()


def store_trimesh(uuid: str, trimesh: Trimesh):
    dump_buffer = BytesIO()
    dump(trimesh, dump_buffer, compress=("gzip", 3))
    dump_buffer.seek(0)
    db = SessionLocal()
    model = ModelObj(uuid=uuid, trimesh=dump_buffer.getvalue())
    db.add(model)
    db.commit()
    db.close()


def get_trimesh(uuid: str) -> Trimesh:
    db = SessionLocal()
    dump_buffer = db.query(ModelObj.trimesh).filter(ModelObj.uuid == uuid).one()[0]
    db.close()
    return load(BytesIO(dump_buffer))


def create_model_preview(uuid: str):
    db = SessionLocal()
    new_model_preview = ModelPreview(uuid=uuid, status=TaskStatusEnum.waiting)
    db.add(new_model_preview)
    db.commit()
    db.close()


def get_earliest_waiting_preview_uuid():
    db = SessionLocal()
    earliest_waiting_preview = (
        db.query(ModelPreview)
        .filter(ModelPreview.status == TaskStatusEnum.waiting)
        .order_by(ModelPreview.created_at.asc())
        .first()
    )
    db.close()
    if earliest_waiting_preview is not None:
        return earliest_waiting_preview.uuid
    else:
        return None


def update_model_preview_status(uuid: str, new_status: TaskStatusEnum):
    db = SessionLocal()
    model_preview = db.query(ModelPreview).filter(ModelPreview.uuid == uuid).first()
    if model_preview is not None:
        model_preview.status = new_status
        db.commit()
    else:
        print(f"No ModelPreview found with uuid: {uuid}")

    db.close()


def finish_model_preview(uuid: str, file_type: str, preview_file_bytes: bytes):
    db = SessionLocal()
    model_preview = db.query(ModelPreview).filter(ModelPreview.uuid == uuid).first()
    if model_preview is not None:
        model_preview.preview_file = preview_file_bytes
        model_preview.preview_file_type = file_type
        model_preview.status = TaskStatusEnum.completed
        db.commit()
    else:
        print(f"No ModelPreview found with uuid: {uuid}")
    db.close()


def get_preview_status(uuid: str):
    db = SessionLocal()
    # Get the task
    preview = db.query(ModelPreview).filter(ModelPreview.uuid == uuid).first()
    if preview:
        status = preview.status
    else:
        status = None

    db.close()

    return status


def get_preview(uuid: str):
    db = SessionLocal()
    preview_row = db.query(ModelPreview).filter(ModelPreview.uuid == uuid).one()
    db.close()
    return preview_row.preview_file, preview_row.preview_file_type
