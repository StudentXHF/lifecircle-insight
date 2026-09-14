from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Coordinate(BaseModel):
    lng: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)


class AnalysisRequest(BaseModel):
    mode: Literal['demo', 'real'] = 'demo'
    center: Coordinate
    center_name: str = Field(default='中心点', max_length=80)
    city: str = Field(default='上海市', max_length=40)
    coord_type: Literal['bd09ll', 'gcj02', 'wgs84'] = 'bd09ll'
    threshold_minutes: int = Field(default=15, ge=5, le=30)
    sample_bearings: int = Field(default=16, ge=8, le=32)
    poi_radius_meters: int = Field(default=1800, ge=800, le=3000)

    @field_validator('center_name', 'city')
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip() or '未命名'


class GeocodeRequest(BaseModel):
    address: str = Field(min_length=2, max_length=120)
    city: str = Field(default='上海市', max_length=40)


class CoordinateConvertRequest(BaseModel):
    points: list[Coordinate] = Field(min_length=1, max_length=100)
    source: Literal['gcj02', 'wgs84']
