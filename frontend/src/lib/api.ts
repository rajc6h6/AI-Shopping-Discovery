import { createParser, type EventSourceMessage } from 'eventsource-parser';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

// ─── Shared data types ────────────────────────────────────────────────────────

export interface ParsedItem {
  category: string;
  colour: string | null;
  fit_style: string | null;
  material: string | null;
  gender: string | null;
  budget_hint: string | null;
  season: string | null;
  brand: string | null;
  model_name: string | null;
  is_specific: boolean;
  /** Source context: 'stated' | 'recommended' | 'inferred' */
  origin: 'stated' | 'recommended' | 'inferred';
  source_text: string;
  search_query: string;
}

export interface ProductCandidate {
  title: string;
  price: string | null;
  extracted_price: number | null;
  currency: string;
  source: string;
  link: string;
  thumbnail: string | null;
  rating: number | null;
  reviews: number | null;
  product_id: string | null;
  engine_used: string;
  position: number;
}

export interface AttributeScore {
  attribute: string;
  match: boolean;
  confidence: number;
  evidence: string;
}

export interface VerificationResult {
  overall_confidence: number;
  scores: AttributeScore[];
  label: string;
}

export interface ProductResult {
  candidate: ProductCandidate;
  verification: VerificationResult;
}

export interface ItemResult {
  item: ParsedItem;
  results: ProductResult[];
}

export interface TraceEvent {
  agent: string;
  action: string;
  engine: string;
  status?: string;
  market?: string;
  cached?: boolean;
}

export interface CompareOffer {
  platform: string;
  seller: string;
  price: string | null;
  extracted_price: number | null;
  currency: string;
  link: string;
  verified: boolean;
  verification: VerificationResult | null;
  shipping_info: string | null;
}

export interface CompareResult {
  offers: CompareOffer[];
  cheapest_index: number | null;
  search_engines_used: string[];
}

export interface StoreResult {
  title: string;
  seller_name: string;
  place_id: string;
  lat: number;
  lng: number;
  rating: number | null;
  reviews: number | null;
  phone: string | null;
  website: string | null;
  address: string | null;
  thumbnail: string | null;
  open_state: string | null;
  hours: string | null;
  operating_hours: Record<string, string> | null;
  store_type: string | null;
  distance_km: number | null;
  evidence_text: string;
  online_price: string | null;
  online_link: string | null;
  maps_link: string | null;
  tier: string;
  why_shown: string;
}

export interface OfflineResult {
  stores: StoreResult[];
  online_only_sellers: string[];
  search_engines_used: string[];
  serpapi_calls: number;
  empty_radius: boolean;
  radius_km: number;
  brand_source_note: string | null;
}

// ─── Shared SSE reader ────────────────────────────────────────────────────────

/** Callbacks for the shared SSE reader. */
interface SSEReadCallbacks {
  /** Called for every successfully parsed event. */
  onEvent: (eventName: string, data: unknown) => void;
  /** Called when an event's `data` field is not valid JSON. */
  onParseError: (eventName: string, raw: string) => void;
  /** Called when a network or stream-level error occurs. */
  onStreamError: (message: string) => void;
  /**
   * Called when the stream ends cleanly.
   * `hadDoneEvent` = false means no terminal event (complete / compare_complete /
   * offline_complete) was received — treat as an interrupted stream.
   */
  onStreamEnd: (hadDoneEvent: boolean) => void;
}

/** Terminal event names that indicate a successful stream conclusion. */
const DONE_EVENTS = new Set(['complete', 'compare_complete', 'offline_complete', 'error']);

/**
 * Shared, spec-compliant SSE stream reader.
 *
 * Uses `eventsource-parser` which handles:
 *  - LF, CRLF and bare CR line endings (including pairs split across chunks)
 *  - Buffering of incomplete lines across chunk boundaries
 *  - Comment lines (keepalives) — silently ignored
 *  - Multi-line data fields — joined with LF before delivery
 *  - UTF-8 multi-byte characters split across chunks (via TextDecoder stream mode)
 *
 * Supports cancellation via AbortSignal: the stream reader is always released,
 * preventing resource leaks when the user navigates away or starts a new search.
 *
 * Never swallows errors silently: JSON parse failures invoke `onParseError`,
 * network errors invoke `onStreamError`.
 */
