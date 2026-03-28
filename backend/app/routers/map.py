from fastapi import APIRouter, Query
from app.database import get_duck_conn
from app.h3_utils import zoom_to_resolution, h3_to_boundary
from app.cache import cached
from app.config import settings
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

    try:
        duck = get_duck_conn()
        rows = duck.execute(f"""
            SELECT
                h3_h3_to_string(h3_latlng_to_cell(latitude, longitude, {resolution})) AS h3_index,
                COUNT(*) AS property_count,
                AVG(pg.avg_cagr) AS avg_cagr,
                AVG(s.purchase_price) AS avg_price,
                MAX(s.contract_date)::VARCHAR AS last_sale,
                MAX(s.property_locality) AS suburb
            FROM read_parquet('{r2_path}') s
            LEFT JOIN read_parquet('{pg_path}') pg ON pg.property_id = s.property_id
            WHERE s.latitude BETWEEN {min_lat} AND {max_lat}
              AND s.longitude BETWEEN {min_lng} AND {max_lng}
              AND EXTRACT(YEAR FROM s.contract_date::DATE) <= {year}
              AND s.latitude IS NOT NULL
            GROUP BY 1
            ORDER BY property_count DESC
            LIMIT 5000
        """).fetchall()
    except Exception as e:
        logger.warning(f"DuckDB viewport query failed: {e}, falling back to PG")
        rows = None

    if rows is None:
        from app.database import get_db, get_pg_conn

        conn = get_pg_conn()
        if conn is None:
            return {"type": "FeatureCollection", "features": []}
        try:
            from app.models import Sale, PropertyGrowth
            from sqlalchemy import func, text

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

    features = []
    for row in rows:
        h3_idx = row[0]
        if not h3_idx:
            continue
        count = row[1]
        cagr = row[2]
        price = row[3]
        last_sale = row[4]
        suburb = row[5]
        try:
            boundary = h3_to_boundary(h3_idx)
        except Exception:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [boundary],
                },
                "properties": {
                    "h3_index": h3_idx,
                    "property_count": count,
                    "avg_cagr": round(float(cagr or 0), 6),
                    "avg_price": round(float(price or 0), 0),
                    "last_sale": last_sale or "",
                    "suburb": suburb or "Unknown",
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}
