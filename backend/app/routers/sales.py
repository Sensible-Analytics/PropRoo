from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session, load_only
from sqlalchemy import func, desc
from typing import List, Optional
from ..database import get_db, SessionLocal
from ..models import Sale, PropertyGrowth
from pydantic import BaseModel
from datetime import date
from ..geocoding import get_nearest_station

router = APIRouter()

class SaleResponse(BaseModel):
    id: int
    district_code: Optional[str]
    property_id: Optional[str]
    property_name: Optional[str]
    property_unit_number: Optional[str]
    property_house_number: Optional[str]
    property_street_name: Optional[str]
    property_locality: Optional[str]
    property_post_code: Optional[int]
    area: Optional[float]
    area_type: Optional[str]
    contract_date: Optional[date]
    settlement_date: Optional[date]
    purchase_price: Optional[float]
    zoning: Optional[str]
    nature_of_property: Optional[str]
    primary_purpose: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    
    # Growth metrics
    cagr: Optional[float]
    total_growth: Optional[float]
    years_held: Optional[float]

    # Station info
    nearest_station: Optional[str]
    distance_to_station: Optional[float]

    # Listing URLs
    realestate_url: Optional[str]
    domain_url: Optional[str]
    
    class Config:
        orm_mode = True

@router.get("/sales", response_model=List[SaleResponse])
def get_sales(
    skip: int = 0, 
    limit: int = 100,
    suburb: Optional[str] = None,
    min_area: Optional[float] = None,
    max_area: Optional[float] = None,
    property_type: Optional[str] = None,
    min_growth: Optional[float] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    query = db.query(
        Sale,
        PropertyGrowth.cagr,
        PropertyGrowth.total_growth,
        PropertyGrowth.years_held
    ).outerjoin(PropertyGrowth, Sale.property_id == PropertyGrowth.property_id)

    if suburb:
        query = query.filter(Sale.property_locality.ilike(f"%{suburb}%"))
    if min_area:
        query = query.filter(Sale.area >= min_area)
    if max_area:
        query = query.filter(Sale.area <= max_area)
    if property_type:
        query = query.filter(Sale.primary_purpose == property_type)
    if min_growth is not None:
        query = query.filter(PropertyGrowth.cagr >= (min_growth / 100.0)) # Percentage to decimal
    
    if min_price:
        query = query.filter(Sale.purchase_price >= min_price)
    if max_price:
        query = query.filter(Sale.purchase_price <= max_price)
        
    if start_date:
        query = query.filter(Sale.contract_date >= start_date)
    if end_date:
        query = query.filter(Sale.contract_date <= end_date)
    
    results = query.order_by(Sale.contract_date.desc()).offset(skip).limit(limit).all()

    # Map results to response model
    response = []
    for row in results:
        sale_obj = row[0]
        # We need to manually construct the response or add fields to the Sale object if we returned just Sale.
        # But since we selected fields, it's a tuple.
        # Easier way: Return a Pydantic model constructing from the tuple
        
        # Helper to convert sqlalchemy model instance to dict
        sale_dict = sale_obj.__dict__
        if '_sa_instance_state' in sale_dict:
            del sale_dict['_sa_instance_state']
            
        sale_dict['cagr'] = row[1]
        sale_dict['total_growth'] = row[2]
        sale_dict['years_held'] = row[3]
        
        # Calculate station distance on the fly
        # Ideally this should be pre-calculated in DB, but for MVP we do it here
        if sale_obj.latitude and sale_obj.longitude:
            station, dist = get_nearest_station(sale_obj.latitude, sale_obj.longitude)
            sale_dict['nearest_station'] = station
            sale_dict['distance_to_station'] = dist
        else:
            sale_dict['nearest_station'] = None
            sale_dict['distance_to_station'] = None

        response.append(sale_dict)
        
    return response

@router.get("/stats/monthly_median")
def get_monthly_median(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    # Group by month and calculate median price
    # SQLite doesn't have easy median, so we might need avg or fetch valid data
    # Let's do Average for now as simpler in SQL, or fetch data and process in pandas if not too huge.
    # Grouping by YYYY-MM
    
    # SQLite strftime('%Y-%m', contract_date)
    # SQLite strftime('%Y-%m', contract_date)
    q = db.query(
        func.strftime('%Y-%m', Sale.contract_date).label('month'),
        func.avg(Sale.purchase_price).label('avg_price'),
        func.count(Sale.id).label('count')
    )
    
    if start_date:
        q = q.filter(Sale.contract_date >= start_date)
    if end_date:
        q = q.filter(Sale.contract_date <= end_date)
        
    results = q.group_by('month').order_by('month').all()
    
    return [{"month": r.month, "avg_price": r.avg_price, "count": r.count} for r in results if r.month is not None]

@router.get("/stats/top_suburbs")
def get_top_suburbs(
    limit: int = 10, 
    start_date: Optional[date] = None, 
    end_date: Optional[date] = None, 
    db: Session = Depends(get_db)
):
    q = db.query(
        Sale.property_locality,
        func.count(Sale.id).label('count'),
        func.avg(Sale.purchase_price).label('avg_price')
    )
    
    if start_date:
        q = q.filter(Sale.contract_date >= start_date)
    if end_date:
        q = q.filter(Sale.contract_date <= end_date)
        
    results = q.group_by(Sale.property_locality).order_by(desc('count')).limit(limit).all()
    
    return [{"suburb": r.property_locality, "count": r.count, "avg_price": r.avg_price} for r in results]

from ..geocoding import batch_geocode_sales
import threading

@router.post("/geocode")
def trigger_geocode(sale_ids: List[int], db: Session = Depends(get_db)):
    # Run in background or just limit the size strictly
    if len(sale_ids) > 20:
         return {"message": "Limit 20 records at a time for on-demand geocoding."}
    
    # We can run this synchronously for small batches for MVP to ensure UI updates
    count = batch_geocode_sales(db, sale_ids)
    return {"message": f"Geocoded {count} records."}

# New endpoints for property detail view
@router.get("/property/{property_id}/history", response_model=List[SaleResponse])
def get_property_history(property_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Get all sales for a specific property in chronological order"""
    
    # Check if we need to refresh listings (if latest sale has no listing info or is old)
    # We trigger this in the background to not slow down the response
    from ..listing_search import search_property_listings
    from datetime import datetime, timedelta
    
    def refresh_listings_task(pid):
        # Create fresh session for background task
        bg_db = SessionLocal()
        try:
            # Find latest sale for this property
            latest_sale = bg_db.query(Sale).filter(Sale.property_id == pid).order_by(desc(Sale.contract_date)).first()
            if latest_sale:
                # If never checked or checked more than 7 days ago
                if not latest_sale.listings_last_checked or latest_sale.listings_last_checked < datetime.utcnow() - timedelta(days=7):
                    results = search_property_listings(latest_sale)
                    latest_sale.realestate_url = results['realestate_url']
                    latest_sale.domain_url = results['domain_url']
                    latest_sale.listings_last_checked = results['timestamp']
                    bg_db.commit()
        except Exception as e:
            print(f"Background listing search failed: {e}")
        finally:
            bg_db.close()

    background_tasks.add_task(refresh_listings_task, property_id)
    
    query = db.query(
        Sale,
        PropertyGrowth.cagr,
        PropertyGrowth.total_growth,
        PropertyGrowth.years_held
    ).outerjoin(PropertyGrowth, Sale.property_id == PropertyGrowth.property_id)
    
    query = query.filter(Sale.property_id == property_id)
    results = query.order_by(Sale.contract_date.asc()).all()
    
    # Map results to response model
    response = []
    for row in results:
        sale_obj = row[0]
        sale_dict = sale_obj.__dict__
        if '_sa_instance_state' in sale_dict:
            del sale_dict['_sa_instance_state']
            
        sale_dict['cagr'] = row[1]
        sale_dict['total_growth'] = row[2]
        sale_dict['years_held'] = row[3]
        
        # Calculate station distance on the fly
        if sale_obj.latitude and sale_obj.longitude:
            station, dist = get_nearest_station(sale_obj.latitude, sale_obj.longitude)
            sale_dict['nearest_station'] = station
            sale_dict['distance_to_station'] = dist
        else:
            sale_dict['nearest_station'] = None
            sale_dict['distance_to_station'] = None

        response.append(sale_dict)
        
    return response

from ..models import StreetGrowth, SuburbGrowth, StreetSummary, SuburbSummary

@router.get("/stats/suburb_cagr")
def get_suburb_cagr(suburb: str, year: Optional[int] = 2024, db: Session = Depends(get_db)):
    """Get average CAGR and property count for a suburb for a given year"""
    result = db.query(SuburbGrowth).filter(
        SuburbGrowth.suburb == suburb,
        SuburbGrowth.year == year
    ).first()
    
    if result:
        return {
            "suburb": result.suburb,
            "avg_cagr": result.avg_cagr,
            "property_count": result.property_count,
            "year": result.year
        }
    return {"suburb": suburb, "avg_cagr": None, "property_count": 0, "year": year}

@router.get("/stats/street_trend")
def get_street_trend(street_name: str, suburb: str, db: Session = Depends(get_db)):
    """Get CAGR trend over years for a street"""
    results = db.query(StreetGrowth).filter(
        StreetGrowth.street_name == street_name,
        StreetGrowth.suburb == suburb
    ).order_by(StreetGrowth.year.asc()).all()
    return [{"year": r.year, "avg_cagr": r.avg_cagr, "property_count": r.property_count} for r in results]

@router.get("/stats/suburb_trend")
def get_suburb_trend(suburb: str, db: Session = Depends(get_db)):
    """Get CAGR trend over years for a suburb"""
    results = db.query(SuburbGrowth).filter(
        SuburbGrowth.suburb == suburb
    ).order_by(SuburbGrowth.year.asc()).all()
    return [{"year": r.year, "avg_cagr": r.avg_cagr, "property_count": r.property_count} for r in results]

@router.get("/stats/global_summary")
def get_global_summary(db: Session = Depends(get_db)):
    """Get overall top suburbs and summary stats"""
    top_suburbs = db.query(SuburbSummary).order_by(desc(SuburbSummary.avg_cagr)).limit(5).all()
    top_streets = db.query(StreetSummary).order_by(desc(StreetSummary.avg_cagr)).limit(5).all()
    
    return {
        "top_suburbs": [
            {
                "suburb": s.suburb, 
                "avg_cagr": s.avg_cagr, 
                "unique_properties": s.unique_properties, 
                "total_sales": s.total_sales
            } for s in top_suburbs
        ],
        "top_streets": [
            {
                "street_name": s.street_name,
                "suburb": s.suburb,
                "avg_cagr": s.avg_cagr,
                "total_sales": s.total_sales
            } for s in top_streets
        ]
    }

@router.get("/stats/suburb_centroids")
def get_suburb_centroids(db: Session = Depends(get_db)):
    """Get average lat/lon for each suburb to use as fallback coordinates"""
    results = db.query(
        Sale.property_locality,
        func.avg(Sale.latitude).label('avg_lat'),
        func.avg(Sale.longitude).label('avg_lon')
    ).filter(Sale.latitude != None).group_by(Sale.property_locality).all()
    
    return {r.property_locality: {"lat": r.avg_lat, "lon": r.avg_lon} for r in results}

@router.get("/stats/top_performers")
def get_top_performers(year: int = 2024, property_type: Optional[str] = None, db: Session = Depends(get_db)):
    """Get top performing suburbs and streets for a specific year, optionally filtered by property type"""
    suburbs = db.query(SuburbGrowth).filter(SuburbGrowth.year == year).order_by(desc(SuburbGrowth.avg_cagr)).limit(10).all()
    streets = db.query(StreetGrowth).filter(StreetGrowth.year == year).order_by(desc(StreetGrowth.avg_cagr)).limit(10).all()
    
    # Leaderboard by sales activity (number of sales records in that year)
    suburb_act_q = db.query(
        Sale.property_locality,
        func.count(Sale.id).label('sales_count')
    ).filter(func.strftime('%Y', Sale.contract_date) == str(year))
    
    street_act_q = db.query(
        Sale.property_street_name,
        Sale.property_locality,
        func.count(Sale.id).label('sales_count')
    ).filter(func.strftime('%Y', Sale.contract_date) == str(year))

    if property_type:
        suburb_act_q = suburb_act_q.filter(Sale.primary_purpose == property_type)
        street_act_q = street_act_q.filter(Sale.primary_purpose == property_type)

    suburb_activity = suburb_act_q.group_by(Sale.property_locality).order_by(desc('sales_count')).limit(10).all()
    street_activity = street_act_q.group_by(Sale.property_street_name, Sale.property_locality).order_by(desc('sales_count')).limit(10).all()

    return {
        "growth": {
            "suburbs": [{"suburb": s.suburb, "avg_cagr": s.avg_cagr, "property_count": s.property_count} for s in suburbs],
            "streets": [{"street_name": s.street_name, "suburb": s.suburb, "avg_cagr": s.avg_cagr, "property_count": s.property_count} for s in streets]
        },
        "activity": {
            "suburbs": [{"suburb": s.property_locality, "sales_count": s.sales_count} for s in suburb_activity],
            "streets": [{"street_name": s.property_street_name, "suburb": s.property_locality, "sales_count": s.sales_count} for s in street_activity]
        }
    }

@router.get("/stats/neighbors/suburbs")
def get_neighboring_suburbs(suburb: str, db: Session = Depends(get_db)):
    """Get summary stats for neighboring suburbs based on geographic proximity"""
    # First get target suburb centroid
    target = db.query(
        func.avg(Sale.latitude).label('lat'),
        func.avg(Sale.longitude).label('lon')
    ).filter(Sale.property_locality == suburb, Sale.latitude != None).first()
    
    if not target.lat:
        return []
        
    # Find neighbors by Euclidean distance (approximate since we just need top N)
    # limit search to 10 nearest distinct suburbs
    neighbors = db.query(
        Sale.property_locality,
        func.avg(Sale.latitude).label('lat'),
        func.avg(Sale.longitude).label('lon'),
        ((func.avg(Sale.latitude) - target.lat) * (func.avg(Sale.latitude) - target.lat) + 
         (func.avg(Sale.longitude) - target.lon) * (func.avg(Sale.longitude) - target.lon)).label('dist')
    ).filter(Sale.property_locality != suburb, Sale.latitude != None)\
     .group_by(Sale.property_locality).order_by('dist').limit(10).all()
     
    suburb_names = [n.property_locality for n in neighbors]
    stats = db.query(SuburbSummary).filter(SuburbSummary.suburb.in_(suburb_names)).all()
    
    # Merge coords and stats
    neighbor_map = {n.property_locality: {"lat": n.lat, "lon": n.lon} for n in neighbors}
    return [
        {
            "suburb": s.suburb,
            "latitude": neighbor_map[s.suburb]["lat"],
            "longitude": neighbor_map[s.suburb]["lon"],
            "avg_cagr": s.avg_cagr,
            "total_sales": s.total_sales,
            "unique_properties": s.unique_properties
        } for s in stats
    ]

@router.get("/stats/neighbors/streets")
def get_neighboring_streets(street_name: str, suburb: str, db: Session = Depends(get_db)):
    """Get summary stats for streets in the same suburb and geographic neighbors"""
    # Get target street centroid
    target = db.query(
        func.avg(Sale.latitude).label('lat'),
        func.avg(Sale.longitude).label('lon')
    ).filter(Sale.property_street_name == street_name, Sale.property_locality == suburb, Sale.latitude != None).first()
    
    if not target.lat:
        # Fallback to just same suburb
        streets = db.query(StreetSummary).filter(StreetSummary.suburb == suburb, StreetSummary.street_name != street_name).limit(10).all()
    else:
        # Geographic proximity within same suburb or neighboring suburbs
        neighbors = db.query(
            Sale.property_street_name,
            Sale.property_locality,
            func.avg(Sale.latitude).label('lat'),
            func.avg(Sale.longitude).label('lon'),
            ((func.avg(Sale.latitude) - target.lat) * (func.avg(Sale.latitude) - target.lat) + 
             (func.avg(Sale.longitude) - target.lon) * (func.avg(Sale.longitude) - target.lon)).label('dist')
        ).filter(Sale.latitude != None)\
         .filter((Sale.property_street_name != street_name) | (Sale.property_locality != suburb))\
         .group_by(Sale.property_street_name, Sale.property_locality).order_by('dist').limit(20).all()
         
        # Fetch stats for these combinations
        res = []
        for n in neighbors:
            s_stat = db.query(StreetSummary).filter(StreetSummary.street_name == n.property_street_name, StreetSummary.suburb == n.property_locality).first()
            if s_stat:
                res.append({
                    "street_name": s_stat.street_name,
                    "suburb": s_stat.suburb,
                    "latitude": n.lat,
                    "longitude": n.lon,
                    "avg_cagr": s_stat.avg_cagr,
                    "total_sales": s_stat.total_sales
                })
        return res[:15]
    return []

@router.get("/stats/neighbors/properties")
def get_neighboring_properties(property_id: str, db: Session = Depends(get_db)):
    """Get neighboring properties with stats"""
    target = db.query(Sale).filter(Sale.property_id == property_id, Sale.latitude != None).first()
    if not target:
        return []
        
    neighbors = db.query(
        Sale,
        PropertyGrowth.cagr,
        ((Sale.latitude - target.latitude) * (Sale.latitude - target.latitude) + 
         (Sale.longitude - target.longitude) * (Sale.longitude - target.longitude)).label('dist')
    ).join(PropertyGrowth, Sale.property_id == PropertyGrowth.property_id)\
     .filter(Sale.property_id != property_id, Sale.latitude != None)\
     .order_by('dist').limit(20).all()
     
    return [
        {
            "property_id": r[0].property_id,
            "address": f"{r[0].property_house_number} {r[0].property_street_name}",
            "suburb": r[0].property_locality,
            "latitude": r[0].latitude,
            "longitude": r[0].longitude,
            "avg_cagr": r[1],
            "last_price": r[0].purchase_price
        } for r in neighbors
    ]
@router.get("/stats/unified_map")
def get_unified_map_data(
    level: str = "suburb", # "suburb" or "street"
    year: int = 2024,
    property_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get data for the unified map: Top 10 entities for the level/year,
    along with their respective neighboring entities for comparison.
    """
    if level == "suburb":
        top_performers = db.query(SuburbGrowth).filter(SuburbGrowth.year == year)\
            .order_by(desc(SuburbGrowth.avg_cagr)).limit(10).all()
        
        clusters = []
        for i, tp in enumerate(top_performers):
            # Get centroid for this suburb
            target = db.query(
                func.avg(Sale.latitude).label('lat'),
                func.avg(Sale.longitude).label('lon')
            ).filter(Sale.property_locality == tp.suburb, Sale.latitude != None).first()
            
            if not target or not target.lat:
                continue
                
            # Find neighbors
            neighbors_raw = db.query(
                Sale.property_locality,
                func.avg(Sale.latitude).label('lat'),
                func.avg(Sale.longitude).label('lon'),
                ((func.avg(Sale.latitude) - target.lat) * (func.avg(Sale.latitude) - target.lat) + 
                 (func.avg(Sale.longitude) - target.lon) * (func.avg(Sale.longitude) - target.lon)).label('dist')
            ).filter(Sale.property_locality != tp.suburb, Sale.latitude != None)\
             .group_by(Sale.property_locality).order_by('dist').limit(5).all()
            
            neighbor_names = [n.property_locality for n in neighbors_raw]
            neighbor_stats = db.query(SuburbSummary).filter(SuburbSummary.suburb.in_(neighbor_names)).all()
            neighbor_map = {n.property_locality: {"lat": n.lat, "lon": n.lon} for n in neighbors_raw}
            
            clusters.append({
                "id": tp.suburb,
                "name": tp.suburb,
                "lat": target.lat,
                "lon": target.lon,
                "cagr": tp.avg_cagr,
                "rank": i + 1,
                "neighbors": [
                    {
                        "name": s.suburb,
                        "lat": neighbor_map[s.suburb]["lat"],
                        "lon": neighbor_map[s.suburb]["lon"],
                        "cagr": s.avg_cagr
                    } for s in neighbor_stats
                ]
            })
        return {"clusters": clusters}

    elif level == "street":
        top_performers = db.query(StreetGrowth).filter(StreetGrowth.year == year)\
            .order_by(desc(StreetGrowth.avg_cagr)).limit(10).all()
            
        clusters = []
        for i, tp in enumerate(top_performers):
            target = db.query(
                func.avg(Sale.latitude).label('lat'),
                func.avg(Sale.longitude).label('lon')
            ).filter(Sale.property_street_name == tp.street_name, Sale.property_locality == tp.suburb, Sale.latitude != None).first()
            
            if not target or not target.lat:
                continue
                
            # Geographic proximity within same suburb or neighboring suburbs
            neighbors_raw = db.query(
                Sale.property_street_name,
                Sale.property_locality,
                func.avg(Sale.latitude).label('lat'),
                func.avg(Sale.longitude).label('lon'),
                ((func.avg(Sale.latitude) - target.lat) * (func.avg(Sale.latitude) - target.lat) + 
                 (func.avg(Sale.longitude) - target.lon) * (func.avg(Sale.longitude) - target.lon)).label('dist')
            ).filter(Sale.latitude != None)\
             .filter((Sale.property_street_name != tp.street_name) | (Sale.property_locality != tp.suburb))\
             .group_by(Sale.property_street_name, Sale.property_locality).order_by('dist').limit(5).all()
             
            cluster_neighbors = []
            for n in neighbors_raw:
                s_stat = db.query(StreetSummary).filter(StreetSummary.street_name == n.property_street_name, StreetSummary.suburb == n.property_locality).first()
                if s_stat:
                    cluster_neighbors.append({
                        "name": f"{s_stat.street_name}, {s_stat.suburb}",
                        "lat": n.lat,
                        "lon": n.lon,
                        "cagr": s_stat.avg_cagr
                    })
            
            clusters.append({
                "id": f"{tp.street_name}_{tp.suburb}",
                "name": f"{tp.street_name}, {tp.suburb}",
                "lat": target.lat,
                "lon": target.lon,
                "cagr": tp.avg_cagr,
                "rank": i + 1,
                "neighbors": cluster_neighbors
            })
        return {"clusters": clusters}
        
    return {"clusters": []}
