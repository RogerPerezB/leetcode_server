import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Cache
cache = {
    "latest_submission": None,
    "last_updated": None
}

USERNAME = os.getenv("LEETCODE_USERNAME")

# Fetcher
async def fetch_leetcode_data():
    url = "https://leetcode.com/graphql"
    query = """
    query getRecentSubmissionList($username: String!, $limit: Int!) {
      recentSubmissionList(username: $username, limit: $limit) {
        title
        titleSlug
        timestamp
        statusDisplay
        lang
      }
    }
    """
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url,
                json={"query": query, "variables": {"username": USERNAME, "limit": 1}}
            )
            data = response.json()
            submissions = data.get("data", {}).get("recentSubmissionList", [])
            
            accepted = [sub for sub in submissions if sub["statusDisplay"] == "Accepted"]
            if accepted:
                cache["latest_submission"] = accepted[0]
                cache["last_updated"] = datetime.now().isoformat()
                print(f"Cache updated with: {accepted[0]['title']}")
        except Exception as e:
            print(f"Failed to fetch LeetCode data: {e}")

# Background Scheduler
@asynccontextmanager
async def lifespan(app: FastAPI):
    await fetch_leetcode_data()
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(fetch_leetcode_data, 'interval', hours=2)
    scheduler.start()
    
    yield 
    
    scheduler.shutdown()

# CORS
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# API endpoint
@app.get("/api/leetcode/latest")
async def get_latest_leetcode():
    if not cache["latest_submission"]:
        raise HTTPException(status_code=503, detail="Cache warming up or LeetCode unavailable.")
    
    return {
        "source": "cache",
        "last_updated": cache["last_updated"],
        "data": cache["latest_submission"],
        "url": f"https://leetcode.com/problems/{cache['latest_submission']['titleSlug']}"
    }