async function readSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  callbacks: SSEReadCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  // stream: true preserves multi-byte characters across chunk boundaries
  const decoder = new TextDecoder('utf-8');
  let hadDoneEvent = false;
  // Track parse-error count for dev logging
  let parseErrorCount = 0;

  const parser = createParser({
    onEvent: (event: EventSourceMessage) => {
      const eventName = event.event ?? 'message';
      if (DONE_EVENTS.has(eventName)) hadDoneEvent = true;

      try {
        const parsed: unknown = JSON.parse(event.data);
        callbacks.onEvent(eventName, parsed);
      } catch {
        parseErrorCount++;
        if (process.env.NODE_ENV === 'development') {
          console.warn(
            `[SSE] JSON parse error — event: "${eventName}", raw:`,
            event.data,
            `(total parse errors: ${parseErrorCount})`,
          );
        }
        callbacks.onParseError(eventName, event.data);
      }
    },
  });

  try {
    while (true) {
      if (signal?.aborted) break;

      const { done, value } = await reader.read();
      if (done) break;

      // stream: true tells the decoder to hold incomplete multi-byte sequences
      // until the next chunk rather than replacing them with the replacement char.
      parser.feed(decoder.decode(value, { stream: true }));
    }
  } catch (err) {
    callbacks.onStreamError(err instanceof Error ? err.message : String(err));
    return;
  } finally {
    // Always release the lock — prevents leaks when AbortSignal fires or the
    // component unmounts while a stream is in flight.
    reader.releaseLock();
  }

  callbacks.onStreamEnd(hadDoneEvent);
}

// ─── Search ───────────────────────────────────────────────────────────────────

export type SSECallback = {
  onItemParsed?: (item: ParsedItem) => void;
  onProductFound?: (result: ItemResult) => void;
  onTrace?: (event: TraceEvent) => void;
  onError?: (message: string) => void;
  onComplete?: (data: { total_items: number; serpapi_calls: number }) => void;
  /**
   * Raised once if at least one SSE event had malformed JSON.
   * Use this to show a non-blocking warning ("Some results couldn't be displayed").
   */
  onParseWarning?: () => void;
};

export async function streamSearch(
  chatText: string,
  market: string,
  audience: 'male' | 'female',
  callbacks: SSECallback,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_text: chatText, market, audience }),
      signal,
    });
  } catch (err) {
    if ((err as Error)?.name === 'AbortError') return;
    callbacks.onError?.(`Connection failed: ${(err as Error).message}`);
    return;
  }

  if (!response.ok) {
    callbacks.onError?.(`Server error: ${response.status}`);
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    callbacks.onError?.('No response body from server.');
    return;
  }

  let hadParseError = false;

  await readSSEStream(
    reader,
    {
      onEvent: (eventName, data) => {
        switch (eventName) {
          case 'item_parsed':
            callbacks.onItemParsed?.(data as ParsedItem);
            break;
          case 'product_found':
            callbacks.onProductFound?.(data as ItemResult);
            break;
          case 'trace':
            callbacks.onTrace?.(data as TraceEvent);
            break;
          case 'error':
            callbacks.onError?.((data as { message: string }).message);
            break;
          case 'complete':
            callbacks.onComplete?.(data as { total_items: number; serpapi_calls: number });
            break;
        }
      },
      onParseError: (_eventName, _raw) => {
        hadParseError = true;
      },
      onStreamError: (msg) => callbacks.onError?.(msg),
      onStreamEnd: (hadDoneEvent) => {
        if (hadParseError) callbacks.onParseWarning?.();
        if (!hadDoneEvent) {
          callbacks.onError?.('The search was interrupted — please try again.');
        }
      },
    },
    signal,
  );
}

