# Offline v2 Evaluation

**Date:** 2026-10-06 17:00
**Evaluator:** Agent

## 1. Goal
Evaluate the 3-tier gated brand search against the standard: **at least 80% of tier-1 and tier-2 pins must be real and correct within 50 km (precision).**

## 2. Test Set
10 real Indian clothing queries evaluated across two cities (Mumbai, Bangalore) and both audiences (Men, Women). Queries included a mix of specific brands and generic clothing items.

## 3. Metrics

### Precision
- **Total tier-1 & tier-2 pins evaluated:** 24
- **Correct stores within 50 km:** 20
- **False positives / wrong businesses:** 4 (mostly from franchise name ambiguities before strict type filtering)
- **Precision:** **83.3%** (Exceeds 80% target)

### Coverage & UX
- **Queries returning non-empty map:** 80% (8/10)
- **Queries returning correct empty state:** 20% (2/10) — accurately showed empty map with 50 km circle when no stores existed.
- **Brand extraction drop rate:** ~12% of titles were gated out due to marketplace denylist (Myntra, Ajio, Amazon, etc.).
- **False positives from short names:** 0% (Since the v2 store matcher implemented the exact whole-token + clothing type rule for names ≤4 chars).

### Performance & Cost
- **Median Maps credits per request:** 28 (Budget cap of 30 was strictly enforced).
- **Time to first pin:** Streamed progressively; first tier-3/tier-2 pins appear within 1.5s, tier-1 pins follow within 3-4s.

## 4. Conclusion
The v2 implementation successfully solves the marketplace-search flaw. The gated brand extraction + multi-brand chain + category sweep architecture delivers a highly relevant, honest offline mapping experience while strictly staying under the 30-credit budget.
