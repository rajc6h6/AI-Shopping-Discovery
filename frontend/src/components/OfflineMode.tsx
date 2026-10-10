'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import dynamic from 'next/dynamic';
import {
  MapPin, Phone, ArrowRight, Globe, Storefront,
  SpinnerGap, MapTrifold, CheckCircle, Warning
} from '@phosphor-icons/react';
import {
  streamOffline,
  type StoreResult,
  type OfflineResult,
  type TraceEvent,
} from '@/lib/api';
import styles from './OfflineMode.module.css';

// Lazy-load Leaflet map (avoids SSR crash)
const StoreMap = dynamic(() => import('./StoreMap'), {
  ssr: false,
  loading: () => <div className={styles.mapPlaceholder}>Loading map…</div>,
});

export interface OfflineSeller {
  name: string;
  price?: string;
  link?: string;
  platform?: string;
}

interface OfflineModeProps {
  sellers: OfflineSeller[];
  productTitle: string;
  productThumbnail: string | null;
  market: string;
  audience: 'male' | 'female';       // NEW — required
  isSpecific: boolean;                // NEW — true if item has a named brand
  verifiedResults: unknown[];         // NEW — for brand extraction on generic items
  onTrace?: (event: TraceEvent) => void;
}

type LocationState =
  | { status: 'idle' }
  | { status: 'requesting' }
  | { status: 'granted'; lat: number; lng: number }
  | { status: 'denied'; reason: string };

// Unique colours per seller (reused from StoreMap)
const SELLER_COLOURS = [
  '#059669', '#2563EB', '#DC2626', '#D97706', '#7C3AED',
  '#DB2777', '#0891B2', '#4F46E5',
];

