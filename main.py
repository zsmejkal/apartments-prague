# main.py
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from typing import List, Optional
import asyncio
from datetime import datetime, timedelta

from models import Apartment, ApartmentResponse
from database import create_db_and_tables, get_session
from crawler import SrealityCrawler

app = FastAPI(title="Prague Apartments Crawler", version="1.0.0")

# Add CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://192.168.0.192:3000"],  # React default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize crawler
crawler = SrealityCrawler()

# Background task for periodic crawling
async def periodic_crawl():
    """Background task that runs every minute"""
    while True:
        try:
            new_apartments = await crawler.crawl_and_save_apartments()
            print(f"Crawled {len(new_apartments)} new apartments at {datetime.now()}")
        except Exception as e:
            print(f"Error during crawling: {e}")

        # Wait 1 minute
        await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    create_db_and_tables()
    # Start background crawling task
    asyncio.create_task(periodic_crawl())

@app.get("/")
async def root():
    return {"message": "Prague Apartments Crawler API"}

@app.get("/apartments/", response_model=List[ApartmentResponse])
async def get_apartments(
        skip: int = 0,
        limit: int = 20,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        has_garage: Optional[bool] = None,
        room_layout: Optional[str] = None,
        session: Session = Depends(get_session)
):
    """Get apartments with optional filters"""
    query = select(Apartment)

    # Apply filters
    if min_price is not None:
        query = query.where(Apartment.price >= min_price)
    if max_price is not None:
        query = query.where(Apartment.price <= max_price)
    if min_size is not None:
        query = query.where(Apartment.size_sqm >= min_size)
    if max_size is not None:
        query = query.where(Apartment.size_sqm <= max_size)
    if has_garage is not None:
        query = query.where(Apartment.has_garage == has_garage)
    if room_layout is not None:
        query = query.where(Apartment.room_layout == room_layout)

    # Order by date created (newest first)
    query = query.order_by(Apartment.date_created.desc())

    # Apply pagination
    query = query.offset(skip).limit(limit)

    apartments = session.exec(query).all()
    return apartments

@app.get("/apartments/{apartment_id}", response_model=ApartmentResponse)
async def get_apartment(apartment_id: int, session: Session = Depends(get_session)):
    """Get specific apartment by ID"""
    apartment = session.get(Apartment, apartment_id)
    if not apartment:
        raise HTTPException(status_code=404, detail="Apartment not found")
    return apartment

@app.get("/apartments/new/", response_model=List[ApartmentResponse])
async def get_new_apartments(
        hours: int = 24,
        session: Session = Depends(get_session)
):
    """Get apartments added in the last N hours"""
    cutoff_time = datetime.now() - timedelta(hours=hours)

    query = select(Apartment).where(
        Apartment.date_created >= cutoff_time
    ).order_by(Apartment.date_created.desc())

    apartments = session.exec(query).all()
    return apartments

@app.post("/crawl/trigger")
async def trigger_crawl(background_tasks: BackgroundTasks):
    """Manually trigger crawling"""
    background_tasks.add_task(crawler.crawl_and_save_apartments)
    return {"message": "Crawling triggered"}

@app.get("/stats/")
async def get_stats(session: Session = Depends(get_session)):
    """Get basic statistics"""
    total_apartments = session.exec(select(Apartment)).all()

    total_count = len(total_apartments)
    avg_price = sum(apt.price for apt in total_apartments) / total_count if total_count > 0 else 0
    avg_size = sum(apt.size_sqm for apt in total_apartments if apt.size_sqm) / len([apt for apt in total_apartments if apt.size_sqm]) if total_apartments else 0

    return {
        "total_apartments": total_count,
        "average_price": round(avg_price, 2),
        "average_size": round(avg_size, 2),
        "apartments_with_garage": len([apt for apt in total_apartments if apt.has_garage])
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)