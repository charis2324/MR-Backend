from datetime import datetime, timedelta
from gzip import compress, decompress

from sqlalchemy import Column, DateTime, Enum, Float, LargeBinary, String, create_engine
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from mr_backend.app.models import TaskStatusEnum

from joblib import load, dump
from io import BytesIO
from trimesh import Trimesh

# Define the SQLAlchemy's Base model to maintain catalog of classes and tables
Base = declarative_base()


# Defining the GenerationTask model
class GenerationTask(Base):
    __tablename__ = "tasks"

    task_id = Column(String, primary_key=True)
    prompt = Column(String)
    guidance_scale = Column(Float)
    estimated_duration = Column(Float)  # This is timedelta in seconds
    actual_duration = Column(Float)
    status = Column(Enum(TaskStatusEnum), index=True)
    created_at = Column(
        DateTime(timezone=False), default=datetime.now, index=True
    )  # To know when each task was created
    completed_at = Column(DateTime(timezone=False), index=True)


class ModelObj(Base):
    __tablename__ = "models"
    uuid = Column(String, primary_key=True)
    trimesh = Column(LargeBinary)


class ModelPreview(Base):
    __tablename__ = "model_previews"
    uuid = Column(String, primary_key=True)
    preview_file = Column(LargeBinary)
    preview_file_type = Column(String)
    status = Column(Enum(TaskStatusEnum))
    created_at = Column(DateTime(timezone=False), default=datetime.now, index=True)


# Initialize the database
engine = create_engine("sqlite:///main_storage.db?check_same_thread=False", echo=False)
Base.metadata.create_all(engine)

SessionLocal = sessionmaker(bind=engine)


def add_task(
    task_id: str, prompt: str, guidance_scale: float, estimated_duration: timedelta
):
    db = SessionLocal()

    # Create a new task
    task = GenerationTask(
        task_id=task_id,
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
