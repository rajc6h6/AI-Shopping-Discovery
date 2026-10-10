'use client';

import { useEffect, useRef } from 'react';
import type { StoreResult } from '@/lib/api';

// Unique colour per seller
const SELLER_COLOURS = [
  '#059669', '#2563EB', '#DC2626', '#D97706', '#7C3AED',
  '#DB2777', '#0891B2', '#4F46E5',
];

interface StoreMapProps {
  stores: StoreResult[];
  userLat: number;
  userLng: number;
  selectedStore: string | null;
  radiusKm?: number;
  onMarkerClick: (placeId: string) => void;
}

export default function StoreMap({
  stores,
  userLat,
  userLng,
  selectedStore,
  radiusKm = 50,
  onMarkerClick,
}: StoreMapProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapInstanceRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const markersRef = useRef<Record<string, any>>({});

  // Build seller → colour mapping
  const sellerColours = useRef<Record<string, string>>({});
  let colourIdx = 0;
  stores.forEach((s) => {
    if (!sellerColours.current[s.seller_name]) {
      sellerColours.current[s.seller_name] =
        SELLER_COLOURS[colourIdx % SELLER_COLOURS.length];
      colourIdx++;
    }
  });

  // Initialise map once
  useEffect(() => {
    if (mapInstanceRef.current || !mapRef.current) return;

    // Dynamic import to avoid SSR issues
    import('leaflet').then((L) => {
      // Fix default icon paths in Next.js
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      delete (L.Icon.Default.prototype as any)._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl:
          'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
        iconUrl:
          'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
        shadowUrl:
          'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
      });

      // Prevent "Map container is already initialized" error in React Strict Mode
      if ((mapRef.current as any)._leaflet_id) {
        return;
      }

      const map = L.map(mapRef.current!, {
        center: [userLat, userLng],
        zoom: 13,
        zoomControl: true,
      });

      L.tileLayer(
        'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        {
          attribution:
            '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
          maxZoom: 19,
        }
      ).addTo(map);

      // User location marker (dark dot)
      const userIcon = L.divIcon({
        className: '',
        html: `<div style="width:14px;height:14px;background:#111;border:3px solid #fff;border-radius:50%;box-shadow:0 0 0 3px rgba(0,0,0,0.15);"></div>`,
        iconSize: [14, 14],
        iconAnchor: [7, 7],
      });
      L.marker([userLat, userLng], { icon: userIcon })
        .addTo(map)
        .bindPopup('<strong>Your location</strong>');

      // Draw the radius circle
      L.circle([userLat, userLng], {
        color: '#3b82f6',
        fillColor: '#3b82f6',
        fillOpacity: 0.05,
        weight: 1,
        radius: radiusKm * 1000
      }).addTo(map);

      mapInstanceRef.current = map;
    });

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Sync markers when stores change
  useEffect(() => {
    if (!mapInstanceRef.current) return;

    import('leaflet').then((L) => {
      const map = mapInstanceRef.current;

      // Clear existing store markers
      Object.values(markersRef.current).forEach((m) => m.remove());
      markersRef.current = {};

      if (stores.length === 0) return;

      const points: [number, number][] = [[userLat, userLng]];

      stores.forEach((store) => {
        const colour =
          sellerColours.current[store.seller_name] || '#059669';
        const isSelected = selectedStore === store.place_id;

        const icon = L.divIcon({
          className: '',
          html: `<div style="
            width:${isSelected ? 18 : 14}px;
            height:${isSelected ? 18 : 14}px;
            background:${colour};
            border:2.5px solid #fff;
            border-radius:50%;
            box-shadow:0 2px 6px rgba(0,0,0,0.25);
            cursor:pointer;
          "></div>`,
          iconSize: [isSelected ? 18 : 14, isSelected ? 18 : 14],
          iconAnchor: [isSelected ? 9 : 7, isSelected ? 9 : 7],
        });

        const marker = L.marker([store.lat, store.lng], { icon })
          .addTo(map)
          .bindPopup(
            `<strong>${store.title}</strong><br>${store.seller_name}${store.distance_km ? ` · ${store.distance_km}km` : ''}`
          );

        marker.on('click', () => onMarkerClick(store.place_id));
        markersRef.current[store.place_id] = marker;
        points.push([store.lat, store.lng]);
      });

      // Fit map to show all stores + user
      if (points.length > 1) {
        map.fitBounds(points, { padding: [40, 40], maxZoom: 15 });
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stores, selectedStore]);

  return (
    <>
      <link
        rel="stylesheet"
        href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
        crossOrigin=""
      />
      <div
        ref={mapRef}
        style={{ width: '100%', height: '100%', borderRadius: '12px' }}
      />
    </>
  );
}
