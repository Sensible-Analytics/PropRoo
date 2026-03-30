from fastapi import APIRouter, Query
from app.database import get_duck_conn
from app.cache import cached
from app.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def _r2(table: str) -> str:
    return f"s3://{settings.r2_bucket_name}/parquet/{table}/latest.parquet"


def _duck_query(query: str):
    try:
        duck = get_duck_conn()
        df = duck.execute(query).df()
        # Replace NaN with None for JSON compliance (DuckDB returns NaN for empty aggregates)
        df = df.where(pd.notnull(df), None)
        return df.to_dict("records")
    except Exception as e:
        logger.warning(f"DuckDB query failed: {e}, falling back to PostgreSQL")
        return None


@router.get("/global_summary")
@cached(ttl=300)
async def global_summary(year: int = Query(2024)):
    parquet_data = _duck_query(f"""
        SELECT suburb, post_code, avg_cagr, unique_properties, total_sales
        FROM read_parquet('{_r2("suburb_summary")}')
        WHERE avg_cagr > 0
        ORDER BY avg_cagr DESC
        LIMIT 20
    """)
    top_streets_data = _duck_query(f"""
        SELECT street_name, suburb, post_code, avg_cagr, total_sales
        FROM read_parquet('{_r2("street_summary")}')
        WHERE avg_cagr > 0
        ORDER BY avg_cagr DESC
        LIMIT 20
    """)

    if parquet_data is not None and top_streets_data is not None:
        return {
            "top_suburbs": parquet_data,
            "top_streets": top_streets_data,
            "year": year,
        }

    from app.database import get_db
    from app.models import SuburbSummary, StreetSummary
    from sqlalchemy import desc

    db = next(get_db())
    try:
        top_suburbs = (
            db.query(SuburbSummary)
            .order_by(desc(SuburbSummary.avg_cagr))
            .limit(20)
            .all()
        )
        top_streets = (
            db.query(StreetSummary)
            .order_by(desc(StreetSummary.avg_cagr))
            .limit(20)
            .all()
        )
        return {
            "top_suburbs": [
                {
                    "suburb": s.suburb,
                    "post_code": s.post_code,
                    "avg_cagr": s.avg_cagr,
                    "unique_properties": s.unique_properties,
                    "total_sales": s.total_sales,
                }
                for s in top_suburbs
            ],
            "top_streets": [
                {
                    "street_name": s.street_name,
                    "suburb": s.suburb,
                    "post_code": s.post_code,
                    "avg_cagr": s.avg_cagr,
                    "total_sales": s.total_sales,
                }
                for s in top_streets
            ],
            "year": year,
        }
    finally:
        db.close()


@router.get("/top_performers")
@cached(ttl=300)
async def top_performers(
    year: int = Query(2024),
    property_type: str = Query(None),
):
    type_filter = ""
    if property_type:
        type_filter = f"AND s.primary_purpose = '{property_type}'"

    parquet_data = _duck_query(f"""
        SELECT
            pg.suburb,
            pg.post_code,
            AVG(pg.avg_cagr) AS avg_cagr,
            COUNT(pg.property_id) AS property_count
        FROM read_parquet('{_r2("property_growth")}') pg
        JOIN read_parquet('{_r2("sales")}') s ON s.property_id = pg.property_id
        WHERE pg.last_sale_year <= {year} {type_filter}
        GROUP BY pg.suburb, pg.post_code
        ORDER BY avg_cagr DESC
        LIMIT 20
    """)

    if parquet_data is not None:
        return {"growth": {"suburbs": parquet_data}}

    from app.database import get_db
    from app.models import SuburbGrowth
    from sqlalchemy import desc

    db = next(get_db())
    try:
        suburbs = (
            db.query(SuburbGrowth)
            .filter(SuburbGrowth.year == year)
            .order_by(desc(SuburbGrowth.avg_cagr))
            .limit(20)
            .all()
        )
        return {
            "growth": {
                "suburbs": [
                    {
                        "suburb": s.suburb,
                        "avg_cagr": s.avg_cagr,
                        "property_count": s.property_count,
                    }
                    for s in suburbs
                ]
            }
        }
    finally:
        db.close()


@router.get("/suburb_centroids")
@cached(ttl=600)
async def suburb_centroids(year: int = Query(2024)):
    parquet_data = _duck_query(f"""
        SELECT
            s.property_locality AS suburb,
            AVG(s.latitude) AS lat,
            AVG(s.longitude) AS lng,
            ss.avg_cagr,
            ss.total_sales
        FROM read_parquet('{_r2("sale")}') s
        JOIN read_parquet('{_r2("suburb_summary")}') ss
            ON ss.suburb = s.property_locality
        WHERE EXTRACT(YEAR FROM s.contract_date::DATE) <= {year}
          AND s.latitude IS NOT NULL
        GROUP BY s.property_locality, ss.avg_cagr, ss.total_sales
    """)

    if parquet_data is not None:
        return {"centroids": parquet_data}

    from app.database import get_db
    from app.models import Sale, SuburbSummary
    from sqlalchemy import func

    db = next(get_db())
    try:
        rows = (
            db.query(
                Sale.property_locality,
                func.avg(Sale.latitude).label("lat"),
                func.avg(Sale.longitude).label("lng"),
            )
            .filter(Sale.latitude != None)
            .group_by(Sale.property_locality)
            .all()
        )
        return {
            "centroids": [
                {"suburb": r.property_locality, "lat": r.lat, "lng": r.lng}
                for r in rows
            ]
        }
    finally:
        db.close()
