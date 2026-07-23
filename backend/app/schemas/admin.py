from pydantic import BaseModel


class HardResetRequest(BaseModel):
    confirm: bool = False


class HardResetResponse(BaseModel):
    status: str
    message: str


class ReplayAdvanceRequest(BaseModel):
    turn: int  # experiment runner's cycle number, 1-indexed


class ReplayAdvanceResponse(BaseModel):
    turn: int
    prices: dict[str, str]
