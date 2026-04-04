import logging
from typing import Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def calculate_cagr(
    first_price: float, last_price: float, years: float
) -> Tuple[float, float]:
    """
    Calculate Compound Annual Growth Rate (CAGR) and total growth.

    Args:
        first_price: Price at the start of the period.
        last_price: Price at the end of the period.
        years: Number of years between sales.

    Returns:
        A tuple of (cagr, total_growth).
    """
    if years < 0.5:  # Ignore if held for less than 6 months for CAGR purposes
        return 0.0, (last_price - first_price) / first_price

    try:
        cagr = ((last_price / first_price) ** (1 / years)) - 1
    except (ZeroDivisionError, OverflowError) as e:
        logger.error(f"Error calculating CAGR: {e}")
        cagr = 0.0

    total_growth = (last_price - first_price) / first_price
    return cagr, total_growth


if __name__ == "__main__":
    cagr, growth = calculate_cagr(500000.0, 750000.0, 5.0)
    print(f"CAGR: {cagr:.4f}, Total Growth: {growth:.4f}")
