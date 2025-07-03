# crawler.py
import httpx
import re
from typing import List, Optional
from models import Apartment
from sqlmodel import Session, select
from database import engine
import logging

logger = logging.getLogger(__name__)

class SrealityCrawler:
    def __init__(self):
        self.base_url = "https://www.sreality.cz/api/cs/v2/estates"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def extract_size_and_layout(self, name: str) -> tuple[Optional[int], Optional[str]]:
        """Extract size in m² and room layout from apartment name"""
        # Extract size (e.g., "35 m²")
        size_match = re.search(r'(\d+)\s*m²', name)
        size_sqm = int(size_match.group(1)) if size_match else None

        # Extract room layout (e.g., "1+kk", "2+1")
        layout_match = re.search(r'(\d+\+\w+)', name)
        room_layout = layout_match.group(1) if layout_match else None

        return size_sqm, room_layout

    def is_prague_locality(self, locality: str) -> bool:
        """Check if locality is in Prague"""
        prague_keywords = ["Praha", "Prague", "Praze"]
        return any(keyword in locality for keyword in prague_keywords)

    def has_garage(self, labels: List[str], labels_all: List[List[str]]) -> bool:
        """Check if apartment has garage"""
        garage_keywords = ["garage", "Garáž", "Parkování", "parking_lots"]

        # Check in main labels
        for label in labels:
            if any(keyword.lower() in label.lower() for keyword in garage_keywords):
                return True

        # Check in all labels
        for label_group in labels_all:
            for label in label_group:
                if any(keyword.lower() in label.lower() for keyword in garage_keywords):
                    return True

        return False

    def extract_images(self, links: dict) -> List[str]:
        """Extract image URLs from _links"""
        images = []
        if "images" in links:
            for image_link in links["images"]:
                images.append(image_link["href"])
        return images

    async def fetch_apartments(self, page: int = 1) -> Optional[dict]:
        """Fetch apartments from sreality API"""
        params = {
            "category_sub_cb": "2",  # Apartments
            "category_type_cb": "2",  # Rent
            "page": page
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    self.base_url,
                    params=params,
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.RequestError as e:
            logger.error(f"Request failed: {e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e}")
            return None

    async def crawl_and_save_apartments(self) -> List[Apartment]:
        """Main crawling function"""
        new_apartments = []

        # Fetch first page to get total results
        data = await self.fetch_apartments(page=1)
        if not data:
            logger.error("Failed to fetch data from sreality")
            return new_apartments

        estates = data.get("_embedded", {}).get("estates", [])

        with Session(engine) as session:
            for estate_data in estates:
                # Check if locality is Prague
                locality = estate_data.get("locality", "")
                if not self.is_prague_locality(locality):
                    continue

                hash_id = estate_data.get("hash_id")
                if not hash_id:
                    continue

                # Check if apartment already exists
                existing = session.exec(
                    select(Apartment).where(Apartment.hash_id == hash_id)
                ).first()

                if existing:
                    continue  # Skip if already exists

                # Extract apartment data
                name = estate_data.get("name", "")
                price = estate_data.get("price", 0)
                price_unit = estate_data.get("price_czk", {}).get("unit", "za měsíc")

                # Extract size and room layout
                size_sqm, room_layout = self.extract_size_and_layout(name)

                # Check for garage
                labels = estate_data.get("labels", [])
                labels_all = estate_data.get("labelsAll", [])
                has_garage_flag = self.has_garage(labels, labels_all)

                # Extract GPS coordinates
                gps = estate_data.get("gps", {})
                latitude = gps.get("lat")
                longitude = gps.get("lon")

                # Extract images
                images = self.extract_images(estate_data.get("_links", {}))

                # Create apartment object
                apartment = Apartment(
                    hash_id=hash_id,
                    name=name,
                    price=price,
                    price_unit=price_unit,
                    locality=locality,
                    size_sqm=size_sqm,
                    room_layout=room_layout,
                    has_garage=has_garage_flag,
                    latitude=latitude,
                    longitude=longitude,
                    images=images
                )

                session.add(apartment)
                new_apartments.append(apartment)
                logger.info(f"Added new apartment: {name} in {locality}")

            session.commit()

        return new_apartments