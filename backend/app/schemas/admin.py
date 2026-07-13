from pydantic import BaseModel


class HardResetRequest(BaseModel):
    confirm: bool = False


class HardResetResponse(BaseModel):
    status: str
    message: str
