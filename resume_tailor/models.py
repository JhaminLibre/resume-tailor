from pydantic import BaseModel, Field
from typing import Optional


class ContactInfo(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None


class ExperienceEntry(BaseModel):
    company: str
    title: str
    location: Optional[str] = None
    start_date: str
    end_date: Optional[str] = None
    bullets: list[str]
    tags: list[str] = Field(default_factory=list)


class EducationEntry(BaseModel):
    institution: str
    degree: str
    field_of_study: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    gpa: Optional[str] = None
    honors: list[str] = Field(default_factory=list)


class SkillCategory(BaseModel):
    name: str
    items: list[str]


class Certification(BaseModel):
    name: str
    issuer: Optional[str] = None
    date: Optional[str] = None


class Project(BaseModel):
    name: str
    description: Optional[str] = None
    bullets: list[str] = Field(default_factory=list)
    url: Optional[str] = None


class Resume(BaseModel):
    contact: ContactInfo
    summary: str
    experience: list[ExperienceEntry]
    education: list[EducationEntry]
    skills: list[SkillCategory]
    certifications: list[Certification] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)

    model_config = {"title": "Resume"}


class MatchResult(BaseModel):
    match_score: int = Field(ge=0, le=100)
    summary: str
    strengths: list[str]
    gaps: list[str]
