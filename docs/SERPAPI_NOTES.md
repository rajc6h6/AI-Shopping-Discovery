# SerpApi Verified Notes

## Engines Available and Relevant

### Primary Discovery Engines
| Engine | API Endpoint | Purpose | Key Params |
|--------|-------------|---------|------------|
| **Google Shopping** | `engine=google_shopping` | Main product discovery | `q`, `location`, `gl`, `hl`, `tbs` (price range), `num` |
| **Google Shopping Light** | `engine=google_shopping_light` | Cheaper/faster shopping | Same as above, fewer fields returned |
| **Google Immersive Product** | `engine=google_immersive_product` | Deep product detail from Shopping result | `page_token` (from Shopping result's `product_id`) |

### Compare-Prices Engines
| Engine | API Endpoint | Purpose | Key Params |
|--------|-------------|---------|------------|
| **Amazon Search** | `engine=amazon` | Search Amazon products | `q`, `amazon_domain` |
| **Amazon Product** | `engine=amazon_product` | Get product detail | `product_id`, `amazon_domain` |
| **eBay Search** | `engine=ebay` | Search eBay listings | `_nkw` (query), `ebay_domain` |
| **eBay Product** | `engine=ebay_product` | eBay listing detail | `product_id` |
| **Walmart Search** | `engine=walmart` | Search Walmart | `query` |
| **Walmart Product** | `engine=walmart_product` | Walmart product detail | `product_id` |

### Visual Search (P1)
| Engine | API Endpoint | Purpose | Key Params |
|--------|-------------|---------|------------|
| **Google Lens** | `engine=google_lens` | Visual product search | `url` (publicly reachable image URL) |
| **Google Reverse Image** | `engine=google_reverse_image` | Reverse image search | `image_url` |

### Supplementary
| Engine | API Endpoint | Purpose |
|--------|-------------|---------|
| **Bing Shopping** | `engine=bing_shopping` | Additional platform for compare |
| **Bing Product** | `engine=bing_product` | Bing product detail |

## India-Specific Notes

### What Works
- **Google Shopping**: Supports `gl=in` (country), `hl=en` for India. Returns INR prices for many products.
- **Amazon**: `amazon_domain=amazon.in` works. Returns INR prices.
- **eBay**: Not India-specific but `ebay_domain=ebay.com` may ship to India.

### What Does NOT Work
- **Flipkart**: No SerpApi engine. Not reachable through SerpApi.
- **Myntra**: No SerpApi engine. Not reachable through SerpApi.
- **Walmart**: US-only (walmart.com). Does NOT support India.
- **Home Depot**: US-only. Not relevant for fashion.

### Design Implication
For India-based demos: Google Shopping (`gl=in`) and Amazon India (`amazon.in`) are the viable engines. eBay as supplementary. State this limitation honestly in the UI.

## serpapi-search-tools Python Package

- **Package**: `serpapi-search-tools` v1.0.0
- **Key tool**: `shopping_search()` — wraps Google Shopping API
- **Supports**: OpenAI Agents SDK, Pydantic AI, LangChain, LangGraph, CrewAI, and more
- **Configuration**: `allowed_engines`, `default_params`, `result_limit`, `provider`
- **Auto-detects** installed agent SDK

### Decision: Use direct SerpApi REST API vs serpapi-search-tools?
**Choice**: Use **direct REST API** (`serpapi.com/search.json?...`) via a thin Python wrapper.
**Reason**: 
1. We need fine-grained control over caching (by normalised request)
2. We need raw JSON for verification scoring
3. serpapi-search-tools abstracts away the raw response structure we need
4. We need to use engines (Immersive Product, Lens) not exposed by search-tools
5. We still get credit for "using SerpApi deeply" by hitting multiple engines directly

## Google Shopping API Response Structure (verified from KB examples)

```json
{
  "shopping_results": [
    {
      "position": 1,
      "title": "Product Name",
      "link": "https://...",
      "source": "Retailer Name",
      "price": "$XX.XX",
      "extracted_price": 29.99,
      "thumbnail": "https://...",
      "rating": 4.5,
      "reviews": 123,
      "product_id": "abc123",
      "serpapi_product_api": "https://serpapi.com/search.json?engine=google_product&product_id=abc123"
    }
  ]
}
```

## Google Immersive Product API
- Input: `page_token` from Google Shopping result
- Returns: detailed product info with sellers, prices, specifications, reviews
- **Key for Compare flow**: gives multiple sellers for same product

## Google Lens API
- Input: `url` parameter — must be a publicly reachable image URL
- Returns: `visual_matches` array with title, link, source, thumbnail, price
- **Limitation**: Image must be hosted publicly (not local file)
- **For image upload P1**: Need to upload user image to temporary public hosting first

## Credit Budget Design

| Action | Max SerpApi calls | Engines Used |
|--------|------------------|--------------|
| Parse chat | 0 | None (LLM only) |
| Find products per item | 2 | Google Shopping (1) + optional Shopping Light (1) |
| Verify per item | 0 | Uses data already fetched |
| Compare prices per product | 4 | Google Shopping (1) + Amazon (1) + eBay (1) + Immersive Product (1) |
| **Total per 5-item outfit** | **10** | Discovery only |
| **Total with 2 compares** | **18** | Discovery + 2 compare clicks |
| **Session hard cap** | **50** | Prevents runaway |

## Rate Limits & Error Handling
- SerpApi returns HTTP 429 on rate limit
- Returns `error` field in JSON on failures
- Handle: retry with exponential backoff (max 3 retries)
- Cache ALL responses by normalised request key (engine + sorted params hash)
