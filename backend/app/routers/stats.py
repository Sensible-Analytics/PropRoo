from fastapi import APIRouter, Query
from app.database import get_duck_conn, parquet_path
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def _parquet(table: str) -> str:
    return parquet_path(f"{table}.parquet")


@router.get("/global_summary")
async def global_summary(year: int = Query(2024)):
    suburb_path = _parquet("suburb_summary")
    street_path = _parquet("street_summary")

    conn = get_duck_conn()

    suburb_sql = f"""
        SELECT suburb, avg_cagr, unique_properties, total_sales
        FROM read_parquet('{suburb_path}')
        WHERE avg_cagr > 0
        ORDER BY avg_cagr DESC
        LIMIT 20
    """
    result = conn.execute(suburb_sql)
    columns = [desc[0] for desc in result.description]
    suburb_rows = result.fetchall()

    street_sql = f"""
        SELECT street_name, suburb, avg_cagr, total_sales
        FROM read_parquet('{street_path}')
        WHERE avg_cagr > 0
        ORDER BY avg_cagr DESC
        LIMIT 20
    """
    result = conn.execute(street_sql)
    columns = [desc[0] for desc in result.description]
    street_rows = result.fetchall()

    conn.close()

    return {
        "top_suburbs": [
            {
                "suburb": r[0],
                "avg_cagr": r[1],
                "unique_properties": r[2],
                "total_sales": r[3],
            }
            for r in suburb_rows
        ],
        "top_streets": [
            {
                "street_name": r[0],
                "suburb": r[1],
                "avg_cagr": r[2],
                "total_sales": r[3],
            }
            for r in street_rows
        ],
        "year": year,
    }


@router.get("/top_performers")
async def top_performers(
    year: int = Query(2024),
    property_type: str = Query(None),
):
    growth_path = _parquet("property_growth")
    sales_path = _parquet("sales")

    type_filter = ""
    if property_type:
        type_filter = f"AND s.primary_purpose = '{property_type}'"

    conn = get_duck_conn()

    sql = f"""
        SELECT
            pg.suburb,
            AVG(pg.avg_cagr) AS avg_cagr,
            COUNT(pg.property_id) AS property_count
        FROM read_parquet('{growth_path}') pg
        JOIN read_parquet('{sales_path}') s ON s.property_id = pg.property_id
        WHERE pg.last_sale_year <= {year} {type_filter}
        GROUP BY pg.suburb
        ORDER BY avg_cagr DESC
        LIMIT 20
    """
    result = conn.execute(sql)
    columns = [desc[0] for desc in result.description]
    rows = result.fetchall()
    conn.close()

    return {"growth": {"suburbs": [
        {
            "suburb": r[0],
            "avg_cagr": r[1],
            "property_count": r[2],
        }
        for r in rows
    ]}}


@router.get("/suburb_centroids")
async def suburb_centroids(year: int = Query(2024)):
    sales_path = _parquet("sales")
    suburb_path = _parquet("suburb_summary")

    conn = get_duck_conn()

    sql = f"""
        SELECT
            s.property_locality AS suburb,
            AVG(s.latitude) AS lat,
            AVG(s.longitude) AS lng,
            ss.avg_cagr,
            ss.total_sales
        FROM read_parquet('{sales_path}') s
        LEFT JOIN read_parquet('{suburb_path}') ss
            ON ss.suburb = s.property_locality
        WHERE EXTRACT(YEAR FROM s.contract_date::DATE) <= {year}
          AND s.latitude IS NOT NULL
        GROUP BY s.property_locality, ss.avg_cagr, ss.total_sales
    """
    result = conn.execute(sql)
    columns = [desc[0] for desc in result.description]
    rows = result.fetchall()
    conn.close()

    return {"centroids": [
        {
            "suburb": r[0],
            "lat": r[1],
            "lng": r[2],
            "avg_cagr": r[3],
            "total_sales": r[4],
        }
        for r in rows
    ]}