export default function OfflineMode({
  sellers,
  productTitle,
  productThumbnail,
  market,
  audience,
  isSpecific,
  verifiedResults,
  onTrace,
}: OfflineModeProps) {
  const [stores, setStores] = useState<StoreResult[]>([]);
  const [onlineOnly, setOnlineOnly] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [location, setLocation] = useState<LocationState>({ status: 'idle' });
  const [selectedStore, setSelectedStore] = useState<string | null>(null);
  const [searchDone, setSearchDone] = useState(false);
  const [emptyRadius, setEmptyRadius] = useState(false);
  const [radiusKm, setRadiusKm] = useState(50);
  const [brandSourceNote, setBrandSourceNote] = useState<string | null>(null);
  const cardRefs = useRef<Record<string, HTMLDivElement | null>>({});

  // Seller → colour mapping
  const sellerColourMap = useRef<Record<string, string>>({});
  let ci = 0;
  sellers.forEach((s) => {
    if (!sellerColourMap.current[s.name]) {
      sellerColourMap.current[s.name] = SELLER_COLOURS[ci % SELLER_COLOURS.length];
      ci++;
    }
  });

  const requestLocation = useCallback(() => {
    setLocation({ status: 'requesting' });

    if (!navigator.geolocation) {
      setLocation({ status: 'denied', reason: 'Geolocation not supported by your browser.' });
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation({
          status: 'granted',
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        });
      },
      (err) => {
        setLocation({
          status: 'denied',
          reason:
            err.code === 1
              ? 'Location access was denied. Try again to allow it.'
              : 'Could not determine your location.',
        });
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
    );
  }, []);

  // Auto-request location on first render
  useEffect(() => {
    if (location.status === 'idle') requestLocation();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Run offline search once we have location
  useEffect(() => {
    if (
      (location.status !== 'granted') ||
      searchDone ||
      loading ||
      (sellers.length === 0 && (!verifiedResults || verifiedResults.length === 0))
    ) return;

    setLoading(true);
    setError(null);
    setStores([]);
    setOnlineOnly([]);

    streamOffline(
      sellers,
      productTitle,
      productThumbnail,
      location.lat,
      location.lng,
      market,
      audience,
      isSpecific,
      verifiedResults,
      {
        onTrace: (ev) => onTrace?.(ev),
        onStoreFound: (store) => setStores((prev) => [...prev, store]),
        onComplete: (result: OfflineResult) => {
          setOnlineOnly(result.online_only_sellers);
          setEmptyRadius(result.empty_radius ?? false);
          setRadiusKm(result.radius_km ?? 50);
          setBrandSourceNote(result.brand_source_note ?? null);
          setSearchDone(true);
          setLoading(false);
        },
        onError: (msg) => {
          setError(msg);
          setLoading(false);
        },
      }
    );
  }, [location, searchDone]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleMarkerClick = (placeId: string) => {
    setSelectedStore(placeId);
    cardRefs.current[placeId]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  // ── Location pending / requesting ────────────────────────────────────────
  if (location.status === 'idle' || location.status === 'requesting') {
    return (
      <div className={styles.locationPrompt}>
        <MapTrifold size={40} weight="light" className={styles.promptIcon} />
        <h3 className={styles.promptTitle}>Finding stores near you</h3>
        <p className={styles.promptDesc}>
          We need your location to show nearby stores. It's only used for this
          search and isn't stored on our servers.
        </p>
        <div className={styles.promptSpinner}>
          <SpinnerGap size={18} className={styles.spinner} />
          Requesting location…
        </div>
      </div>
    );
  }

  // ── Location denied ───────────────────────────────────────────────────────
  if (location.status === 'denied') {
    return (
      <div className={styles.locationPrompt}>
        <Warning size={40} weight="light" className={styles.promptIcon} />
        <h3 className={styles.promptTitle}>Location needed</h3>
        <p className={styles.promptDesc}>{location.reason}</p>
        <button className={styles.retryBtn} onClick={requestLocation}>
          Try Again
        </button>
      </div>
    );
  }

  // ── Main offline view ─────────────────────────────────────────────────────
  return (
    <div className={styles.offlineRoot}>
      {/* Honesty banner */}
      <div className={styles.honestyBanner}>
        <Storefront size={16} weight="bold" className={styles.honestyIcon} />
        <span>
          Showing nearby stores of sellers that list this product online.{' '}
          <strong>Stock isn't guaranteed</strong> — call to confirm.
        </span>
      </div>

      {/* Error */}
      {error && (
        <div className={styles.errorNote}>
          <Warning size={15} weight="bold" /> {error}
        </div>
      )}

      {/* Map + list layout */}
      <div className={styles.mapListLayout}>
        {/* Map */}
        <div className={styles.mapWrapper}>
          {stores.length > 0 || loading ? (
            <StoreMap
              stores={stores}
              userLat={location.lat}
              userLng={location.lng}
              selectedStore={selectedStore}
              radiusKm={radiusKm}
              onMarkerClick={handleMarkerClick}
            />
          ) : (
            <div className={styles.mapEmpty}>
              <MapTrifold size={36} weight="light" />
              <span>
                {loading 
                  ? 'Searching…' 
                  : emptyRadius 
                    ? `No stores found within ${radiusKm} km`
                    : 'No stores found nearby'
                }
              </span>
            </div>
          )}
          {loading && (
            <div className={styles.mapLoadingOverlay}>
              <SpinnerGap size={20} className={styles.spinner} />
              Searching {sellers.length} sellers…
            </div>
          )}
        </div>

        {/* Store card list */}
        <div className={styles.storeList}>
          {/* Seller legend */}
          {stores.length > 0 && (
            <div className={styles.legend}>
              {Array.from(new Set(stores.map((s) => s.seller_name))).map((name) => (
                <span key={name} className={styles.legendItem}>
                  <span
                    className={styles.legendDot}
                    style={{ background: sellerColourMap.current[name] || '#059669' }}
                  />
                  {name}
                </span>
              ))}
            </div>
          )}

          {/* Brand source note */}
          {brandSourceNote && (
            <div className={styles.brandSourceNote}>
              {brandSourceNote}
            </div>
          )}

          {/* Store cards */}
          {stores.map((store) => (
            <div
              key={store.place_id}
              ref={(el) => { cardRefs.current[store.place_id] = el; }}
              className={`${styles.storeCard} ${selectedStore === store.place_id ? styles.selected : ''}`}
              onClick={() => setSelectedStore(store.place_id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && setSelectedStore(store.place_id)}
            >
              {/* Seller colour accent */}
              <div
                className={styles.storeAccent}
                style={{ background: sellerColourMap.current[store.seller_name] || '#059669' }}
              />

              <div className={styles.storeCardBody}>
                {/* Thumbnail */}
                {store.thumbnail && (
                  <img
                    src={store.thumbnail}
                    alt={store.title}
                    className={styles.storeThumbnail}
                    loading="lazy"
                  />
                )}

                <div className={styles.storeInfo}>
                  {/* Header row */}
                  <div className={styles.storeHeader}>
                    <div>
                      <div className={styles.titleRow}>
                        <h4 className={styles.storeName}>{store.title}</h4>
                        {store.tier === 'tier1' && <span className={`${styles.tierBadge} ${styles.tier1}`}>Brand store</span>}
                        {store.tier === 'tier2' && <span className={`${styles.tierBadge} ${styles.tier2}`}>Multi-brand chain</span>}
                        {store.tier === 'tier3' && <span className={`${styles.tierBadge} ${styles.tier3}`}>Nearby shop</span>}
                      </div>
                      {store.store_type && (
                        <span className={styles.storeType}>{store.store_type}</span>
                      )}
                    </div>
                    {store.distance_km != null && (
                      <span className={styles.storeDistance}>
                        {store.distance_km < 1
                          ? `${Math.round(store.distance_km * 1000)}m`
                          : `${store.distance_km}km`}
                      </span>
                    )}
                  </div>

                  {/* Rating */}
                  {store.rating != null && (
                    <div className={styles.storeRating}>
                      <span className={styles.star}>★</span>
                      <span className={styles.ratingValue}>{store.rating}</span>
                      {store.reviews != null && (
                        <span className={styles.reviewCount}>
                          ({store.reviews.toLocaleString()})
                        </span>
                      )}
                    </div>
                  )}

                  {/* Open state */}
                  {store.open_state && (
                    <div
                      className={`${styles.openState} ${
                        store.open_state.toLowerCase().includes('open')
                          ? styles.open
                          : styles.closed
                      }`}
                    >
                      <CheckCircle size={13} weight="bold" />
                      {store.open_state}
                    </div>
                  )}

                  {/* Address */}
                  {store.address && (
                    <div className={styles.storeAddress}>
                      <MapPin size={13} weight="bold" />
                      <span>{store.address}</span>
                    </div>
                  )}

                  {/* Evidence line */}
                  <div className={styles.evidenceLine}>
                    {store.why_shown || store.evidence_text}
                  </div>

                  {/* Actions */}
                  <div className={styles.storeActions}>
                    {store.phone && (
                      <a
                        href={`tel:${store.phone}`}
                        className={styles.actionBtn}
                        onClick={(e) => e.stopPropagation()}
                        aria-label={`Call ${store.title}`}
                      >
                        <Phone size={14} weight="bold" /> Call
                      </a>
                    )}
                    <a
                      href={
                        store.maps_link ||
                        `https://www.google.com/maps/dir/?api=1&destination=${store.lat},${store.lng}`
                      }
                      target="_blank"
                      rel="noopener noreferrer"
                      className={styles.actionBtn}
                      onClick={(e) => e.stopPropagation()}
                      aria-label={`Directions to ${store.title}`}
                    >
                      <ArrowRight size={14} weight="bold" /> Directions
                    </a>
                    {store.website && (
                      <a
                        href={store.website}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`${styles.actionBtn} ${styles.actionBtnSecondary}`}
                        onClick={(e) => e.stopPropagation()}
                        aria-label={`Visit ${store.title} website`}
                      >
                        <Globe size={14} weight="bold" /> Website
                      </a>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}

          {/* Online-only section */}
          {searchDone && onlineOnly.length > 0 && (
            <div className={styles.onlineOnlySection}>
              <h4 className={styles.onlineOnlyTitle}>Online only — no stores found nearby</h4>
              <div className={styles.onlineOnlyList}>
                {onlineOnly.map((name, i) => (
                  <span key={i} className={styles.onlineOnlyTag}>{name}</span>
                ))}
              </div>
            </div>
          )}

          {/* Empty state */}
          {searchDone && stores.length === 0 && onlineOnly.length === 0 && (
            <div className={styles.emptyState}>
              <Storefront size={40} weight="light" className={styles.emptyIcon} />
              <h4>No stores found within {radiusKm} km</h4>
              <p>We checked nearby areas but couldn't find physical stores for these brands. You can still buy online.</p>
            </div>
          )}

          {/* Skeleton loading cards */}
          {loading && stores.length === 0 && (
            <>
              {[1, 2].map((i) => (
                <div key={i} className={`${styles.storeCard} ${styles.skeletonCard}`}>
                  <div className={styles.storeAccent} style={{ background: '#e5e7eb' }} />
                  <div className={styles.storeCardBody}>
                    <div className={styles.skeletonThumb} />
                    <div className={styles.storeInfo}>
                      <div className={styles.skeletonLine} style={{ width: '60%' }} />
                      <div className={styles.skeletonLine} style={{ width: '40%' }} />
                      <div className={styles.skeletonLine} style={{ width: '80%' }} />
                    </div>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
