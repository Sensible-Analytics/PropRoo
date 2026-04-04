# Australian Property Data Sources Research Report

## Executive Summary
This report outlines publicly available Australian property data sources that can supplement or replace the current NSW government data source used by PropRoo. The research covers federal, state, and territory-level sources with a focus on free/open access APIs and datasets suitable for integration.

## Current Data Source
- **Primary**: NSW Government property data via Valuer General NSW
- **Limitation**: Geographic restriction to New South Wales only

## Recommended Alternative Data Sources

### 1. Federal Government Sources (National Coverage)

#### Australian Bureau of Statistics (ABS)
- **API**: https://data.api.abs.gov.au/
- **Key Datasets**:
  - Residential Property Price Indexes (RPPI)
  - Building Approvals, Australia
  - Housing Finance, Australia
  - Total Value of Dwellings
  - Auction Clearance Rates
- **Access**: REST API with JSON responses
- **Frequency**: Monthly/Quarterly
- **Coverage**: National, State/Territory breakdown
- **Cost**: Free
- **Integration Notes**: Requires ABS API key for higher rate limits

#### Australian Government Data Portal (data.gov.au)
- **Portal**: https://www.data.gov.au/
- **Relevant Datasets**:
  - Residential property prices (CoreLogic RPDI)
  - Housing affordability metrics
  - Mortgage and lending statistics
  - Property tax and stamp duty data
- **Access**: Direct download (CSV, JSON, API endpoints)
- **Coverage**: National with state/territory specifics

### 2. State and Territory Sources

#### Victoria (VIC)
- **Data Vic**: https://discover.data.vic.gov.au/
  - Property sales statistics
  - Valuation data
  - Planning scheme amendments
  - Median house prices by suburb
- **Consumer Affairs Victoria**: https://www.consumer.vic.gov.au/
  - Property price guides
  - Rental bond data
  - Estate agent sales reports

#### Queensland (QLD)
- **Queensland Government Data**: https://www.data.qld.gov.au/
  - Property sales and transfers
  - Land valuations
  - Building approvals
  - Rental bond lodgements
- **Queensland Treasury**: Property market reports

#### Western Australia (WA)
- **Landgate**: https://www.landgate.wa.gov.au/
  - Sales evidence data (free sample available)
  - Valuation and property information
  - Landgate Maps and property reports
- **WA Government Data Catalog**: https://catalogue.data.wa.gov.au/
  - Sales evidence datasets
  - Property price indices

#### South Australia (SA)
- **Location SA**: https://location.sa.gov.au/
  - Property sales information
  - Valuation data
  - Planning and development data
- **Data.SA**: https://data.sa.gov.au/
  - Property sales datasets
  - Housing affordability metrics

#### Tasmania (TAS)
- **The LIST Data**: https://www.thelist.tas.gov.au/
  - Property sales and valuations
  - Title and plan information
  - Planning scheme data

#### Australian Capital Territory (ACT)
- **ACT Government Data**: https://www.data.act.gov.au/
  - Property sales and transfers
  - Land valuations
  - Development applications

#### Northern Territory (NT)
- **NT Government Data**: https://data.nt.gov.au/
  - Property sales information
  - Valuation data
  - Planning and development records

### 3. Semi-Government and Regulatory Sources

#### Australian Prudential Regulation Authority (APRA)
- **Data**: https://www.apra.gov.au/data-and-statistics
  - Housing lending statistics
  - Mortgage portfolio data
  - Property exposure metrics

#### Australian Taxation Office (ATO)
- **Taxation Statistics**: Property-related tax data
- **Capital gains property data**
- **Rental property income statistics**

### 4. Aggregated and Commercial Sources (Free Tiers)

#### Domain Developer API
- **Portal**: https://developer.domain.com.au/
- **Free Tier**: Limited daily calls
- **Data**: Property listings, sales history, suburb profiles
- **Note**: Requires developer registration

