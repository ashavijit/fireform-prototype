from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator

class IncidentType(str, Enum):
    STRUCTURE_FIRE = 'structure_fire'
    VEHICLE_FIRE = 'vehicle_fire'
    WILDLAND_FIRE = 'wildland_fire'
    MEDICAL = 'medical'
    HAZMAT = 'hazmat'
    RESCUE = 'rescue'
    FALSE_ALARM = 'false_alarm'
    SERVICE_CALL = 'service_call'
    OTHER = 'other'

class PropertyUse(str, Enum):
    RESIDENTIAL_1FAMILY = 'residential_1family'
    RESIDENTIAL_MULTI = 'residential_multi'
    COMMERCIAL = 'commercial'
    INDUSTRIAL = 'industrial'
    EDUCATIONAL = 'educational'
    HEALTHCARE = 'healthcare'
    STORAGE = 'storage'
    VEHICLE = 'vehicle'
    OUTDOOR = 'outdoor'
    OTHER = 'other'

class AlarmSource(str, Enum):
    AUTOMATIC = 'automatic_detector'
    MANUAL_PULL = 'manual_pull'
    PHONE_911 = 'phone_911'
    PASSERBY = 'passerby'
    CREW = 'crew_observed'
    OTHER = 'other'

class CasualtyRecord(BaseModel):
    civilian_injuries: int = Field(default=0, ge=0)
    civilian_fatalities: int = Field(default=0, ge=0)
    responder_injuries: int = Field(default=0, ge=0)
    responder_fatalities: int = Field(default=0, ge=0)
    treated_on_scene: bool = False

    @property
    def total_casualties(self) -> int:
        return self.civilian_injuries + self.civilian_fatalities + self.responder_injuries + self.responder_fatalities

class ResourceRecord(BaseModel):
    unit_id: str
    unit_type: str = ''
    personnel_count: int = Field(default=0, ge=0)
    arrived: bool = True

class IncidentReport(BaseModel):
    incident_type: IncidentType
    address: str = Field(min_length=3)
    narrative: str = Field(min_length=10)
    incident_number: Optional[str] = None
    date_time: Optional[datetime] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    property_use: Optional[PropertyUse] = None
    alarm_source: Optional[AlarmSource] = None
    occupants_rescued: int = Field(default=0, ge=0)
    area_of_origin: Optional[str] = None
    cause_of_ignition: Optional[str] = None
    contributing_factors: list[str] = Field(default_factory=list)
    estimated_loss_usd: Optional[float] = Field(default=None, ge=0)
    casualties: Optional[CasualtyRecord] = None
    resources: list[ResourceRecord] = Field(default_factory=list)

    @model_validator(mode='after')
    def check_casualty_vs_rescued(self) -> 'IncidentReport':
        if self.casualties and self.occupants_rescued:
            total_cas = self.casualties.total_casualties
            if total_cas > self.occupants_rescued + 10:
                pass
        return self

    class Config:
        use_enum_values = True
        json_encoders = {datetime: lambda v: v.isoformat()}