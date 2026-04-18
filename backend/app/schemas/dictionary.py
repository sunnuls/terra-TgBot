from pydantic import BaseModel


class ActivityOut(BaseModel):
    id: int
    name: str
    grp: str
    pos: int
    mode: str | None = None
    options: list[str] | None = None
    message: str | None = None
    model_config = {"from_attributes": True}


class ActivityCreate(BaseModel):
    name: str
    grp: str
    pos: int = 0
    mode: str | None = None
    options: list[str] | None = None
    message: str | None = None


class ActivityUpdate(BaseModel):
    name: str | None = None
    mode: str | None = None
    options: list[str] | None = None
    message: str | None = None


class LocationOut(BaseModel):
    id: int
    name: str
    grp: str
    pos: int
    mode: str | None = None
    options: list[str] | None = None
    message: str | None = None
    model_config = {"from_attributes": True}


class LocationCreate(BaseModel):
    name: str
    grp: str
    pos: int = 0
    mode: str | None = None
    options: list[str] | None = None
    message: str | None = None


class LocationUpdate(BaseModel):
    name: str | None = None
    mode: str | None = None
    options: list[str] | None = None
    message: str | None = None


class MachineKindOut(BaseModel):
    id: int
    title: str
    mode: str
    pos: int
    options: list[str] | None = None
    message: str | None = None
    model_config = {"from_attributes": True}


class MachineKindCreate(BaseModel):
    title: str
    mode: str = "list"
    pos: int = 0
    options: list[str] | None = None
    message: str | None = None


class MachineKindUpdate(BaseModel):
    title: str | None = None
    mode: str | None = None
    options: list[str] | None = None
    message: str | None = None


class MachineItemOut(BaseModel):
    id: int
    kind_id: int
    name: str
    pos: int
    model_config = {"from_attributes": True}


class MachineItemCreate(BaseModel):
    kind_id: int
    name: str
    pos: int = 0


class CropOut(BaseModel):
    name: str
    pos: int
    mode: str | None = None
    options: list[str] | None = None
    message: str | None = None
    model_config = {"from_attributes": True}


class CropCreate(BaseModel):
    name: str
    pos: int = 0
    mode: str | None = None
    options: list[str] | None = None
    message: str | None = None


class CropUpdate(BaseModel):
    name: str | None = None
    mode: str | None = None
    options: list[str] | None = None
    message: str | None = None


class CustomDictItemOut(BaseModel):
    id: int
    dict_id: int
    value: str
    pos: int
    mode: str | None = None
    options: list[str] | None = None
    message: str | None = None
    model_config = {"from_attributes": True}


class CustomDictItemCreate(BaseModel):
    dict_id: int
    value: str
    pos: int = 0
    mode: str | None = None
    options: list[str] | None = None
    message: str | None = None


class CustomDictItemUpdate(BaseModel):
    mode: str | None = None
    options: list[str] | None = None
    message: str | None = None


class CustomDictOut(BaseModel):
    id: int
    name: str
    pos: int
    items: list[CustomDictItemOut] = []
    model_config = {"from_attributes": True}


class CustomDictCreate(BaseModel):
    name: str
    pos: int = 0


class CustomDictUpdate(BaseModel):
    name: str | None = None


class DictionariesOut(BaseModel):
    activities: list[ActivityOut]
    locations: list[LocationOut]
    machine_kinds: list[MachineKindOut]
    machine_items: list[MachineItemOut]
    crops: list[CropOut]
    custom_dicts: list[CustomDictOut] = []


class ReorderRequest(BaseModel):
    ids: list[int]
