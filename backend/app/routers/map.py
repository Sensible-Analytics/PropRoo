from fastapi import APIRouter, Query
from app.database import get_duck_conn, parquet_path
from app.h3_utils import h3_to_boundary
import h3
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def _parquet(table: str) -> str:
    return parquet_path(f"{table}.parquet")


@router.get("/viewport")
async def viewport_data(
    min_lat: float = Query(-38.0),
    max_lat: float = Query(-28.0),
    min_lng: float = Query(140.0),
    max_lng: float = Query(154.0),
    zoom: int = Query(8),
    year: int = Query(2024),
):
    resolution = zoom_to_resolution(zoom)
    sales_path = _parquet("sales")
    growth_path = _parquet("property_growth")

    conn = get_duck_conn()
    duck_rows = conn.execute(f"""
        SELECT
            CAST(s.latitude AS DOUBLE) AS lat,
            CAST(s.longitude AS DOUBLE) AS lng,
            CAST(s.purchase_price AS DOUBLE) AS price,
            CAST(s.contract_date AS VARCHAR) AS contract_date,
            s.property_locality AS locality,
            CAST(pg.avg_cagr AS DOUBLE) AS cagr
        FROM read_parquet('{sales_path}') s
        LEFT JOIN read_parquet('{growth_path}') pg ON pg.property_id = s.property_id
        WHERE s.latitude BETWEEN {min_lat} AND {max_lat}
          AND s.longitude BETWEEN {min_lng} AND {max_lng}
          AND EXTRACT(YEAR FROM s.contract_date) <= {year}
          AND s.latitude IS NOT NULL
    """).fetchall()
    conn.close()

    h3_groups = {}
    for row in duck_rows:
        lat, lng, price, contract_date, locality, cagr = row
        if lat is None or lng is None:
            continue
        try:
            h3_idx = h3.latlng_to_cell(float(lat), float(lng), resolution)
        except Exception as ex:
            logger.warning(f"H3 conversion failed for ({lat}, {lng}): {ex}")
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
