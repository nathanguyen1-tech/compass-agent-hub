from pathlib import Path
from sqlmodel import SQLModel, Session, create_engine

BASE = Path(__file__).parent.parent.parent
DB_PATH = BASE / "agent_hub.db"
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False,
                        connect_args={"check_same_thread": False})


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
