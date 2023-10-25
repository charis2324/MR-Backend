from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from json import dumps


# Event format:
# event: updateUserInfo
# data: {"userId": 123, "username": "jdoe", "email": "jdoe@example.com"}
# \n\n
@dataclass
class SSEControllerEvent(ABC):
    event: str

    def __str__(self):
        return f"event: {self.event}\ndata: {self.data_as_json()}\n\n"

    def data_as_json(self):
        data = asdict(self)
        data.pop("event")
        return dumps(data)


@dataclass
class SSEImportFurnitureEvent(SSEControllerEvent):
    event: str = "importFurniture"
    furniture_uuid: str = None


@dataclass
class PollingControllerEvent(ABC):
    event_name: str

    def data_as_json(self):
        data = asdict(self)
        return dumps(data)

    def data_as_dict(self):
        return asdict(self)


@dataclass
class PollingImportFurnitureEvent(PollingControllerEvent):
    event_name: str = "importFurniture"
    furniture_uuid: str = None
