import requests
from bs4 import BeautifulSoup
import time
import logging
from urllib.parse import quote
from datetime import datetime

logger = logging.getLogger(__name__)

def search_realestate_listing(address: str, suburb: str, postcode: str) -> str:
    """
    Search for a property listing on realestate.com.au.
    
    Args:
        address: Street address (e.g., "64 Kent St").
        suburb: Suburb name.
        postcode: Postcode.
        
    Returns:
        The listing URL if found, None otherwise.
    """
    try:
        # Format search query
        search_query = f"{address}, {suburb} NSW {postcode}"
        
        # Search URL - using buy section for current listings
        search_url = f"https://www.realestate.com.au/buy/in-{suburb.lower().replace(' ', '+')},+nsw+{postcode}/list-1"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for property cards/listings
            listings = soup.find_all('article', class_='residential-card')
            
            for listing in listings:
                # Get the address from listing
                address_elem = listing.find('span', class_='address')
                if address_elem and address.lower() in address_elem.text.lower():
                    # Found a match, get the URL
                    link = listing.find('a', class_='details-link')
                    if link and link.get('href'):
                        listing_url = link['href']
                        if not listing_url.startswith('http'):
                            listing_url = f"https://www.realestate.com.au{listing_url}"
                        logger.info(f"Found realestate.com.au listing: {listing_url}")
                        return listing_url
        
        logger.debug(f"No realestate.com.au listing found for {search_query}")
        return None
    
    except Exception as e:
        logger.error(f"Error searching realestate.com.au: {e}")
        return None

def search_domain_listing(address: str, suburb: str, postcode: str) -> str:
    """
    Search for a property listing on domain.com.au.
    
    Args:
        address: Street address.
        suburb: Suburb name.
        postcode: Postcode.
        
    Returns:
        The listing URL if found, None otherwise.
    """
    try:
        # Format search query
        search_query = f"{address}, {suburb} NSW {postcode}"
        
        # Domain search URL
        search_url = f"https://www.domain.com.au/sale/{suburb.lower().replace(' ', '-')}-nsw-{postcode}/"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for property cards
            listings = soup.find_all('div', {'data-testid': 'listing-card-wrapper'})
            
            for listing in listings:
                # Get address
                address_elem = listing.find('h2', {'data-testid': 'address-line1'})
                if address_elem and address.lower() in address_elem.text.lower():
                    # Found a match, get the URL
                    link = listing.find('a', {'data-testid': 'listing-card-image-wrapper'})
                    if link and link.get('href'):
                        listing_url = link['href']
                        if not listing_url.startswith('http'):
                            listing_url = f"https://www.domain.com.au{listing_url}"
                        logger.info(f"Found domain.com.au listing: {listing_url}")
                        return listing_url
        
        logger.debug(f"No domain.com.au listing found for {search_query}")
        return None
    
    except Exception as e:
        logger.error(f"Error searching domain.com.au: {e}")
        return None

def search_property_listings(sale) -> dict:
    """
    Search both realestate.com.au and domain.com.au for a given sale record.
    
    Returns:
        A dictionary with 'realestate_url', 'domain_url', and 'timestamp'.
    """
    if not sale.property_house_number or not sale.property_street_name or not sale.property_locality:
        logger.warning(f"Sale {sale.id} missing address components")
        return {'realestate_url': None, 'domain_url': None, 'timestamp': datetime.utcnow()}
    
    address = f"{sale.property_house_number} {sale.property_street_name}"
    suburb = sale.property_locality
    postcode = str(sale.property_post_code) if sale.property_post_code else ''
    
    logger.info(f"Searching listings for: {address}, {suburb} {postcode}")
    
    # Search both sites
    realestate_url = search_realestate_listing(address, suburb, postcode)
    time.sleep(2)  # Be polite with requests
    
    domain_url = search_domain_listing(address, suburb, postcode)
    time.sleep(2)
    
    return {
        'realestate_url': realestate_url,
        'domain_url': domain_url,
        'timestamp': datetime.utcnow()
    }