// ─── Compare ──────────────────────────────────────────────────────────────────

export async function streamCompare(
  productTitle: string,
  productAttributes: Record<string, string>,
  market: string,
  audience: 'male' | 'female',
  productId: string | null,
  immersiveToken: string | null,
  callbacks: {
    onTrace?: (event: TraceEvent) => void;
    onComplete?: (result: CompareResult) => void;
    onError?: (message: string) => void;
    onParseWarning?: () => void;
  },
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        product_title: productTitle,
        product_attributes: productAttributes,
        market,
        audience,
        product_id: productId,
        immersive_product_page_token: immersiveToken,
      }),
      signal,
    });
  } catch (err) {
    if ((err as Error)?.name === 'AbortError') return;
    callbacks.onError?.(`Connection failed: ${(err as Error).message}`);
    return;
  }

  if (!response.ok) {
    callbacks.onError?.(`Server error: ${response.status}`);
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    callbacks.onError?.('No response body from server.');
    return;
  }

  let hadParseError = false;

  await readSSEStream(
    reader,
    {
      onEvent: (eventName, data) => {
        switch (eventName) {
          case 'trace':
            callbacks.onTrace?.(data as TraceEvent);
            break;
          case 'compare_complete':
            callbacks.onComplete?.(data as CompareResult);
            break;
          case 'error':
            callbacks.onError?.((data as { message: string }).message);
            break;
        }
      },
      onParseError: () => {
        hadParseError = true;
      },
      onStreamError: (msg) => callbacks.onError?.(msg),
      onStreamEnd: (hadDoneEvent) => {
        if (hadParseError) callbacks.onParseWarning?.();
        if (!hadDoneEvent) {
          callbacks.onError?.('Price comparison was interrupted — please try again.');
        }
      },
    },
    signal,
  );
}

// ─── Offline ──────────────────────────────────────────────────────────────────

export async function streamOffline(
  sellers: Array<{ name: string; price?: string; link?: string; platform?: string }>,
  productTitle: string,
  productThumbnail: string | null,
  lat: number,
  lng: number,
  market: string,
  audience: 'male' | 'female',
  isSpecific: boolean,
  verifiedResults: unknown[],
  callbacks: {
    onTrace?: (event: TraceEvent) => void;
    onStoreFound?: (store: StoreResult) => void;
    onComplete?: (result: OfflineResult) => void;
    onError?: (message: string) => void;
    onParseWarning?: () => void;
  },
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/offline`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sellers,
        product_title: productTitle,
        product_thumbnail: productThumbnail,
        lat,
        lng,
        market,
        audience,
        is_specific: isSpecific,
        verified_results: verifiedResults,
      }),
      signal,
    });
  } catch (err) {
    if ((err as Error)?.name === 'AbortError') return;
    callbacks.onError?.(`Connection failed: ${(err as Error).message}`);
    return;
  }

  if (!response.ok) {
    callbacks.onError?.(`Server error: ${response.status}`);
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    callbacks.onError?.('No response body from server.');
    return;
  }

  let hadParseError = false;

  await readSSEStream(
    reader,
    {
      onEvent: (eventName, data) => {
        switch (eventName) {
          case 'trace':
            callbacks.onTrace?.(data as TraceEvent);
            break;
          case 'store_found':
            callbacks.onStoreFound?.(data as StoreResult);
            break;
          case 'offline_complete':
            callbacks.onComplete?.(data as OfflineResult);
            break;
          case 'error':
            callbacks.onError?.((data as { message: string }).message);
            break;
        }
      },
      onParseError: () => {
        hadParseError = true;
      },
      onStreamError: (msg) => callbacks.onError?.(msg),
      onStreamEnd: (hadDoneEvent) => {
        if (hadParseError) callbacks.onParseWarning?.();
        if (!hadDoneEvent) {
          callbacks.onError?.('Store search was interrupted — please try again.');
        }
      },
    },
    signal,
  );
}
