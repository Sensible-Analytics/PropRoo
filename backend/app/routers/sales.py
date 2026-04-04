from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel
from datetime import date
from ..database import get_duck_conn, parquet_path
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
    cagr: Optional[float]
    total_growth: Optional[float]
    years_held: Optional[float]
    nearest_station: Optional[str]
    distance_to_station: Optional[float]
    realestate_url: Optional[str]
    domain_url: Optional[str]

    class Config:
        from_attributes = True


def _enrich_with_station(row: dict) -> dict:
    if row.get("latitude") and row.get("longitude"):
        station, dist = get_nearest_station(row["latitude"], row["longitude"])
        row["nearest_station"] = station
        row["distance_to_station"] = dist
    else:
        row["nearest_station"] = None
        row["distance_to_station"] = None
    return row


def _sales_path() -> str:
    return parquet_path("sales.parquet")


def _growth_path() -> str:
    return parquet_path("property_growth.parquet")


def _suburb_summary_path() -> str:
    return parquet_path("suburb_summary.parquet")


def _street_summary_path() -> str:
    return parquet_path("street_summary.parquet")


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
):
    sales_path = _sales_path()
    growth_path = _growth_path()

    where_clauses = []
    if suburb:
        where_clauses.append(f"s.property_locality ILIKE '%{suburb}%'")
    if min_area is not None:
        where_clauses.append(f"s.area >= {min_area}")
    if max_area is not None:
        where_clauses.append(f"s.area <= {max_area}")
    if property_type:
        where_clauses.append(f"s.primary_purpose = '{property_type}'")
    if min_growth is not None:
        where_clauses.append(f"pg.avg_cagr >= {min_growth / 100.0}")
    if min_price is not None:
        where_clauses.append(f"s.purchase_price >= {min_price}")
    if max_price is not None:
        where_clauses.append(f"s.purchase_price <= {max_price}")
    if start_date:
        where_clauses.append(f"s.contract_date >= '{start_date}'")
    if end_date:
        where_clauses.append(f"s.contract_date <= '{end_date}'")

    where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

    sql = f"""
        SELECT
            s.id, s.district_code, s.property_id, s.property_name,
            s.property_unit_number, s.property_house_number, s.property_street_name,
            s.property_locality, s.property_post_code, s.area, s.area_type,
            s.contract_date, s.settlement_date, s.purchase_price, s.zoning,
            s.nature_of_property, s.primary_purpose, s.latitude, s.longitude,
            s.realestate_url, s.domain_url,
            pg.avg_cagr AS cagr, pg.total_growth, pg.years_held
        FROM read_parquet('{sales_path}') s
        LEFT JOIN read_parquet('{growth_path}') pg
            ON pg.property_id = s.property_id
        WHERE {where_sql}
        ORDER BY s.contract_date DESC
        LIMIT {limit} OFFSET {skip}
    """

    conn = get_duck_conn()
    result = conn.execute(sql)
    columns = [desc[0] for desc in result.description]
    rows = result.fetchall()
    conn.close()

    response = []
    for row in rows:
        d = dict(zip(columns, row))
        d = _enrich_with_station(d)
        response.append(d)
    return response


