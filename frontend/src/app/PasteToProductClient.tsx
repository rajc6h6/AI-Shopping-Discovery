'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  ShoppingBag, MagnifyingGlass, CheckCircle, Warning, WarningCircle, 
  X, CaretDown, CaretUp, Star, Package, TrendUp, Sparkle, Tag, MagnifyingGlassPlus, ShieldCheck, ArrowRight,
  Wallet, CurrencyDollar, Lightning
} from '@phosphor-icons/react';
import {
  streamSearch,
  streamCompare,
  type ParsedItem,
  type ItemResult,
  type TraceEvent,
  type CompareResult,
} from '@/lib/api';
import OfflineMode, { type OfflineSeller } from '@/components/OfflineMode';
import { EXAMPLE_CHATS } from '@/lib/examples';
import { decodeChatFromHash } from '@/lib/extension-handoff';
import styles from './page.module.css';

export default function PasteToProductClient() {
  const [chatText, setChatText] = useState('');
  const [market, setMarket] = useState('in');
  const [audience, setAudience] = useState<'male' | 'female'>('male');
  const [isSearching, setIsSearching] = useState(false);
  const [parsedItems, setParsedItems] = useState<ParsedItem[]>([]);
  const [itemResults, setItemResults] = useState<ItemResult[]>([]);
  const [traceEvents, setTraceEvents] = useState<TraceEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [searchComplete, setSearchComplete] = useState(false);
  const [serpApiCalls, setSerpApiCalls] = useState(0);
  const [hasParseWarning, setHasParseWarning] = useState(false);
  const [extensionReceived, setExtensionReceived] = useState(false);

  // Offline mode toggle ('online' | 'offline')
  const [offlineMode, setOfflineMode] = useState<'online' | 'offline'>('online');

  // Compare state
  const [compareOpen, setCompareOpen] = useState(false);
  const [compareTitle, setCompareTitle] = useState('');
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null);
  const [isComparing, setIsComparing] = useState(false);
  const [compareTrace, setCompareTrace] = useState<TraceEvent[]>([]);

  const traceRef = useRef<HTMLDivElement>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  // Auto-scroll trace panel
  useEffect(() => {
    if (traceRef.current) {
      traceRef.current.scrollTop = traceRef.current.scrollHeight;
    }
  }, [traceEvents, compareTrace]);

  // Thin wrapper shared by the manual button and the extension hand-off.
  const runPipeline = useCallback(async (text: string) => {
    if (!text.trim() || isSearching) return;

    setIsSearching(true);
    setParsedItems([]);
    setItemResults([]);
    setTraceEvents([]);
    setError(null);
    setSearchComplete(false);
    setSerpApiCalls(0);
    setHasParseWarning(false);

    try {
      await streamSearch(text, market, audience as 'male' | 'female', {
        onItemParsed: (item) => {
          setParsedItems((prev) => [...prev, item]);
        },
        onProductFound: (result) => {
          setItemResults((prev) => [...prev, result]);
        },
        onTrace: (event) => {
          setTraceEvents((prev) => [...prev, { ...event, timestamp: new Date().toLocaleTimeString() } as TraceEvent & { timestamp: string }]);
        },
        onError: (message) => {
          setError(message);
        },
        onComplete: (data) => {
          setSearchComplete(true);
          setSerpApiCalls(data.serpapi_calls);
        },
        onParseWarning: () => {
          setHasParseWarning(true);
        },
      });
    } catch {
      setError('Failed to connect to the server. Make sure the backend is running.');
    } finally {
      setIsSearching(false);
    }
  }, [audience, isSearching, market]);

  const handleSearch = () => runPipeline(chatText);

  useEffect(() => {
    const text = decodeChatFromHash(window.location.hash);
    if (text === null) return;

    window.history.replaceState(null, '', window.location.pathname + window.location.search);
    window.queueMicrotask(() => {
      setChatText(text);
      setExtensionReceived(true);
      setTimeout(() => {
        const btn = document.getElementById('search-btn');
        if (btn) btn.focus();
      }, 50);
    });
  }, [runPipeline]);

  const handleCompare = async (title: string, attributes: Record<string, string>, productId: string | null, immersiveToken: string | null) => {
    setCompareOpen(true);
    setCompareTitle(title);
    setCompareResult(null);
    setIsComparing(true);
    setCompareTrace([]);

    try {
      await streamCompare(title, attributes, market, audience as 'male' | 'female', productId, immersiveToken, {
        onTrace: (event) => {
          setCompareTrace((prev) => [...prev, event]);
        },
        onComplete: (result) => {
          setCompareResult(result);
          setIsComparing(false);
        },
        onError: (message) => {
          setError(message);
          setIsComparing(false);
        },
      });
    } catch {
      setIsComparing(false);
    }
  };

  const loadExample = (text: string) => {
    setChatText(text);
    setParsedItems([]);
    setItemResults([]);
    setTraceEvents([]);
    setError(null);
    setSearchComplete(false);
  };

  const hasResults = parsedItems.length > 0 || itemResults.length > 0;

  return (
    <div className={styles.app}>
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <a href="/" className={styles.logo}>
            <ShoppingBag weight="fill" className={styles.logoIcon} />
            <span className={styles.logoText}>Paste-to-Product</span>
          </a>
          <div className={styles.headerControls}>
            <select
              className={styles.marketSelect}
              value={market}
              onChange={(e) => setMarket(e.target.value)}
              aria-label="Select market"
            >
              <option value="in">India (IN)</option>
              <option value="us">United States (US)</option>
            </select>
          </div>
        </div>
      </header>

      <main className={styles.main}>
        {extensionReceived && (
          <div className={styles.extensionBanner} role="status">
            Chat received from the extension
          </div>
        )}
        {/* Hero / Input Section */}
        {!hasResults && (
          <section className={styles.hero}>
            <div className={styles.heroText}>
              <span className={styles.heroEyebrow}>AI Product Discovery</span>
              <h1 className={styles.heroTitle}>
                AI tells you what to buy.
                <br />
                <span className={styles.heroTitleAccent}>We find it, prove it, and get the best price.</span>
              </h1>
              <p className={styles.heroSubtitle}>
                Paste any AI style advice chat. We&apos;ll find real, buyable products with
                verified confidence scores and cross-platform price comparison.
              </p>
            </div>
            
            <div className={styles.heroVisual}>
              <div className={styles.heroAmbient} />
              <div className={styles.heroVisualInner}>
                <div className={styles.heroWindowBar}>
                  <div className={styles.heroWindowDot} />
                  <div className={styles.heroWindowDot} />
                  <div className={styles.heroWindowDot} />
                </div>
                <div className={styles.heroWindowContent}>
                  <div className={styles.heroWindowLine} style={{ width: '90%' }} />
                  <div className={styles.heroWindowLine} style={{ width: '70%', marginBottom: '1rem' }} />
                  
                  <div className={styles.heroWindowTag}>
                    <CheckCircle weight="bold" size={12} />
                    Verified Match
                  </div>
                  
                  <div className={styles.heroWindowCard}>
                    <div className={styles.heroWindowThumb} />
                    <div className={styles.heroWindowMeta}>
                      <div className={styles.heroWindowTitle} />
                      <div className={styles.heroWindowPrice} />
                      <div className={styles.heroWindowConf} />
                    </div>
                  </div>
                  
                  <div className={styles.heroWindowCard}>
                    <div className={styles.heroWindowThumb} />
                    <div className={styles.heroWindowMeta}>
                      <div className={styles.heroWindowTitle} style={{ width: '60%' }} />
                      <div className={styles.heroWindowPrice} style={{ width: '30%' }} />
                      <div className={styles.heroWindowConf} style={{ width: '40%', opacity: 0.3 }} />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* Input Area */}
        <section className={styles.inputSection}>
          <div className={styles.inputCard}>
            <textarea
              className={styles.textarea}
              placeholder="Paste your AI style advice chat here..."
              value={chatText}
              onChange={(e) => setChatText(e.target.value)}
              rows={hasResults ? 3 : 8}
              maxLength={10000}
              aria-label="Paste AI chat text"
            />
            <div className={styles.inputFooter}>
              <span className={styles.charCount}>
                {chatText.length.toLocaleString()} / 10,000
              </span>
              <div className={styles.inputActions}>
                <div className={styles.audienceSelector}>
                  <button
                    className={`${styles.audienceBtn} ${audience === 'female' ? styles.active : ''}`}
                    onClick={() => setAudience('female')}
                    type="button"
                  >
                    Female
                  </button>
                  <button
                    className={`${styles.audienceBtn} ${audience === 'male' ? styles.active : ''}`}
                    onClick={() => setAudience('male')}
                    type="button"
                  >
                    Male
                  </button>
                </div>
                {chatText && (
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => setChatText('')}
                    type="button"
                  >
                    Clear
                  </button>
                )}
                <button
                  id="search-btn"
                  className="btn btn-cta"
                  onClick={handleSearch}
                  disabled={!chatText.trim() || !audience || isSearching}
                  title={!audience ? 'Select an audience to continue' : ''}
                  type="button"
                >
                  {isSearching ? (
                    <>
                      <span className={styles.spinner} />
                      Searching
                    </>
                  ) : (
                    <>
                      <MagnifyingGlass weight="bold" />
                      Find Products
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Example Chats */}
          {!hasResults && (
            <div className={styles.examples}>
              <p className={styles.examplesLabel}>Or try an example:</p>
              <div className={styles.exampleCards}>
                {EXAMPLE_CHATS.map((ex, i) => (
                  <button
                    key={i}
                    className={styles.exampleCard}
                    onClick={() => loadExample(ex.text)}
                    type="button"
                  >
                    <span className={styles.exampleTitle}>{ex.title}</span>
                    <span className={styles.exampleDesc}>{ex.description}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </section>

        {/* Error */}
        {error && (
          <div className={styles.errorBanner}>
            <div className={styles.errorText}>
              <WarningCircle size={20} weight="fill" />
              <span>{error}</span>
            </div>
            <button className="btn btn-ghost btn-sm" onClick={() => setError(null)}>
              Dismiss
            </button>
          </div>
        )}

        {/* Parse warning — non-blocking, raised when one or more SSE events had malformed JSON */}
        {hasParseWarning && (
          <div className={styles.warningBanner}>
            <Warning size={18} weight="fill" />
            <span>Some results couldn&apos;t be displayed due to a data issue.</span>
            <button className="btn btn-ghost btn-sm" onClick={() => setHasParseWarning(false)}>Dismiss</button>
          </div>
        )}

        {/* Results + Trace Layout */}
        {hasResults && (
          <div className={styles.resultsLayout}>
            {/* Results Column */}
            <div className={styles.resultsColumn} ref={resultsRef}>
              {/* Parsed Items Summary */}
              {parsedItems.length > 0 && (
                <div className={styles.parsedSummary}>
                  <div className={styles.parsedSummaryHeader}>
                    <Tag className={styles.parsedSummaryIcon} weight="bold" />
                    Found {parsedItems.length} items
                  </div>
                  <div className={styles.parsedTags}>
                    {parsedItems.map((item, i) => (
                      <span key={i} className={styles.parsedTag}>
                        {item.brand ? `${item.brand} ` : ''}{item.category}
                        {item.is_specific && <span className="badge badge-exact" style={{marginLeft: '0.25rem'}}>Specific</span>}
                        {item.origin === 'inferred' && (
                          <span className={styles.originInferred} title="Inferred from your need">suggested</span>
                        )}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Online / Offline Toggle */}
              {searchComplete && (
                <div className={styles.modeToggle}>
                  <button
                    className={`${styles.modeBtn} ${offlineMode === 'online' ? styles.modeBtnActive : ''}`}
                    onClick={() => setOfflineMode('online')}
                    aria-pressed={offlineMode === 'online'}
                  >
                    Online
                  </button>
                  <button
                    className={`${styles.modeBtn} ${offlineMode === 'offline' ? styles.modeBtnActive : ''}`}
                    onClick={() => setOfflineMode('offline')}
                    aria-pressed={offlineMode === 'offline'}
                  >
                    🗺 Offline
                  </button>
                </div>
              )}

              {/* Offline Mode Panel */}
              {offlineMode === 'offline' && searchComplete && (() => {
                const sellerSet = new Map<string, OfflineSeller>();
                itemResults.forEach((ir) => {
                  ir.results.slice(0, 2).forEach((pr) => {
                    const name = pr.candidate.source;
                    if (name && !sellerSet.has(name)) {
                      sellerSet.set(name, {
                        name,
                        price: pr.candidate.price || undefined,
                        link: pr.candidate.link || undefined,
                        platform: pr.candidate.engine_used || undefined,
                      });
                    }
                  });
                });
                const sellers = Array.from(sellerSet.values()).slice(0, 5);
                const firstThumb = itemResults[0]?.results[0]?.candidate.thumbnail || null;
                return (
                  <OfflineMode
                    sellers={sellers}
                    productTitle={itemResults.map(ir => ir.item.category).join(', ')}
                    productThumbnail={firstThumb}
                    market={market}
                    audience={audience as 'male' | 'female'}
                    isSpecific={itemResults.some(ir => ir.item.brand && ir.item.model_name)}
                    verifiedResults={itemResults.flatMap(ir => ir.results)}
                    onTrace={(ev) => setTraceEvents((prev) => [...prev, ev])}
                  />
                );
              })()}

              {/* Product Results — only shown in Online mode */}
              {offlineMode === 'online' && itemResults.map((ir, i) => (
                <div
                  key={i}
                  className={`${styles.itemSection} animate-reveal-up`}
                  style={{ animationDelay: `${i * 100}ms` }}
                >
                  <div className={styles.itemHeader}>
                    <div className={styles.itemHeaderRow}>
                      <h3 className={styles.itemName}>
                        {ir.item.brand ? `${ir.item.brand} ` : ''}
                        {ir.item.category}
                        {ir.item.colour ? ` · ${ir.item.colour}` : ''}
                      </h3>
                      {ir.item.origin === 'inferred' && (
                        <span className={styles.originInferredBadge}>✨ Suggested for you</span>
                      )}
                    </div>
                    <span className={styles.itemSource}>&ldquo;{ir.item.source_text}&rdquo;</span>
                  </div>

                  {ir.results.length === 0 ? (
                    <div className={styles.noResults}>
                      <Warning size={32} className={styles.noResultsIcon} weight="light" />
                      <div className={styles.noResultsTitle}>No matching products found</div>
                      <div className={styles.noResultsBody}>Try adjusting the description or switching markets.</div>
                    </div>
                  ) : (
                    <div className={styles.productGrid}>
                      {ir.results.map((pr, j) => (
                        <ProductCard
                          key={j}
                          candidate={pr.candidate}
                          verification={pr.verification}
                          onCompare={() => handleCompare(pr.candidate.title, {
                            category: ir.item.category,
                            brand: ir.item.brand || '',
                            model_name: ir.item.model_name || '',
                            colour: ir.item.colour || '',
                            material: ir.item.material || '',
                          }, pr.candidate.product_id, (pr.candidate as any).immersive_product_page_token || null)}
                          rank={j}
                        />
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {/* Loading skeleton (minimalist-ui matching layout) */}
              {isSearching && itemResults.length < parsedItems.length && (
                <div className={styles.skeletonItem}>
                  <div className={`skeleton ${styles.skeletonHeader}`} />
                  <div className={`skeleton ${styles.skeletonSubheader}`} />
                  <div className={styles.skeletonGrid}>
                    {[1, 2, 3].map((n) => (
                      <div key={n} className={`skeleton ${styles.skeletonCard}`} />
                    ))}
                  </div>
                </div>
              )}

              {/* Completion summary */}
              {searchComplete && (
                <div className={`${styles.completionBanner} animate-reveal-in`}>
                  <CheckCircle weight="fill" className={styles.completionIcon} />
                  <span>Search complete — found <span className={styles.completionStat}>{itemResults.length}</span> items using <span className={styles.completionStat}>{serpApiCalls}</span> API calls</span>
                </div>
              )}

              {/* ── Outfit Summary — Total cost + cheapest combination ── */}
              {searchComplete && itemResults.length > 1 && (() => {
                // For each item, find the cheapest verified product
                const outfitPicks = itemResults.map((ir) => {
                  const withPrice = ir.results.filter(
                    (pr) => pr.candidate.extracted_price && pr.candidate.extracted_price > 0
                  );
                  if (withPrice.length === 0) return null;
                  // Sort by price ascending, pick cheapest
                  const sorted = [...withPrice].sort(
                    (a, b) => (a.candidate.extracted_price ?? Infinity) - (b.candidate.extracted_price ?? Infinity)
                  );
                  return {
                    item: ir.item,
                    pick: sorted[0],
                  };
                }).filter(Boolean) as { item: ParsedItem; pick: import('@/lib/api').ProductResult }[];

                if (outfitPicks.length === 0) return null;

                const totalCost = outfitPicks.reduce(
                  (sum, op) => sum + (op.pick.candidate.extracted_price ?? 0), 0
                );
                const currency = outfitPicks[0]?.pick.candidate.currency ?? 'USD';
                const currencySymbol = currency === 'INR' ? '₹' : currency === 'GBP' ? '£' : currency === 'EUR' ? '€' : '$';

                // Group by source/platform to find which platform is cheapest overall
                const platformTotals: Record<string, { total: number; count: number }> = {};
                outfitPicks.forEach((op) => {
                  const src = op.pick.candidate.source;
                  if (!platformTotals[src]) platformTotals[src] = { total: 0, count: 0 };
                  platformTotals[src].total += op.pick.candidate.extracted_price ?? 0;
                  platformTotals[src].count += 1;
                });
                const topPlatform = Object.entries(platformTotals).sort(
                  (a, b) => b[1].count - a[1].count
                )[0];

                return (
                  <div className={`${styles.outfitSummary} animate-reveal-up`}>
                    <div className={styles.outfitSummaryHeader}>
                      <div className={styles.outfitSummaryTitle}>
                        <Wallet weight="bold" className={styles.outfitSummaryIcon} />
                        Complete Outfit Summary
                      </div>
                      <div className={styles.outfitTotalCost}>
                        <span className={styles.outfitTotalLabel}>Total Outfit Cost</span>
                        <span className={styles.outfitTotalPrice}>
                          {currencySymbol}{totalCost.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                        </span>
                      </div>
                    </div>

                    <div className={styles.outfitItems}>
                      {outfitPicks.map((op, i) => (
                        <div key={i} className={styles.outfitItem}>
                          <div className={styles.outfitItemInfo}>
                            <span className={styles.outfitItemCategory}>
                              {op.item.brand ? `${op.item.brand} ` : ''}{op.item.category}
                            </span>
                            <a
                              href={op.pick.candidate.link}
                              target="_blank"
                              rel="noopener noreferrer"
                              className={styles.outfitItemProduct}
                            >{op.pick.candidate.title.slice(0, 50)}{op.pick.candidate.title.length > 50 ? '…' : ''}</a>
                          </div>
                          <div className={styles.outfitItemRight}>
                            <span className={styles.outfitItemPrice}>{op.pick.candidate.price}</span>
                            <span className={styles.outfitItemSource}>{op.pick.candidate.source}</span>
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className={styles.outfitFooter}>
                      <div className={styles.outfitInsight}>
                        <Lightning weight="fill" className={styles.outfitInsightIcon} />
                        <span>
                          Cheapest verified combination across <strong>{Object.keys(platformTotals).length} platforms</strong>
                          {topPlatform && ` — most items from ${topPlatform[0]}`}
                        </span>
                      </div>
                      <div className={styles.outfitPerItem}>
                        <CurrencyDollar weight="bold" size={14} />
                        <span>
                          {currencySymbol}{Math.round(totalCost / outfitPicks.length).toLocaleString()} avg per item · {outfitPicks.length} of {itemResults.length} items priced
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })()}
            </div>

            {/* Trace Panel */}
            <div className={`${styles.tracePanel} animate-reveal-right`}>
              <div className={styles.tracePanelHeader}>
                <div className={styles.tracePanelTitle}>
                  <TrendUp weight="bold" className={styles.tracePanelIcon} />
                  Agent Trace
                </div>
                {isSearching ? (
                  <div className="badge badge-live">
                    <div className={styles.traceLiveDot} /> Live
                  </div>
                ) : (
                  <div className="badge badge-cached">Done</div>
                )}
              </div>
              <div className={styles.traceScroll} ref={traceRef}>
                {traceEvents.map((event, i) => (
                  <div
                    key={i}
                    className={`${styles.traceEvent} animate-reveal-in`}
                  >
                    <div className={styles.traceAgentRow}>
                      <Sparkle weight="fill" className={`${styles.traceAgentIcon} ${
                        event.agent === 'parser' ? styles.traceAgentParser : 
                        event.agent === 'finder' ? styles.traceAgentFinder : 
                        styles.traceAgentCompare
                      }`} />
                      <span className={styles.traceAgentName}>{event.agent}</span>
                      {event.cached && <span className="badge badge-cached">cached</span>}
                    </div>
                    <div className={styles.traceAction}>{event.action}</div>
                    <div className={styles.traceBottom}>
                      <span className={styles.traceEnginePill}>{event.engine}</span>
                      <span className={`${styles.traceStatus} ${
                        event.status === 'complete' ? styles.traceStatusDone :
                        event.status === 'error' ? styles.traceStatusError :
                        styles.traceStatusRunning
                      }`}>
                        {event.status === 'complete' ? '✓' : event.status === 'error' ? '✗' : '●'}
                      </span>
                    </div>
                  </div>
                ))}
                {traceEvents.length === 0 && !isSearching && (
                  <div className={styles.traceEmpty}>
                    Trace events will appear here when you search.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Compare Modal */}
      {compareOpen && (
        <div className={styles.modalOverlay} onClick={() => !isComparing && setCompareOpen(false)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <div className={styles.modalHeaderText}>
                <h2 className={styles.modalTitle}>
                  <MagnifyingGlassPlus weight="bold" style={{ verticalAlign: 'text-bottom', marginRight: '6px' }} />
                  Compare Prices
                </h2>
                <p className={styles.modalSubtitle}>{compareTitle}</p>
              </div>
              <button
                className="btn btn-ghost"
                onClick={() => setCompareOpen(false)}
                aria-label="Close"
              >
                <X weight="bold" size={20} />
              </button>
            </div>

            <div className={styles.modalBody}>
              {/* Compare trace */}
              <div className={styles.compareTrace}>
                {compareTrace.map((event, i) => (
                  <div key={i} className={styles.compareTraceEvent}>
                    <TrendUp weight="bold" />
                    <span>{event.action}</span>
                    {event.status === 'complete' && <CheckCircle weight="fill" className={styles.traceStatusDone} />}
                  </div>
                ))}
              </div>

              {isComparing && (
                <div className={styles.compareLoading}>
                  <span className={styles.spinner} />
                  <span>Searching across platforms...</span>
                </div>
              )}

              {compareResult && (
                <div className={`${styles.compareResults} animate-reveal-in`}>
                  {compareResult.offers.length === 0 ? (
                    <div className={styles.noResults}>
                      <span>No verified offers found across other platforms.</span>
                      <p>Only one seller may carry this product.</p>
                    </div>
                  ) : (
                    <div className={styles.compareOffers}>
                      {compareResult.offers.map((offer, i) => (
                        <div
                          key={i}
                          className={`${styles.compareOffer} ${
                            i === compareResult.cheapest_index ? styles.compareOfferCheapest : ''
                          } animate-reveal-up`}
                          style={{ animationDelay: `${i * 100}ms` }}
                        >
                          {i === compareResult.cheapest_index && (
                            <div className={styles.cheapestBadge}>Cheapest</div>
                          )}
                          <div className={styles.offerPlatform}>{offer.platform}</div>
                          <div className={styles.offerSeller}>{offer.seller}</div>
                          <div className={styles.offerPrice}>
                            {offer.price || 'Price unavailable'}
                          </div>
                          <div className={styles.offerVerifiedCol}>
                            {offer.verified ? (
                              <span className="badge badge-exact">
                                <ShieldCheck weight="fill" size={14} /> Verified match
                              </span>
                            ) : (
                              <span className="badge badge-weak">
                                <WarningCircle weight="fill" size={14} /> Unverified
                              </span>
                            )}
                          </div>
                          <a
                            href={offer.link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="btn btn-secondary btn-xs"
                          >
                            View <ArrowRight weight="bold" />
                          </a>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className={styles.compareFooter}>
                    Searched: {compareResult.search_engines_used.join(', ')}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className={styles.footer}>
        <p>Built with <a href="https://serpapi.com" target="_blank" rel="noopener noreferrer">SerpApi</a> · All products from real marketplaces · No fabricated data</p>
      </footer>
    </div>
  );
}

/* Product Card Component */
function ProductCard({
  candidate,
  verification,
  onCompare,
  rank,
}: {
  candidate: import('@/lib/api').ProductCandidate;
  verification: import('@/lib/api').VerificationResult;
  onCompare: () => void;
  rank: number;
}) {
  const [showBreakdown, setShowBreakdown] = useState(false);

  const confidenceClass =
    verification.overall_confidence >= 0.8 ? 'confidence-high' :
    verification.overall_confidence >= 0.5 ? 'confidence-medium' :
    'confidence-low';

  const labelClass =
    verification.label === 'Exact' ? 'badge-exact' :
    verification.label === 'Variant' ? 'badge-variant' :
    verification.overall_confidence >= 0.5 ? 'badge-match' :
    'badge-weak';

  return (
    <div className={`${styles.productCard} ${rank === 0 ? styles.productCardHero : ''} animate-grid-item`} style={{ animationDelay: `${rank * 100}ms` }}>
      {/* Image */}
      <div className={styles.productImageWrapper}>
        {candidate.thumbnail ? (
          <img
            className={styles.productImage}
            src={candidate.thumbnail}
            alt={candidate.title}
            loading="lazy"
          />
        ) : (
          <div className={styles.productImagePlaceholder}>
            <Package size={48} weight="light" />
          </div>
        )}
      </div>

      {/* Content */}
      <div className={styles.productContent}>
        <div className={styles.productMetaRow}>
          <span className={`badge ${labelClass}`}>{verification.label}</span>
          {rank === 0 && (
            <span className={styles.productBestBadge}>
              <Star weight="fill" size={12} style={{marginRight: '2px', verticalAlign: 'text-bottom'}} />
              Best Match
            </span>
          )}
        </div>

        <h4 className={styles.productTitle}>{candidate.title}</h4>

        <div className={styles.productPriceRow}>
          <span className={styles.productPrice}>
            {candidate.price || 'Price unavailable'}
          </span>
          <span className={styles.productSeller}>{candidate.source}</span>
        </div>

        {/* Confidence */}
        <div className={styles.confidenceSection}>
          <div className={styles.confidenceRow}>
            <span className={styles.confidenceLabel}>Confidence: {Math.round(verification.overall_confidence * 100)}%</span>
            <button
              className={styles.confidenceToggle}
              onClick={() => setShowBreakdown(!showBreakdown)}
              aria-label="Toggle confidence breakdown"
              aria-expanded={showBreakdown}
            >
              {showBreakdown ? <CaretUp weight="bold" /> : <CaretDown weight="bold" />}
            </button>
          </div>
          <div className="confidence-bar">
            <div
              className={`confidence-bar-fill ${confidenceClass}`}
              style={{ width: `${verification.overall_confidence * 100}%` }}
            />
          </div>

          {showBreakdown && (
            <div className={`${styles.breakdown} animate-reveal-in`}>
              {verification.scores.map((score, i) => (
                <div key={i} className={styles.breakdownRow}>
                  <div className={styles.breakdownAttrRow}>
                    {score.match ? (
                      <CheckCircle weight="fill" className={`${styles.breakdownCheck} ${styles.breakdownCheckMatch}`} />
                    ) : (
                      <X weight="bold" className={`${styles.breakdownCheck} ${styles.breakdownCheckFail}`} />
                    )}
                    <span className={styles.breakdownAttr}>{score.attribute}</span>
                  </div>
                  <div className={styles.breakdownEvidence}>{score.evidence}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className={styles.productActions}>
          <a
            href={candidate.link}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-primary btn-sm"
          >
            Buy <ArrowRight weight="bold" />
          </a>
          <button className="btn btn-secondary btn-sm" onClick={onCompare}>
            Compare Prices
          </button>
        </div>
      </div>
    </div>
  );
}