#### Real Estate Institute (REI) Sources
- **REIWA** (Western Australia): Market reports
- **REIV** (Victoria): Median price reports
- **REIQ** (Queensland): Market statistics

## Technical Integration Plan

### Data Collection Strategy
1. **Federal Layer**: ABS API for national indicators and trends
2. **State Layer**: Individual state APIs for granular transaction data
3. **Aggregation Layer**: Normalize data to common schema
4. **Caching Layer**: Implement intelligent caching to respect rate limits
5. **Fallback Layer**: Maintain current NSW source as baseline

### Schema Normalization
Proposed common property record schema:
```json
{
  "property_id": "string",
  "address": {
    "street_number": "string",
    "street_name": "string", 
    "suburb": "string",
    "state": "string",
    "postcode": "string",
    "latitude": "number",
    "longitude": "number"
  },
  "sale": {
    "price": "number",
    "date": "ISO date string",
    "property_type": "string",
    "bedrooms": "number",
    "bathrooms": "number",
    "car_spaces": "number",
    "land_size": "number",
    "building_area": "number"
  },
  "metadata": {
    "source": "string",
    "collected_at": "ISO timestamp",
    "confidence_score": "number"
  }
}
```

### Implementation Phases
**Phase 1**: Integrate ABS national indicators (immediate value)
**Phase 2**: Add Victoria and Queensland sources (highest volume)
**Phase 3**: Add remaining states/territories
**Phase 4**: Implement data validation and quality scoring
**Phase 5**: Add historical data backfill capabilities

## Risk Assessment and Mitigation

### Risks
1. **Inconsistent Data Formats**: Different states use different schemas
2. **Rate Limits**: Government APIs may have restrictive limits
3. **Data Quality**: Varying levels of data completeness and accuracy
4. **Change Management**: APIs and endpoints may change without notice

### Mitigation Strategies
1. **Adapter Pattern**: Create state-specific data adapters
2. **Rate Limiting**: Implement exponential backoff and request queuing
3. **Validation Layer**: Cross-reference between sources where possible
4. **Monitoring**: API health checks and automated alerting
5. **Fallback Chains**: Multiple sources for same data points

## Cost Analysis
- **Direct Costs**: $0 (all sources are free government data)
- **Indirect Costs**: Development time for integration and maintenance
- **Infrastructure**: Minimal increase (caching layer may require Redis or similar)
- **Ongoing**: ~5-10 hours/month for maintenance and monitoring

## Recommendations

### Immediate Actions (Next 2-4 weeks)
1. **Implement ABS API Integration**: Start with national indicators for immediate dashboard enhancements
2. **Create Data Adapter Framework**: Build foundation for adding state sources
3. **Add Victoria Data Source**: Highest transaction volume after NSW
4. **Implement Caching Layer**: Reduce API calls and improve response times

### Medium-term Goals (1-3 months)
1. **Complete State Coverage**: Integrate all states and territories
2. **Add Historical Backfill**: Populate database with 2-5 years of historical data
3. **Implement Data Quality Scoring**: Rank sources by reliability and completeness
4. **Build Analytics Layer**: Extract trends and insights from multi-source data

### Long-term Vision (3-6 months)
1. **Real-time Updates**: Webhook or streaming capabilities where available
2. **Predictive Modeling**: Machine learning models using multi-source data
3. **Cross-validation Engine**: Automatically resolve conflicts between sources
4. **API Export**: Offer normalized data as a service to other applications

## Conclusion
Australian property data availability has improved significantly with government open data initiatives. By integrating multiple sources, PropRoo can achieve:
- **National Coverage**: Beyond current NSW-only limitation
- **Enhanced Accuracy**: Cross-validation between sources
- **Richer Insights**: Combining transaction data with economic indicators
- **Future-proofing**: Reduced dependency on any single data source
- **Competitive Advantage**: More comprehensive data than most competitors

The recommended approach provides a scalable, maintainable path to national property data coverage while leveraging free government resources.