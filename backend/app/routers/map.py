from fastapi import APIRouter, Query
from app.database import get_duck_conn
from app.h3_utils import h3_to_boundary
from app.cache import cached
from app.config import settings
import h3
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/viewport")
@cached(ttl=120)
async def viewport_data(
    min_lat: float = Query(-38.0),
    max_lat: float = Query(-28.0),
    min_lng: float = Query(140.0),
    max_lng: float = Query(154.0),
    zoom: int = Query(8),
    year: int = Query(2024),
):
    resolution = zoom_to_resolution(zoom)
    r2_path = f"s3://{settings.r2_bucket_name}/parquet/sales/latest.parquet"
    pg_path = f"s3://{settings.r2_bucket_name}/parquet/property_growth/latest.parquet"

    duck_rows = None
    try:
        duck = get_duck_conn()
        duck_rows = duck.execute(f"""
            SELECT
                s.latitude,
                s.longitude,
                s.purchase_price,
                s.contract_date::VARCHAR,
                s.property_locality,
                pg.avg_cagr
            FROM read_parquet('{r2_path}') s
            LEFT JOIN read_parquet('{pg_path}') pg ON pg.property_id = s.property_id
            WHERE s.latitude BETWEEN {min_lat} AND {max_lat}
              AND s.longitude BETWEEN {min_lng} AND {max_lng}
              AND EXTRACT(YEAR FROM s.contract_date::DATE) <= {year}
              AND s.latitude IS NOT NULL
        """).fetchall()
    except Exception as e:
        logger.warning(f"DuckDB viewport query failed: {e}, falling back to PG")
        duck_rows = None

    if duck_rows is not None:
        h3_groups = {}
        for row in duck_rows:
            lat, lng, price, contract_date, locality, cagr = row
            if lat is None or lng is None:
                continue
            try:
                h3_idx = h3.h3_lat_lng_to_cell(lat, lng, resolution)
            except Exception:
                continue
            if h3_idx not in h3_groups:
                h3_groups[h3_idx] = {
                    "prices": [],
                    "cagrs": [],
                    "dates": [],
                    "localities": [],
                }
            h3_groups[h3_idx]["prices"].append(price or 0)
            if cagr is not None:
                h3_groups[h3_idx]["cagrs"].append(cagr)
            if contract_date:
                h3_groups[h3_idx]["dates"].append(contract_date)
            if locality:
                h3_groups[h3_idx]["localities"].append(locality)

        features = []
        for h3_idx, g in sorted(
            h3_groups.items(), key=lambda x: len(x[1]["prices"]), reverse=True
        )[:5000]:
            try:
                boundary = h3_to_boundary(h3_idx)
            except Exception:
                continue
            prices = g["prices"]
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [boundary]},
                    "properties": {
                        "h3_index": h3_idx,
                        "property_count": len(prices),
                        "avg_cagr": (
                            round(sum(g["cagrs"]) / len(g["cagrs"]), 6)
                            if g["cagrs"]
                            else 0
                        ),
                        "avg_price": round(sum(prices) / len(prices), 0)
                        if prices
                        else 0,
                        "last_sale": max(g["dates"]) if g["dates"] else "",
                        "suburb": max(g["localities"], key=g["localities"].count)
                        if g["localities"]
                        else "Unknown",
                    },
                }
            )
        return {"type": "FeatureCollection", "features": features}

    from app.database import get_db, get_pg_conn

    conn = get_pg_conn()
    if conn is None:
        return {"type": "FeatureCollection", "features": []}
    try:
        from app.models import Sale, PropertyGrowth
        from sqlalchemy import func

        db = next(get_db())
        try:
            rows_pg = (
                db.query(
                    func.avg(Sale.latitude).label("lat"),
                    func.avg(Sale.longitude).label("lng"),
                    func.count(Sale.id).label("cnt"),
                    func.avg(PropertyGrowth.avg_cagr).label("cagr"),
                )
                .outerjoin(
                    PropertyGrowth, Sale.property_id == PropertyGrowth.property_id
                )
                .filter(
                    Sale.latitude.between(min_lat, max_lat),
                    Sale.longitude.between(min_lng, max_lng),
                )
                .group_by(
                    func.floor(Sale.latitude * 100),
                    func.floor(Sale.longitude * 100),
                )
                .all()
            )
            features = []
            for r in rows_pg:
                if r.lat is None:
                    continue
                features.append(
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [float(r.lng or 0), float(r.lat or 0)],
                        },
                        "properties": {
                            "property_count": r.cnt,
                            "avg_cagr": round(float(r.cagr or 0), 6),
                            "avg_price": 0,
                            "last_sale": "",
                            "suburb": "Unknown",
                        },
                    }
                )
            return {"type": "FeatureCollection", "features": features}
        finally:
            db.close()
    finally:
        conn.close()


def zoom_to_resolution(zoom: int) -> int:
    mapping = {
        0: 0,
        1: 1,
        2: 2,
        3: 3,
        4: 4,
        5: 5,
        6: 6,
        7: 7,
        8: 8,
        9: 9,
        10: 10,
        11: 11,
        12: 12,
        13: 13,
        14: 14,
        15: 15,
    }
    return mapping.get(zoom, 8)
