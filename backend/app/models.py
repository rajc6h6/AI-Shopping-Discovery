"""Pydantic models shared across the application."""

from pydantic import BaseModel
from typing import Optional, Literal


# Audience type — extensible: add more values later without migration
AudienceType = Literal["male", "female"]


# --- Parser models ---

class ParsedItem(BaseModel):
    """A single shoppable item extracted from AI chat."""
    model_config = {"protected_namespaces": ()}

    category: str  # e.g. "sneakers", "overshirt", "chinos"
    colour: Optional[str] = None
    fit_style: Optional[str] = None
    material: Optional[str] = None
    gender: Optional[str] = None
    budget_hint: Optional[str] = None
    season: Optional[str] = None
    brand: Optional[str] = None
    model_name: Optional[str] = None
    is_specific: bool = False  # True only if brand+model named
    origin: Literal["stated", "recommended", "inferred"] = "stated"  # Source context
    source_text: str  # The original text this was extracted from
    search_query: str  # Constructed search query for SerpApi


class ParseResult(BaseModel):
    """Result of parsing an AI chat."""
    items: list[ParsedItem]
    raw_input_length: int
    parse_model: str


# --- Product discovery models ---

class ProductCandidate(BaseModel):
    """A product found via SerpApi search."""
    title: str
    price: Optional[str] = None
    extracted_price: Optional[float] = None
    currency: str = "USD"
    source: str  # Seller/retailer name
    link: str
    thumbnail: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    product_id: Optional[str] = None
    immersive_product_page_token: Optional[str] = None
    engine_used: str
    position: int


# --- Verification models ---

class AttributeScore(BaseModel):
    """Score for a single attribute match."""
    attribute: str  # e.g. "colour", "category", "brand", "audience"
    match: bool
    confidence: float  # 0.0 - 1.0
    evidence: str  # Why this score


class VerificationResult(BaseModel):
    """Full verification of a product against a parsed item."""
    overall_confidence: float
    scores: list[AttributeScore]
    label: str  # "Exact", "Variant", "Best match to your description"


# --- Compare models ---

class CompareOffer(BaseModel):
    """A single offer from the compare-prices flow."""
    platform: str
    seller: str
    price: Optional[str] = None
    extracted_price: Optional[float] = None
    currency: str = "USD"
    link: str
    verified: bool = False
    verification: Optional[VerificationResult] = None
    shipping_info: Optional[str] = None


class CompareRequest(BaseModel):
    """Request body for the compare endpoint."""
    product_title: str
    product_attributes: dict
    product_image: Optional[str] = None
    market: str = "in"
    audience: AudienceType  # required — no default; backend rejects missing
    product_id: Optional[str] = None
    immersive_product_page_token: Optional[str] = None


class CompareResult(BaseModel):
    """Result of comparing prices across platforms."""
    offers: list[CompareOffer]
    cheapest_index: Optional[int] = None
    search_engines_used: list[str]


# --- API models ---

class SearchRequest(BaseModel):
    """Request body for the main search endpoint."""
    chat_text: str
    market: str = "in"
    audience: AudienceType  # required — no default; backend rejects missing


# --- Offline / store models ---

class StoreResult(BaseModel):
    """A physical store found via Google Maps for a verified seller or brand."""
    title: str
    seller_name: str
    place_id: str
    lat: float
    lng: float
    rating: Optional[float] = None
    reviews: Optional[int] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    thumbnail: Optional[str] = None
    open_state: Optional[str] = None
    hours: Optional[str] = None
    operating_hours: Optional[dict] = None
    store_type: Optional[str] = None
    distance_km: Optional[float] = None
    evidence_text: str
    online_price: Optional[str] = None
    online_link: Optional[str] = None
    maps_link: Optional[str] = None
    tier: str = "tier3"
    why_shown: str = ""


class OfflineRequest(BaseModel):
    """Request body for the offline stores endpoint."""
    sellers: list[dict]
    product_title: str
    product_thumbnail: Optional[str] = None
    lat: float
    lng: float
    market: str = "in"
    audience: AudienceType       # required — no default
    is_specific: bool = False    # True if the item has a named brand
    verified_results: list[dict] = []  # Online results for brand extraction (generic items)


class OfflineResult(BaseModel):
    """Result of offline store search."""
    stores: list[StoreResult]
    online_only_sellers: list[str]
    search_engines_used: list[str]
    empty_radius: bool = False          # True when searched but nothing within 50 km
    radius_km: int = 50                 # Always 50 — sent to frontend for circle drawing
    brand_source_note: Optional[str] = None  # Shown in UI for generic-item brand path
