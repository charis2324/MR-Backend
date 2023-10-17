from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from json import dumps


# Event format:
# event: updateUserInfo
# data: {"userId": 123, "username": "jdoe", "email": "jdoe@example.com"}
# \n\n
@dataclass
class ControllerEvent(ABC):
    event: str

    def __str__(self):
        return f"event: {self.event}\ndata: {self.data_as_json()}\n\n"

    def data_as_json(self):
        data = asdict(self)
        data.pop("event")
        return dumps(data)


@dataclass
class ImportFurnitureEvent(ControllerEvent):
    event: str = "importFurniture"
    furniture_uuid: str = None