@router.get("/stats/monthly_median")
def get_monthly_median(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    sales_path = _sales_path()
    where_clauses = []
    if start_date:
        where_clauses.append(f"contract_date >= '{start_date}'")
    if end_date:
        where_clauses.append(f"contract_date <= '{end_date}'")
    where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

    sql = f"""
        SELECT
            strftime('%Y-%m', contract_date) AS month,
            AVG(purchase_price) AS avg_price,
            COUNT(*) AS count
        FROM read_parquet('{sales_path}')
        WHERE {where_sql}
        GROUP BY month
        ORDER BY month
    """

    conn = get_duck_conn()
    result = conn.execute(sql)
    columns = [desc[0] for desc in result.description]
    rows = result.fetchall()
    conn.close()

    return [
        {"month": r[0], "avg_price": r[1], "count": r[2]}
        for r in rows
        if r[0] is not None
    ]


@router.get("/stats/top_suburbs")
def get_top_suburbs(
    limit: int = 10,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    sales_path = _sales_path()
    where_clauses = []
    if start_date:
        where_clauses.append(f"contract_date >= '{start_date}'")
    if end_date:
        where_clauses.append(f"contract_date <= '{end_date}'")
    where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

    sql = f"""
        SELECT
            property_locality AS suburb,
            COUNT(*) AS count,
            AVG(purchase_price) AS avg_price
        FROM read_parquet('{sales_path}')
        WHERE {where_sql}
        GROUP BY property_locality
        ORDER BY count DESC
        LIMIT {limit}
    """

    conn = get_duck_conn()
    result = conn.execute(sql)
    columns = [desc[0] for desc in result.description]
    rows = result.fetchall()
    conn.close()

    return [{"suburb": r[0], "count": r[1], "avg_price": r[2]} for r in rows]


@router.get("/property/{property_id}/history", response_model=List[SaleResponse])
def get_property_history(property_id: str, background_tasks: BackgroundTasks):
    sales_path = _sales_path()
    growth_path = _growth_path()

    sql = f"""
        SELECT
            s.id, s.district_code, s.property_id, s.property_name,
            s.property_unit_number, s.property_house_number, s.property_street_name,
            s.property_locality, s.property_post_code, s.area, s.area_type,
            s.contract_date, s.settlement_date, s.purchase_price, s.zoning,
            s.nature_of_property, s.primary_purpose, s.latitude, s.longitude,
            s.realestate_url, s.domain_url,
            pg.avg_cagr AS cagr, pg.total_growth, pg.years_held
        FROM read_parquet('{sales_path}') s
        LEFT JOIN read_parquet('{growth_path}') pg
            ON pg.property_id = s.property_id
        WHERE s.property_id = '{property_id}'
        ORDER BY s.contract_date ASC
    """

    conn = get_duck_conn()
    result = conn.execute(sql)
    columns = [desc[0] for desc in result.description]
    rows = result.fetchall()
    conn.close()

    response = []
    for row in rows:
        d = dict(zip(columns, row))
        d = _enrich_with_station(d)
        response.append(d)
    return response


@router.get("/stats/suburb_cagr")
def get_suburb_cagr(suburb: str, year: Optional[int] = 2024):
    suburb_path = _suburb_summary_path()
    sales_path = _sales_path()

    conn = get_duck_conn()

    # Get avg_cagr from suburb_summary
    sql = f"""
        SELECT suburb, avg_cagr
        FROM read_parquet('{suburb_path}')
        WHERE suburb = '{suburb}'
        LIMIT 1
    """
    result = conn.execute(sql)
    rows = result.fetchall()

    if rows:
        r = rows[0]
        avg_cagr = r[1]
    else:
        avg_cagr = None

    # Count unique properties for this suburb from sales
    count_sql = f"""
        SELECT COUNT(DISTINCT property_id) AS property_count
        FROM read_parquet('{sales_path}')
        WHERE property_locality = '{suburb}'
    """
    count_result = conn.execute(count_sql)
    count_row = count_result.fetchone()
    property_count = count_row[0] if count_row else 0

    conn.close()

    return {
        "suburb": suburb,
        "avg_cagr": avg_cagr,
        "property_count": property_count,
        "year": year,
    }


@router.get("/stats/street_trend")
def get_street_trend(street_name: str, suburb: str):
    growth_path = _growth_path()
    sales_path = _sales_path()

    conn = get_duck_conn()

    # Get year, avg_cagr from property_growth
    sql = f"""
        SELECT year, avg_cagr
        FROM read_parquet('{growth_path}')
        WHERE street_name = '{street_name}' AND suburb = '{suburb}'
        ORDER BY year ASC
    """
    result = conn.execute(sql)
    rows = result.fetchall()

    # For each year, compute property_count from sales.parquet
    trend = []
    for r in rows:
        year = r[0]
        count_sql = f"""
            SELECT COUNT(DISTINCT property_id) AS property_count
            FROM read_parquet('{sales_path}')
            WHERE property_street_name = '{street_name}'
              AND property_locality = '{suburb}'
              AND EXTRACT(YEAR FROM contract_date) = {year}
        """
        count_result = conn.execute(count_sql)
        count_row = count_result.fetchone()
        property_count = count_row[0] if count_row else 0
        trend.append({"year": r[0], "avg_cagr": r[1], "property_count": property_count})

    conn.close()
    return trend


@router.get("/stats/suburb_trend")
def get_suburb_trend(suburb: str):
    growth_path = _growth_path()
    sales_path = _sales_path()

    conn = get_duck_conn()

    # Get year, avg_cagr from property_growth (suburb-level rows)
    sql = f"""
        SELECT year, avg_cagr
        FROM read_parquet('{growth_path}')
        WHERE suburb = '{suburb}'
        ORDER BY year ASC
    """
    result = conn.execute(sql)
    rows = result.fetchall()

    # For each year, compute property_count from sales.parquet
    trend = []
    for r in rows:
        year = r[0]
        count_sql = f"""
            SELECT COUNT(DISTINCT property_id) AS property_count
            FROM read_parquet('{sales_path}')
            WHERE property_locality = '{suburb}'
              AND EXTRACT(YEAR FROM contract_date) = {year}
        """
        count_result = conn.execute(count_sql)
        count_row = count_result.fetchone()
        property_count = count_row[0] if count_row else 0
        trend.append({"year": r[0], "avg_cagr": r[1], "property_count": property_count})

    conn.close()
    return trend


@router.get("/stats/global_summary")
def get_global_summary():
    suburb_path = _suburb_summary_path()
    street_path = _street_summary_path()

    conn = get_duck_conn()

    suburb_sql = f"""
        SELECT suburb, avg_cagr, unique_properties, total_sales
        FROM read_parquet('{suburb_path}')
        ORDER BY avg_cagr DESC
        LIMIT 5
    """
    result = conn.execute(suburb_sql)
    columns = [desc[0] for desc in result.description]
    suburb_rows = result.fetchall()

    street_sql = f"""
        SELECT street_name, suburb, avg_cagr, total_sales
        FROM read_parquet('{street_path}')
        ORDER BY avg_cagr DESC
        LIMIT 5
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
            {"street_name": r[0], "suburb": r[1], "avg_cagr": r[2], "total_sales": r[3]}
            for r in street_rows
        ],
    }


@router.get("/stats/suburb_centroids")
def get_suburb_centroids():
    sales_path = _sales_path()

    sql = f"""
        SELECT
            property_locality,
            AVG(latitude) AS avg_lat,
            AVG(longitude) AS avg_lon
        FROM read_parquet('{sales_path}')
        WHERE latitude IS NOT NULL
        GROUP BY property_locality
    """

    conn = get_duck_conn()
    result = conn.execute(sql)
    columns = [desc[0] for desc in result.description]
    rows = result.fetchall()
    conn.close()

    return {r[0]: {"lat": r[1], "lon": r[2]} for r in rows}


@router.get("/stats/top_performers")
def get_top_performers(year: int = 2024, property_type: Optional[str] = None):
    suburb_summary_path = _suburb_summary_path()
    street_summary_path = _street_summary_path()
    sales_path = _sales_path()

    type_filter = ""
    if property_type:
        type_filter = f"AND s.primary_purpose = '{property_type}'"

    conn = get_duck_conn()

    # Use suburb_summary for top suburbs (has property_count)
    suburbs_sql = f"""
        SELECT suburb, avg_cagr, unique_properties AS property_count
        FROM read_parquet('{suburb_summary_path}')
        ORDER BY avg_cagr DESC
        LIMIT 10
    """
    result = conn.execute(suburbs_sql)
    suburb_rows = result.fetchall()

    # Use street_summary for top streets (has property_count)
    streets_sql = f"""
        SELECT street_name, suburb, avg_cagr, unique_properties AS property_count
        FROM read_parquet('{street_summary_path}')
        ORDER BY avg_cagr DESC
        LIMIT 10
    """
    result = conn.execute(streets_sql)
    street_rows = result.fetchall()

    suburb_act_sql = f"""
        SELECT property_locality, COUNT(*) AS sales_count
        FROM read_parquet('{sales_path}')
        WHERE EXTRACT(YEAR FROM contract_date) = {year} {type_filter}
        GROUP BY property_locality
        ORDER BY sales_count DESC
        LIMIT 10
    """
    result = conn.execute(suburb_act_sql)
    suburb_act_rows = result.fetchall()

    street_act_sql = f"""
        SELECT property_street_name, property_locality, COUNT(*) AS sales_count
        FROM read_parquet('{sales_path}')
        WHERE EXTRACT(YEAR FROM contract_date) = {year} {type_filter}
        GROUP BY property_street_name, property_locality
        ORDER BY sales_count DESC
        LIMIT 10
    """
    result = conn.execute(street_act_sql)
    street_act_rows = result.fetchall()

    conn.close()

    return {
        "growth": {
            "suburbs": [
                {"suburb": r[0], "avg_cagr": r[1], "property_count": r[2]}
                for r in suburb_rows
            ],
            "streets": [
                {
                    "street_name": r[0],
                    "suburb": r[1],
                    "avg_cagr": r[2],
                    "property_count": r[3],
                }
                for r in street_rows
            ],
        },
        "activity": {
            "suburbs": [{"suburb": r[0], "sales_count": r[1]} for r in suburb_act_rows],
            "streets": [
                {"street_name": r[0], "suburb": r[1], "sales_count": r[2]}
                for r in street_act_rows
            ],
        },
    }


@router.get("/stats/neighbors/suburbs")
def get_neighboring_suburbs(suburb: str):
    sales_path = _sales_path()
    suburb_path = _suburb_summary_path()

    conn = get_duck_conn()

    target_sql = f"""
        SELECT AVG(latitude) AS lat, AVG(longitude) AS lon
        FROM read_parquet('{sales_path}')
        WHERE property_locality = '{suburb}' AND latitude IS NOT NULL
    """
    target = conn.execute(target_sql).fetchone()
    if not target or not target[0]:
        conn.close()
        return []

    neighbors_sql = f"""
        SELECT
            property_locality,
            AVG(latitude) AS lat,
            AVG(longitude) AS lon,
            (AVG(latitude) - {target[0]}) * (AVG(latitude) - {target[0]})
            + (AVG(longitude) - {target[1]}) * (AVG(longitude) - {target[1]}) AS dist
        FROM read_parquet('{sales_path}')
        WHERE property_locality != '{suburb}' AND latitude IS NOT NULL
        GROUP BY property_locality
        ORDER BY dist
        LIMIT 10
    """
    result = conn.execute(neighbors_sql)
    columns = [desc[0] for desc in result.description]
    neighbor_rows = result.fetchall()

    if not neighbor_rows:
        conn.close()
        return []

    neighbor_names = [n[0] for n in neighbor_rows]
    names_str = ", ".join(f"'{n}'" for n in neighbor_names)
    stats_sql = f"""
        SELECT suburb, avg_cagr, total_sales, unique_properties
        FROM read_parquet('{suburb_path}')
        WHERE suburb IN ({names_str})
    """
    result = conn.execute(stats_sql)
    columns = [desc[0] for desc in result.description]
    stats_rows = result.fetchall()
    conn.close()

    neighbor_map = {n[0]: {"lat": n[1], "lon": n[2]} for n in neighbor_rows}

    return [
        {
            "suburb": s[0],
            "latitude": neighbor_map[s[0]]["lat"],
            "longitude": neighbor_map[s[0]]["lon"],
            "avg_cagr": s[1],
            "total_sales": s[2],
            "unique_properties": s[3],
        }
        for s in stats_rows
    ]


@router.get("/stats/neighbors/streets")
def get_neighboring_streets(street_name: str, suburb: str):
    sales_path = _sales_path()
    street_path = _street_summary_path()

    conn = get_duck_conn()

    target_sql = f"""
        SELECT AVG(latitude) AS lat, AVG(longitude) AS lon
        FROM read_parquet('{sales_path}')
        WHERE property_street_name = '{street_name}'
          AND property_locality = '{suburb}'
          AND latitude IS NOT NULL
    """
    target = conn.execute(target_sql).fetchone()

    if not target or not target[0]:
        conn.close()
        return []

    neighbors_sql = f"""
        SELECT
            property_street_name,
            property_locality,
            AVG(latitude) AS lat,
            AVG(longitude) AS lon,
            (AVG(latitude) - {target[0]}) * (AVG(latitude) - {target[0]})
            + (AVG(longitude) - {target[1]}) * (AVG(longitude) - {target[1]}) AS dist
        FROM read_parquet('{sales_path}')
        WHERE latitude IS NOT NULL
          AND (property_street_name != '{street_name}' OR property_locality != '{suburb}')
        GROUP BY property_street_name, property_locality
        ORDER BY dist
        LIMIT 20
    """
    result = conn.execute(neighbors_sql)
    columns = [desc[0] for desc in result.description]
    neighbor_rows = result.fetchall()

    res = []
    for n in neighbor_rows:
        stat_sql = f"""
            SELECT street_name, suburb, avg_cagr, total_sales
            FROM read_parquet('{street_path}')
            WHERE street_name = '{n[0]}' AND suburb = '{n[1]}'
            LIMIT 1
        """
        stat = conn.execute(stat_sql).fetchone()
        if stat:
            res.append(
                {
                    "street_name": stat[0],
                    "suburb": stat[1],
                    "latitude": n[2],
                    "longitude": n[3],
                    "avg_cagr": stat[2],
                    "total_sales": stat[3],
                }
            )

    conn.close()
    return res[:15]


@router.get("/stats/neighbors/properties")
def get_neighboring_properties(property_id: str):
    sales_path = _sales_path()
    growth_path = _growth_path()

    conn = get_duck_conn()

    target_sql = f"""
        SELECT property_id, property_house_number, property_street_name,
               property_locality, latitude, longitude, purchase_price
        FROM read_parquet('{sales_path}')
        WHERE property_id = '{property_id}' AND latitude IS NOT NULL
        LIMIT 1
    """
    target = conn.execute(target_sql).fetchone()
    if not target:
        conn.close()
        return []

    neighbors_sql = f"""
        SELECT
            s.property_id, s.property_house_number, s.property_street_name,
            s.property_locality, s.latitude, s.longitude, s.purchase_price,
            pg.avg_cagr,
            (s.latitude - {target[4]}) * (s.latitude - {target[4]})
            + (s.longitude - {target[5]}) * (s.longitude - {target[5]}) AS dist
        FROM read_parquet('{sales_path}') s
        LEFT JOIN read_parquet('{growth_path}') pg
            ON pg.property_id = s.property_id
        WHERE s.property_id != '{property_id}' AND s.latitude IS NOT NULL
        ORDER BY dist
        LIMIT 20
    """
    result = conn.execute(neighbors_sql)
    columns = [desc[0] for desc in result.description]
    rows = result.fetchall()
    conn.close()

    return [
        {
            "property_id": r[0],
            "address": f"{r[1]} {r[2]}",
            "suburb": r[3],
            "latitude": r[4],
            "longitude": r[5],
            "avg_cagr": r[7],
            "last_price": r[6],
        }
        for r in rows
    ]


@router.get("/stats/unified_map")
def get_unified_map_data(
    level: str = "suburb",
    year: int = 2024,
    property_type: Optional[str] = None,
):
    growth_path = _growth_path()
    sales_path = _sales_path()
    suburb_path = _suburb_summary_path()
    street_path = _street_summary_path()

    conn = get_duck_conn()

    if level == "suburb":
        # Join property_growth (for year filter) with suburb_summary (for property_count)
        top_sql = f"""
            SELECT pg.suburb, pg.avg_cagr, ss.unique_properties AS property_count
            FROM read_parquet('{growth_path}') pg
            LEFT JOIN read_parquet('{suburb_path}') ss ON pg.suburb = ss.suburb
            WHERE pg.year = {year}
            ORDER BY pg.avg_cagr DESC
            LIMIT 10
        """
        result = conn.execute(top_sql)
        top_performers = result.fetchall()

        clusters = []
        for i, tp in enumerate(top_performers):
            target_sql = f"""
                SELECT AVG(latitude) AS lat, AVG(longitude) AS lon
                FROM read_parquet('{sales_path}')
                WHERE property_locality = '{tp[0]}' AND latitude IS NOT NULL
            """
            target = conn.execute(target_sql).fetchone()
            if not target or not target[0]:
                continue

            neighbors_sql = f"""
                SELECT
                    property_locality,
                    AVG(latitude) AS lat,
                    AVG(longitude) AS lon,
                    (AVG(latitude) - {target[0]}) * (AVG(latitude) - {target[0]})
                    + (AVG(longitude) - {target[1]}) * (AVG(longitude) - {target[1]}) AS dist
                FROM read_parquet('{sales_path}')
                WHERE property_locality != '{tp[0]}' AND latitude IS NOT NULL
                GROUP BY property_locality
                ORDER BY dist
                LIMIT 5
            """
            result = conn.execute(neighbors_sql)
            columns = [desc[0] for desc in result.description]
            neighbors_raw = result.fetchall()

            neighbor_names = [n[0] for n in neighbors_raw]
            neighbor_map = {n[0]: {"lat": n[1], "lon": n[2]} for n in neighbors_raw}

            if neighbor_names:
                names_str = ", ".join(f"'{n}'" for n in neighbor_names)
                stats_sql = f"""
                    SELECT suburb, avg_cagr
                    FROM read_parquet('{suburb_path}')
                    WHERE suburb IN ({names_str})
                """
                result = conn.execute(stats_sql)
                columns = [desc[0] for desc in result.description]
                neighbor_stats = result.fetchall()
            else:
                neighbor_stats = []

            clusters.append(
                {
                    "id": tp[0],
                    "name": tp[0],
                    "lat": target[0],
                    "lon": target[1],
                    "cagr": tp[1],
                    "rank": i + 1,
                    "neighbors": [
                        {
                            "name": s[0],
                            "lat": neighbor_map[s[0]]["lat"],
                            "lon": neighbor_map[s[0]]["lon"],
                            "cagr": s[1],
                        }
                        for s in neighbor_stats
                        if s[0] in neighbor_map
                    ],
                }
            )

        conn.close()
        return {"clusters": clusters}

    elif level == "street":
        # Join property_growth (for year filter) with street_summary (for property_count)
        top_sql = f"""
            SELECT pg.street_name, pg.suburb, pg.avg_cagr, ss.unique_properties AS property_count
            FROM read_parquet('{growth_path}') pg
            LEFT JOIN read_parquet('{street_path}') ss
              ON pg.street_name = ss.street_name AND pg.suburb = ss.suburb
            WHERE pg.year = {year}
            ORDER BY pg.avg_cagr DESC
            LIMIT 10
        """
        result = conn.execute(top_sql)
        top_performers = result.fetchall()

        clusters = []
        for i, tp in enumerate(top_performers):
            target_sql = f"""
                SELECT AVG(latitude) AS lat, AVG(longitude) AS lon
                FROM read_parquet('{sales_path}')
                WHERE property_street_name = '{tp[0]}'
                  AND property_locality = '{tp[1]}'
                  AND latitude IS NOT NULL
            """
            target = conn.execute(target_sql).fetchone()
            if not target or not target[0]:
                continue

            neighbors_sql = f"""
                SELECT
                    property_street_name,
                    property_locality,
                    AVG(latitude) AS lat,
                    AVG(longitude) AS lon,
                    (AVG(latitude) - {target[0]}) * (AVG(latitude) - {target[0]})
                    + (AVG(longitude) - {target[1]}) * (AVG(longitude) - {target[1]}) AS dist
                FROM read_parquet('{sales_path}')
                WHERE latitude IS NOT NULL
                  AND (property_street_name != '{tp[0]}' OR property_locality != '{tp[1]}')
                GROUP BY property_street_name, property_locality
                ORDER BY dist
                LIMIT 5
            """
            result = conn.execute(neighbors_sql)
            columns = [desc[0] for desc in result.description]
            neighbors_raw = result.fetchall()

            cluster_neighbors = []
            for n in neighbors_raw:
                stat_sql = f"""
                    SELECT street_name, suburb, avg_cagr
                    FROM read_parquet('{street_path}')
                    WHERE street_name = '{n[0]}' AND suburb = '{n[1]}'
                    LIMIT 1
                """
                stat = conn.execute(stat_sql).fetchone()
                if stat:
                    cluster_neighbors.append(
                        {
                            "name": f"{stat[0]}, {stat[1]}",
                            "lat": n[2],
                            "lon": n[3],
                            "cagr": stat[2],
                        }
                    )

            clusters.append(
                {
                    "id": f"{tp[0]}_{tp[1]}",
                    "name": f"{tp[0]}, {tp[1]}",
                    "lat": target[0],
                    "lon": target[1],
                    "cagr": tp[2],
                    "rank": i + 1,
                    "neighbors": cluster_neighbors,
                }
            )

        conn.close()
        return {"clusters": clusters}

    conn.close()
    return {"clusters": []}
