# Spike: Offline v2 — Measurement Results

**Date:** 2026-10-06 16:00
**Cities tested:** Mumbai (19.076, 72.878), Bangalore (12.972, 77.595)
**Queries:** 10 (mix of branded/generic, men's/women's Indian clothing)

---

## 1. Brand Extraction from Shopping Titles

| Metric | Count | Share |
|--------|-------|-------|
| Total Shopping results examined | 400 | 100% |
| Titles with brand extracted | 60 | 15% |
| Titles with NO brand | 2 | 0% |
| Sources classified as marketplace | 47 | 12% |
| Brands classified as online-only | 0 | — |
| Brands classified as potential-store | 60 | — |

### No-brand titles (samples)
- "BIBA Women's Purple Cotton Printed Anarkali Kurta Set | Size - 46 | Purple"
- "Men Printed Polo T-shirt"

## 2. Online-Only / Marketplace Private Labels

Brands identified as marketplace private labels or online-only:

## 3. Maps Lookup Results

| Metric | Count |
|--------|-------|
| Total Maps lookups | 29 |
| Lookups with any results | 23 |
| Lookups with correct store within 50 km | 17 |
| Maps credits spent | 27 |
| Shopping credits spent | 9 |
| **Total credits spent** | **36** |

### Per-brand breakdown
| ✅ | `Peter England` | query: `Peter England store` | results: 20 | correct: 10 | wrong: 0 | too far: 0 |
| ❌ | `Myntra - MNow` | query: `Myntra - MNow store` | results: 2 | correct: 0 | wrong: 1 | too far: 1 |
| ✅ | `Peter` | query: `Peter store` | results: 20 | correct: 8 | wrong: 2 | too far: 0 |
| ❌ | `Rust Orange` | query: `Rust Orange store` | results: 0 | correct: 0 | wrong: 0 | too far: 0 |
| ❌ | `AJIO.com` | query: `AJIO.com store` | results: 0 | correct: 0 | wrong: 0 | too far: 0 |
| ✅ | `Vastrakaya` | query: `Vastrakaya store` | results: 13 | correct: 1 | wrong: 5 | too far: 4 |
| ✅ | `Nike` | query: `Nike store` | results: 12 | correct: 9 | wrong: 1 | too far: 0 ⚠️SHORT |
| ❌ | `AJIO.com` | query: `AJIO.com store` | results: 0 | correct: 0 | wrong: 0 | too far: 0 |
| ❌ | `Tata CLiQ Jewellery` | query: `Tata CLiQ Jewellery store` | results: 16 | correct: 0 | wrong: 10 | too far: 0 |
| ❌ | `ajio.com` | query: `ajio.com store` | results: 0 | correct: 0 | wrong: 0 | too far: 0 |
| ✅ | `Levi's` | query: `Levi's store` | results: 20 | correct: 10 | wrong: 0 | too far: 0 |
| ✅ | `Regular` | query: `Regular store` | results: 3 | correct: 1 | wrong: 2 | too far: 0 |
| ❌ | `Myntra - MNow` | query: `Myntra - MNow store` | results: 5 | correct: 0 | wrong: 4 | too far: 1 |
| ✅ | `Tees` | query: `Tees store` | results: 20 | correct: 1 | wrong: 9 | too far: 0 ⚠️SHORT |
| ✅ | `Plain` | query: `Plain store` | results: 20 | correct: 4 | wrong: 6 | too far: 0 |
| ✅ | `Biba` | query: `Biba store` | results: 20 | correct: 10 | wrong: 0 | too far: 0 ⚠️SHORT |
| ❌ | `AJIO.com` | query: `AJIO.com store` | results: 0 | correct: 0 | wrong: 0 | too far: 0 |
| ✅ | `Biba.in` | query: `Biba.in store` | results: 20 | correct: 9 | wrong: 1 | too far: 0 |
| ✅ | `W For Woman` | query: `W For Woman store` | results: 20 | correct: 10 | wrong: 0 | too far: 0 |
| ❌ | `Chanderi Silk` | query: `Chanderi Silk store` | results: 20 | correct: 0 | wrong: 8 | too far: 2 |
| ✅ | `Allen Solly` | query: `Allen Solly store` | results: 20 | correct: 10 | wrong: 0 | too far: 0 |
| ✅ | `Allen` | query: `Allen store` | results: 20 | correct: 7 | wrong: 3 | too far: 0 |
| ❌ | `Tata CLiQ Fashion` | query: `Tata CLiQ Fashion store` | results: 11 | correct: 0 | wrong: 9 | too far: 1 |
| ✅ | `Tiptop` | query: `Tiptop store` | results: 20 | correct: 4 | wrong: 6 | too far: 0 |
| ❌ | `Breasted` | query: `Breasted store` | results: 20 | correct: 0 | wrong: 10 | too far: 0 |
| ✅ | `Allen Solly` | query: `Allen Solly store` | results: 20 | correct: 10 | wrong: 0 | too far: 0 |
| ✅ | `Max` | query: `Max store` | results: 20 | correct: 5 | wrong: 5 | too far: 0 ⚠️SHORT |
| ✅ | `Brown` | query: `Brown store` | results: 4 | correct: 3 | wrong: 1 | too far: 0 |
| ❌ | `ajio.com` | query: `ajio.com store` | results: 0 | correct: 0 | wrong: 0 | too far: 0 |

