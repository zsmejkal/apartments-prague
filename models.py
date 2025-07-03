# models.py
from datetime import datetime
from enum import Enum
from typing import Optional, List
from sqlmodel import Field, SQLModel, Column, JSON
from sqlalchemy import Text, DateTime

class Apartment(SQLModel, table=True):
    __tablename__ = "apartments"

    id: Optional[int] = Field(default=None, primary_key=True)
    hash_id: int = Field(unique=True, index=True)  # Original hash_id from API
    name: str
    price: int
    price_unit: str = Field(default="za měsíc")
    locality: str
    size_sqm: Optional[int] = Field(default=None)  # Size in square meters
    room_layout: Optional[str] = Field(default=None)  # e.g., "1+kk"
    has_garage: bool = Field(default=False)
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    images: List[str] = Field(sa_column=Column(JSON))  # Store image URLs as JSON
    date_created: datetime = Field(default_factory=datetime.now)
    date_updated: datetime = Field(default_factory=datetime.now)

    class Config:
        arbitrary_types_allowed = True

class ApartmentResponse(SQLModel):
    id: int
    hash_id: int
    name: str
    price: int
    price_unit: str
    locality: str
    size_sqm: Optional[int]
    room_layout: Optional[str]
    has_garage: bool
    latitude: Optional[float]
    longitude: Optional[float]
    images: List[str]
    date_created: datetime
    date_updated: datetime