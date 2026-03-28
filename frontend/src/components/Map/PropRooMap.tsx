import React, { useMemo } from 'react';
import Map, { NavigationControl } from 'react-map-gl/maplibre';
import DeckGL from '@deck.gl/react';
import { GeoJsonLayer } from '@deck.gl/layers';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useAppStore } from '../../store/useAppStore';
import { useMapData } from '../../hooks/useMapData';

// Free OSM tiles via Stadia Maps
const MAP_STYLE = 'https://tiles.stadiamaps.com/styles/alidade_smooth.json';

// CAGR colour scale: red (negative) -> yellow -> green (high growth)
function cagrToColor(cagr: number): [number, number, number, number] {
  if (cagr <= 0)    return [220, 50, 50, 200];
  if (cagr < 0.05)  return [240, 180, 50, 200];
  if (cagr < 0.10)  return [100, 200, 80, 200];
  return                   [ 30, 150, 50, 220];
}

export default function PropRooMap() {
  const { viewState, setViewState, mapData } = useAppStore();
  useMapData();

  const hexLayer = useMemo(() => {
    if (!mapData?.features?.length) return null;

    return new GeoJsonLayer({
      id: 'h3-hexagons',
      data: mapData,
      filled: true,
      stroked: true,
      extruded: false,
      getFillColor: (f: any) => cagrToColor(f.properties.avg_cagr),
      getLineColor: [255, 255, 255, 60],
      lineWidthMinPixels: 0.5,
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 80],
      getTooltip: (f: any) => f && {
        html: [
          `Suburb: ${f.properties.suburb || 'Unknown'}`,
          `CAGR: ${(f.properties.avg_cagr * 100).toFixed(1)}%`,
          `Avg Price: $${f.properties.avg_price?.toLocaleString()}`,
          `Properties: ${f.properties.property_count}`,
        ].join('<br/>'),
      },
    });
  }, [mapData]);

  return (
    <DeckGL
      viewState={viewState}
      onViewStateChange={({ viewState: vs }: any) => setViewState(vs)}
      controller={true}
      layers={hexLayer ? [hexLayer] : []}
      style={{ position: 'relative', width: '100%', height: '100%' }}
    >
      <Map
        mapStyle={MAP_STYLE}
        style={{ width: '100%', height: '100%' }}
      >
        <NavigationControl position="top-right" />
      </Map>
    </DeckGL>
  );
}