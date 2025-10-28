from random import randint
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import create_engine, Integer, Column, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from dotenv import load_dotenv
import os
from datetime import datetime, timezone
import requests
from PIL import Image, ImageDraw, ImageFont

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
CACHE_DIR = "cache"
IMAGE_PATH = f"{CACHE_DIR}/summary.png"
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)
Base = declarative_base()

# Updated Country model with correct field name
class Country(Base):
    __tablename__ = "countries"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    capital = Column(String(255), nullable=True)
    region = Column(String(255), nullable=True)
    population = Column(Integer, nullable=False)
    currency_code = Column(String(10), nullable=True)  # Allow null per requirement
    exchange_rate = Column(Float, nullable=True)       # Allow null per requirement
    estimated_gdp = Column(Float, nullable=True)       # Allow null per requirement
    flag_url = Column(String(255), nullable=True)
    last_refreshed_at = Column(DateTime, default=datetime.now(timezone.utc),
                               onupdate=datetime.now(timezone.utc))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.post("/countries/refresh")
def refresh_countries(db: Session = Depends(get_db)):
    try:
        # Fetch country data
        countries_response = requests.get(
            "https://restcountries.com/v2/all?fields=name,capital,region,population,flag,currencies", timeout=10)
        countries_response.raise_for_status()
        countries_data = countries_response.json()
    except requests.exceptions.RequestException:
        raise HTTPException(status_code=503, detail={
            "error": "External data source unavailable",
            "details": "Could not fetch data from restcountries.com"
        })

    try:
        # Fetch exchange rates
        rates_response = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        rates_response.raise_for_status()
        rates_data = rates_response.json()
        exchange_rates = rates_data.get("rates", {})
    except requests.exceptions.RequestException:
        raise HTTPException(status_code=503, detail={
            "error": "External data source unavailable",
            "details": "Could not fetch data from open.er-api.com"
        })

    # Process countries within a transaction
    try:
        for country_data in countries_data:
            name = country_data.get("name")
            population = country_data.get("population")
            capital = country_data.get("capital")
            region = country_data.get("region")
            flag_url = country_data.get("flag")
            currencies = country_data.get("currencies", [])

            # Validate required fields
            if not name:
                raise HTTPException(status_code=400, detail={
                    "error": "Validation failed",
                    "details": {"name": "is required"}
                })
            if population is None:
                raise HTTPException(status_code=400, detail={
                    "error": "Validation failed",
                    "details": {"population": "is required"}
                })

            currency_code = None
            exchange_rate = None
            estimated_gdp = 0.0

            if currencies:
                currency_code = currencies[0].get("code")
                if not currency_code:
                    raise HTTPException(status_code=400, detail={
                        "error": "Validation failed",
                        "details": {"currency_code": "is required"}
                    })
                rate = exchange_rates.get(currency_code)
                if rate:
                    exchange_rate = rate
                    random_multiplier = randint(1000, 2000)
                    estimated_gdp = (population * random_multiplier) / exchange_rate

            existing_country = db.query(Country).filter(Country.name.ilike(name)).first()
            if existing_country:
                existing_country.capital = capital
                existing_country.region = region
                existing_country.population = population
                existing_country.currency_code = currency_code
                existing_country.exchange_rate = exchange_rate
                existing_country.estimated_gdp = estimated_gdp
                existing_country.flag_url = flag_url
            else:
                new_country = Country(
                    name=name,
                    capital=capital,
                    region=region,
                    population=population,
                    currency_code=currency_code,
                    exchange_rate=exchange_rate,
                    estimated_gdp=estimated_gdp,
                    flag_url=flag_url
                )
                db.add(new_country)

        db.commit()

    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail={
            "error": "Internal server error",
            "details": str(e)
        })

    # Generate image after successful commit
    try:
        _get_summary_image(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error": "Internal server error",
            "details": f"Failed to generate summary image: {str(e)}"
        })

    total_countries = db.query(Country).count()
    last_refreshed = db.query(Country).order_by(Country.last_refreshed_at.desc()).first()
    last_refreshed_at = last_refreshed.last_refreshed_at.isoformat() if last_refreshed else "N/A"
    return {
        "message": f"Database refreshed with {total_countries} countries.",
        "last_refreshed_at": last_refreshed_at
    }

