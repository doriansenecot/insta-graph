"""Pydantic models for API requests and responses."""

from pydantic import BaseModel
from typing import Optional
from enum import Enum


class JobStatus(str, Enum):
    """Job execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalyzeRequest(BaseModel):
    """Request to analyze an Instagram account."""
    username: str
    depth: int = 1

    class Config:
        json_schema_extra = {
            "example": {
                "username": "instagram",
                "depth": 2
            }
        }


class FollowerInfo(BaseModel):
    """Information about a filtered follower."""
    username: str
    full_name: str
    follower_count: int
    following_count: int
    is_private: bool
    depth: int


class JobResponse(BaseModel):
    """Response with job status and results."""
    job_id: str
    status: JobStatus
    target_username: str
    depth: int
    min_followers: int
    results: list[FollowerInfo] = []
    error: Optional[str] = None
    progress: Optional[str] = None
