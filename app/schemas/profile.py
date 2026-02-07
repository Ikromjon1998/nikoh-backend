from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Gender(str, Enum):
    male = "male"
    female = "female"


class Build(str, Enum):
    slim = "slim"
    average = "average"
    athletic = "athletic"
    muscular = "muscular"
    curvy = "curvy"
    heavy = "heavy"


class Ethnicity(str, Enum):
    uzbek = "uzbek"
    kazakh = "kazakh"
    tajik = "tajik"
    kyrgyz = "kyrgyz"
    turkmen = "turkmen"
    tatar = "tatar"
    uyghur = "uyghur"
    afghan = "afghan"
    mixed = "mixed"
    other = "other"


class ReligiousPractice(str, Enum):
    central_to_life = "central_to_life"
    important = "important"
    cultural_identity = "cultural_identity"
    family_heritage = "family_heritage"
    journey = "journey"


class Smoking(str, Enum):
    never = "never"
    quit = "quit"
    occasionally = "occasionally"
    regularly = "regularly"


class Alcohol(str, Enum):
    never = "never"
    rarely_special = "rarely_special"
    socially = "socially"


class Diet(str, Enum):
    halal_only = "halal_only"
    generally_halal = "generally_halal"
    no_restrictions = "no_restrictions"


class LivingSituation(str, Enum):
    alone = "alone"
    with_family = "with_family"
    with_roommates = "with_roommates"


class ResidenceStatus(str, Enum):
    citizen = "citizen"
    permanent_resident = "permanent_resident"
    temporary_resident = "temporary_resident"
    student = "student"
    other = "other"


class MaritalStatus(str, Enum):
    never_married = "never_married"
    divorced_once = "divorced_once"
    divorced_twice = "divorced_twice"
    divorced_multiple = "divorced_multiple"
    widowed = "widowed"


class LanguageProficiency(BaseModel):
    language: str
    proficiency: str  # native, fluent, conversational, basic


class ProfileCreate(BaseModel):
    gender: Gender
    seeking_gender: Gender

    height_cm: int | None = Field(None, ge=100, le=250)
    weight_kg: int | None = Field(None, ge=30, le=300)
    build: Build | None = None

    ethnicity: Ethnicity | None = None
    ethnicity_other: str | None = Field(None, max_length=100)
    languages: list[LanguageProficiency] = []
    original_region: str | None = Field(None, max_length=200)
    current_city: str | None = Field(None, max_length=200)
    living_situation: LivingSituation | None = None

    religious_practice: ReligiousPractice | None = None

    smoking: Smoking | None = None
    alcohol: Alcohol | None = None
    diet: Diet | None = None

    profession: str | None = Field(None, max_length=200)
    hobbies: list[str] = []

    about_me: str | None = Field(None, max_length=1500)
    family_meaning: str | None = Field(None, max_length=1000)
    ideal_partner: str | None = Field(None, max_length=1000)
    goals_dreams: str | None = Field(None, max_length=1000)
    message_to_family: str | None = Field(None, max_length=800)


class ProfileUpdate(BaseModel):
    height_cm: int | None = Field(None, ge=100, le=250)
    weight_kg: int | None = Field(None, ge=30, le=300)
    build: Build | None = None

    ethnicity: Ethnicity | None = None
    ethnicity_other: str | None = Field(None, max_length=100)
    languages: list[LanguageProficiency] | None = None
    original_region: str | None = Field(None, max_length=200)
    current_city: str | None = Field(None, max_length=200)
    living_situation: LivingSituation | None = None

    religious_practice: ReligiousPractice | None = None

    smoking: Smoking | None = None
    alcohol: Alcohol | None = None
    diet: Diet | None = None

    profession: str | None = Field(None, max_length=200)
    hobbies: list[str] | None = None

    about_me: str | None = Field(None, max_length=1500)
    family_meaning: str | None = Field(None, max_length=1000)
    ideal_partner: str | None = Field(None, max_length=1000)
    goals_dreams: str | None = Field(None, max_length=1000)
    message_to_family: str | None = Field(None, max_length=800)

    is_visible: bool | None = None


class ProfileResponse(BaseModel):
    id: UUID
    user_id: UUID

    # Verified info
    verified_first_name: str | None
    verified_last_initial: str | None
    verified_birth_date: date | None
    verified_birthplace_country: str | None
    verified_birthplace_city: str | None
    verified_nationality: str | None
    verified_residence_country: str | None
    verified_residence_status: str | None
    verified_marital_status: str | None
    verified_education_level: str | None

    # Self-declared
    gender: str
    seeking_gender: str
    height_cm: int | None
    weight_kg: int | None
    build: str | None
    ethnicity: str | None
    ethnicity_other: str | None
    languages: list[dict]
    original_region: str | None
    current_city: str | None
    living_situation: str | None
    religious_practice: str | None
    smoking: str | None
    alcohol: str | None
    diet: str | None
    profession: str | None
    hobbies: list[str]
    about_me: str | None
    family_meaning: str | None
    ideal_partner: str | None
    goals_dreams: str | None
    message_to_family: str | None

    is_visible: bool
    is_complete: bool
    profile_score: int

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProfileBrief(BaseModel):
    id: UUID
    user_id: UUID
    verified_first_name: str | None
    verified_last_initial: str | None
    verified_birth_date: date | None
    verified_residence_country: str | None
    gender: str
    ethnicity: str | None
    current_city: str | None
    religious_practice: str | None
    profession: str | None
    is_complete: bool
    profile_score: int

    model_config = ConfigDict(from_attributes=True)


class ProfileSearch(BaseModel):
    seeking_gender: Gender | None = None
    min_age: int | None = Field(None, ge=18, le=100)
    max_age: int | None = Field(None, ge=18, le=100)
    ethnicities: list[Ethnicity] | None = None
    residence_countries: list[str] | None = None
    religious_practices: list[ReligiousPractice] | None = None
    min_height_cm: int | None = None
    max_height_cm: int | None = None

    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)


class ProfileSearchResponse(BaseModel):
    profiles: list[ProfileBrief]
    total: int
    page: int
    per_page: int