@app.get("/countries")
def get_countries(
    db: Session = Depends(get_db),
    region: str | None = Query(None, description="Filter by region (e.g., Africa)"),
    currency: str | None = Query(None, description="Filter by currency code (e.g., NGN)"),
    sort: str | None = Query(None, description="Sort order (e.g., name_asc, gdp_desc)")
):
    query = db.query(Country)

    if region:
        query = query.filter(Country.region.ilike(region))
    if currency:
        query = query.filter(Country.currency_code.ilike(currency))
    if sort:
        if sort == "name_asc":
            query = query.order_by(Country.name.asc())
        elif sort == "name_desc":
            query = query.order_by(Country.name.desc())
        elif sort == "gdp_asc":
            query = query.order_by(Country.estimated_gdp.asc())
        elif sort == "gdp_desc":
            query = query.order_by(Country.estimated_gdp.desc())
        else:
            raise HTTPException(status_code=400, detail={
                "error": "Validation failed",
                "details": "Invalid sort parameter. Use one of: name_asc, name_desc, gdp_asc, gdp_desc."
            })

    countries = query.all()
    return [{
        "id": country.id,
        "name": country.name,
        "capital": country.capital,
        "region": country.region,
        "population": country.population,
        "currency_code": country.currency_code,
        "exchange_rate": country.exchange_rate,
        "estimated_gdp": country.estimated_gdp,
        "flag_url": country.flag_url,
        "last_refreshed_at": country.last_refreshed_at.isoformat()
    } for country in countries]

@app.get("/countries/image")
def get_summary_image():
    if not os.path.exists(IMAGE_PATH):
        return JSONResponse(status_code=404, content={"error": "Summary image not found"})
    return FileResponse(IMAGE_PATH, media_type="image/png")

@app.get("/countries/{country_name}")
def get_country_by_name(country_name: str, db: Session = Depends(get_db)):
    country = db.query(Country).filter(Country.name.ilike(country_name)).first()
    if not country:
        raise HTTPException(status_code=404, detail={"error": "Country not found"})
    return {
        "id": country.id,
        "name": country.name,
        "capital": country.capital,
        "region": country.region,
        "population": country.population,
        "currency_code": country.currency_code,
        "exchange_rate": country.exchange_rate,
        "estimated_gdp": country.estimated_gdp,
        "flag_url": country.flag_url,
        "last_refreshed_at": country.last_refreshed_at.isoformat()
    }

@app.delete("/countries/{country_name}")
def delete_country_by_name(country_name: str, db: Session = Depends(get_db)):
    country_query = db.query(Country).filter(Country.name.ilike(country_name))
    country = country_query.first()
    if not country:
        raise HTTPException(status_code=404, detail={"error": "Country not found"})
    country_query.delete(synchronize_session=False)
    db.commit()
    return {"message": f"Country '{country_name}' deleted successfully."}

@app.get("/status")
def get_status(db: Session = Depends(get_db)):
    total_countries = db.query(Country).count()
    last_refreshed = db.query(Country).order_by(Country.last_refreshed_at.desc()).first()
    return {
        "total_countries": total_countries,
        "last_refreshed_at": last_refreshed.last_refreshed_at.isoformat() if last_refreshed else None
    }

def _get_summary_image(db: Session):
    total_countries = db.query(Country).count()
    top_countries = db.query(Country).order_by(Country.estimated_gdp.desc()).limit(5).all()
    latest_country = db.query(Country).order_by(Country.last_refreshed_at.desc()).first()
    last_refreshed_at = latest_country.last_refreshed_at.strftime("%Y-%m-%d %H:%M:%S UTC") if latest_country else "N/A"

    width, height = 600, 400
    background_color = "#333333"
    text_color = "#F0F0F0"
    img = Image.new('RGB', (width, height), color=background_color)
    d = ImageDraw.Draw(img)

    try:
        title_font = ImageFont.truetype("arial.ttf", 24)
        body_font = ImageFont.truetype("arial.ttf", 16)
        mono_font = ImageFont.truetype("courier.ttf", 14)
    except IOError:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
        mono_font = ImageFont.load_default()

    y_offset = 30
    d.text((30, y_offset), "Country Data Cache Summary", fill="#4CAF50", font=title_font)
    y_offset += 40
    d.text((30, y_offset), f"Total Countries: {total_countries}", fill=text_color, font=body_font)
    y_offset += 30
    d.text((30, y_offset), f"Last Refreshed: {last_refreshed_at}", fill=text_color, font=body_font)
    y_offset += 50
    d.text((30, y_offset), "--- Top 5 by Estimated GDP ---", fill="#FFC107", font=body_font)
    y_offset += 30

    for i, country in enumerate(top_countries):
        gdp_str = f"GDP: ${country.estimated_gdp:,.2f}" if country.estimated_gdp else "GDP: $0.00"
        line = f"{i+1}. {country.name.ljust(20)}{gdp_str.rjust(30)}"
        d.text((30, y_offset), line, fill=text_color, font=mono_font)
        y_offset += 20

    os.makedirs(CACHE_DIR, exist_ok=True)
    img.save(IMAGE_PATH)

