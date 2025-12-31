from sqlalchemy import Column, Integer, String, Float, Date, DateTime
from .database import Base

class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    district_code = Column(String, index=True)
    property_id = Column(String, index=True)
    sale_counter = Column(String)
    download_datetime = Column(String)
    property_name = Column(String)
    property_unit_number = Column(String)
    property_house_number = Column(String)
    property_street_name = Column(String)
    property_locality = Column(String, index=True)
    property_post_code = Column(Integer, index=True)
    area = Column(Float)
    area_type = Column(String)
    contract_date = Column(Date, index=True)
    settlement_date = Column(Date)
    purchase_price = Column(Float, index=True)
    zoning = Column(String)
    nature_of_property = Column(String)
    primary_purpose = Column(String)
    strata_lot_number = Column(String)
    dealing_number = Column(String)
    property_legal_description = Column(String)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Property listing URLs
    realestate_url = Column(String, nullable=True)
    domain_url = Column(String, nullable=True)
    listings_last_checked = Column(DateTime, nullable=True)

class PropertyGrowth(Base):
    __tablename__ = "property_growth"
    property_id = Column(String, primary_key=True, index=True)
    cagr = Column(Float)
    total_growth = Column(Float)
    years_held = Column(Float)
    last_sale_price = Column(Float)
    first_sale_price = Column(Float)

class StreetGrowth(Base):
    __tablename__ = "street_growth"
    id = Column(Integer, primary_key=True, index=True)
    street_name = Column(String, index=True)
    suburb = Column(String, index=True)
    post_code = Column(Integer)
    year = Column(Integer, index=True)
    avg_cagr = Column(Float)
    property_count = Column(Integer)

class SuburbGrowth(Base):
    __tablename__ = "suburb_growth"
    id = Column(Integer, primary_key=True, index=True)
    suburb = Column(String, index=True)
    year = Column(Integer, index=True)
    avg_cagr = Column(Float)
    property_count = Column(Integer)

class StreetSummary(Base):
    __tablename__ = "street_summary"
    id = Column(Integer, primary_key=True, index=True)
    street_name = Column(String, index=True)
    suburb = Column(String, index=True)
    post_code = Column(Integer)
    unique_properties = Column(Integer)
    total_sales = Column(Integer)
    avg_cagr = Column(Float)
    is_top_performer = Column(Integer, default=0) # 1 if in top tier

class SuburbSummary(Base):
    __tablename__ = "suburb_summary"
    id = Column(Integer, primary_key=True, index=True)
    suburb = Column(String, index=True)
    unique_properties = Column(Integer)
    total_sales = Column(Integer)
    avg_cagr = Column(Float)
    is_top_performer = Column(Integer, default=0)
