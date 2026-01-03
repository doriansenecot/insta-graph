"""FastAPI application for Instagram followers scraper."""

import uuid
import json
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
import redis

from app.config import get_settings
from app.models import AnalyzeRequest, JobResponse, JobStatus, FollowerInfo
from app.scraper import InstagramScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
redis_client: Optional[redis.Redis] = None
scraper: Optional[InstagramScraper] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global redis_client, scraper
    
    settings = get_settings()
    
    # Initialize Redis
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    logger.info("Connected to Redis")
    
    # Initialize scraper
    scraper = InstagramScraper()
    if not scraper.login():
        logger.warning("Instagram login failed - scraping will not work")
    
    yield
    
    # Cleanup
    if redis_client:
        redis_client.close()


app = FastAPI(
    title="Instagram Followers Scraper",
    description="Microservice to analyze Instagram followers with depth-based filtering",
    version="1.0.0",
    lifespan=lifespan
)


def get_job(job_id: str) -> Optional[dict]:
    """Get job from Redis."""
    data = redis_client.get(f"job:{job_id}")
    return json.loads(data) if data else None


def save_job(job_id: str, job_data: dict):
    """Save job to Redis."""
    redis_client.set(f"job:{job_id}", json.dumps(job_data))


def run_analysis(job_id: str, username: str, depth: int):
    """Background task to run the analysis."""
    settings = get_settings()
    
    job = get_job(job_id)
    job["status"] = JobStatus.RUNNING.value
    save_job(job_id, job)
    
    def on_progress(msg: str):
        job = get_job(job_id)
        job["progress"] = msg
        save_job(job_id, job)
    
    try:
        results = scraper.analyze_recursive(
            username=username,
            max_depth=depth,
            min_followers=settings.min_followers,
            on_progress=on_progress
        )
        
        job = get_job(job_id)
        job["status"] = JobStatus.COMPLETED.value
        job["results"] = [r.model_dump() for r in results]
        job["progress"] = f"Completed: found {len(results)} accounts"
        save_job(job_id, job)
        
        logger.info(f"Job {job_id} completed with {len(results)} results")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        job = get_job(job_id)
        job["status"] = JobStatus.FAILED.value
        job["error"] = str(e)
        save_job(job_id, job)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/analyze", response_model=JobResponse)
async def create_analysis(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    """
    Start a new follower analysis job.
    
    Returns a job_id that can be used to poll for results.
    """
    settings = get_settings()
    
    # Validate depth
    if request.depth < 1 or request.depth > settings.max_depth:
        raise HTTPException(
            status_code=400,
            detail=f"Depth must be between 1 and {settings.max_depth}"
        )
    
    # Create job
    job_id = str(uuid.uuid4())
    job_data = {
        "job_id": job_id,
        "status": JobStatus.PENDING.value,
        "target_username": request.username,
        "depth": request.depth,
        "min_followers": settings.min_followers,
        "results": [],
        "error": None,
        "progress": "Job created, waiting to start"
    }
    save_job(job_id, job_data)
    
    # Start background task
    background_tasks.add_task(run_analysis, job_id, request.username, request.depth)
    
    return JobResponse(**job_data)


@app.get("/analyze/{job_id}", response_model=JobResponse)
async def get_analysis(job_id: str):
    """Get the status and results of an analysis job."""
    job = get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Convert results back to FollowerInfo objects
    job["results"] = [FollowerInfo(**r) for r in job.get("results", [])]
    
    return JobResponse(**job)