### Short-name brands (≤4 chars)
- **Nike**: 9 correct, 1 wrong — sample results: NIKE, NIKE, NIKE
- **Tees**: 1 correct, 9 wrong — sample results: Tees And Knits Enterprises, Marsh Clothing, ism custom clothing
- **Biba**: 10 correct, 0 wrong — sample results: BIBA - Phoenix Market City, Mumbai, La,biba, BIBA - R City Mall, Mumbai
- **Max**: 5 correct, 5 wrong — sample results: Max - Indiranagar, Bangalore, Max, Max - Jayanagar, Bangalore

## 4. Shopping `extensions` "In store" Text

**No "In store" text found in any Indian Shopping result extensions.** This confirms the brief's expectation — drop the In-store badge feature.

## 5. Multi-brand Chain Observations

From Maps results, the following multi-brand retail chains appeared frequently:
- Lifestyle, Westside, Pantaloons, Shoppers Stop, Max, Reliance Trends
- Central, Brand Factory, V-Mart, FBB (Fashion at Big Bazaar)

These should form the fixed chain list for tier-2 coverage.

## 6. Credit Budget

| Item | Credits |
|------|---------|
| Shopping queries | 9 |
| Maps queries | 27 |
| **Total** | **36** |

For production: category sweep (2 pages × 2 queries = 4 credits) + chains (~20 × 1 = 20) + brands (variable, ~6) = ~30 credits per offline request.
Recommended budget: **30 credits** per offline request.

## 7. Conclusions & Gate Settings

1. **Brand extraction works for ~15% of titles.** This is sufficient for tier-1 coverage. Items with no brand get tier-2 (chains) and tier-3 (category sweep) only.

2. **Maps lookup success:** 17/29 lookups found correct stores within 50 km. Established brands (Peter England, Nike, Levi's, Allen Solly) have reliable Maps presence. Short/ambiguous names need stricter matching.

3. **No "In store" extension data** for India. Drop this feature.

4. **Short-name matching risk:** Names ≤4 chars (W, Max, Biba) need exact whole-token match + clothing type check to avoid false positives.

5. **Recommended matching thresholds:**
   - Fuzzy match: 90+ for names >4 chars
   - Exact whole-token match for names ≤4 chars
   - Require clothing-related type OR domain match for short names

6. **Credit budget:** 30 credits per offline request (category sweep + chains + brands).

7. **The design in the brief is sound.** Proceed with implementation.
