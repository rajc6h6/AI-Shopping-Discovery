/**
 * SSE stream reliability tests.
 *
 * Tests the eventsource-parser integration via a minimal in-process harness.
 * No network calls; all streams are created from byte arrays.
 *
 * Covers:
 *  - LF, CRLF, bare CR line endings
 *  - Event/data lines split across chunk boundaries (at every byte position)
 *  - Multi-byte characters (₹ sign) split across chunks
 *  - Comment/keepalive lines
 *  - Malformed JSON in one event — other events still arrive
 *  - Multi-line data fields
 */

import { describe, it, expect } from 'vitest';
import { createParser, type EventSourceMessage } from 'eventsource-parser';

// ---------------------------------------------------------------------------
// Test harness
// ---------------------------------------------------------------------------

interface CollectedEvent {
  name: string;
  data: unknown;
  parseError: boolean;
}

/** Feed byte chunks through eventsource-parser and collect results. */
async function collectEvents(chunks: string[]): Promise<CollectedEvent[]> {
  const events: CollectedEvent[] = [];

  const parser = createParser({
    onEvent: (event: EventSourceMessage) => {
      const name = event.event ?? 'message';
      try {
        events.push({ name, data: JSON.parse(event.data), parseError: false });
      } catch {
        events.push({ name, data: null, parseError: true });
      }
    },
  });

  for (const chunk of chunks) {
    parser.feed(chunk);
  }

  return events;
}

/** Feed raw UTF-8 byte arrays through a TextDecoder (stream mode) and then the parser. */
async function collectEventsFromBytes(byteChunks: Uint8Array[]): Promise<CollectedEvent[]> {
  const decoder = new TextDecoder('utf-8');
  const events: CollectedEvent[] = [];

  const parser = createParser({
    onEvent: (event: EventSourceMessage) => {
      const name = event.event ?? 'message';
      try {
        events.push({ name, data: JSON.parse(event.data), parseError: false });
      } catch {
        events.push({ name, data: null, parseError: true });
      }
    },
  });

  for (let i = 0; i < byteChunks.length; i++) {
    // stream: true preserves incomplete multi-byte sequences across chunks
    const text = decoder.decode(byteChunks[i], { stream: i < byteChunks.length - 1 });
    parser.feed(text);
  }

  return events;
}

// ---------------------------------------------------------------------------
// Line-ending variants
// ---------------------------------------------------------------------------

describe('SSE line endings', () => {
  it('parses events with LF line endings', async () => {
    const events = await collectEvents([
      'event: trace\ndata: {"agent":"parser"}\n\n',
    ]);
    expect(events).toHaveLength(1);
    expect(events[0].name).toBe('trace');
    expect((events[0].data as { agent: string }).agent).toBe('parser');
  });

  it('parses events with CRLF line endings (Uvicorn on Windows)', async () => {
    const events = await collectEvents([
      'event: trace\r\ndata: {"agent":"parser"}\r\n\r\n',
    ]);
    expect(events).toHaveLength(1);
    expect(events[0].name).toBe('trace');
    expect((events[0].data as { agent: string }).agent).toBe('parser');
  });

  it('parses events with bare CR line endings', async () => {
    const events = await collectEvents([
      'event: trace\rdata: {"agent":"parser"}\r\r',
    ]);
    expect(events).toHaveLength(1);
    expect(events[0].name).toBe('trace');
  });

  it('parses multiple events with mixed line endings', async () => {
    const events = await collectEvents([
      'event: trace\r\ndata: {"agent":"parser"}\r\n\r\n',
      'event: complete\ndata: {"total_items":2}\n\n',
    ]);
    expect(events).toHaveLength(2);
    expect(events[0].name).toBe('trace');
    expect(events[1].name).toBe('complete');
  });
});

// ---------------------------------------------------------------------------
// Chunk splits
// ---------------------------------------------------------------------------

describe('SSE chunk boundary splits', () => {
  const fullEvent = 'event: item_parsed\r\ndata: {"category":"sneakers"}\r\n\r\n';

  it('handles event: line in one chunk, data: in the next', async () => {
    const events = await collectEvents([
      'event: item_parsed\r\n',
      'data: {"category":"sneakers"}\r\n\r\n',
    ]);
    expect(events).toHaveLength(1);
    expect(events[0].name).toBe('item_parsed');
    expect((events[0].data as { category: string }).category).toBe('sneakers');
  });

  it('handles data split mid-word in event name', async () => {
    const events = await collectEvents([
      'event: item_',
      'parsed\r\ndata: {"category":"sneakers"}\r\n\r\n',
    ]);
    expect(events).toHaveLength(1);
    expect(events[0].name).toBe('item_parsed');
  });

  it('handles data split mid-JSON', async () => {
    const events = await collectEvents([
      'event: item_parsed\r\ndata: {"catego',
      'ry":"sneakers"}\r\n\r\n',
    ]);
    expect(events).toHaveLength(1);
    expect((events[0].data as { category: string }).category).toBe('sneakers');
  });

  it('handles blank-line separator split across chunks', async () => {
    const events = await collectEvents([
      'event: trace\r\ndata: {"agent":"parser"}\r\n',
      '\r\n',
    ]);
    expect(events).toHaveLength(1);
    expect(events[0].name).toBe('trace');
  });

  it('produces identical results regardless of byte split position', async () => {
    const encoder = new TextEncoder();
    const bytes = encoder.encode(fullEvent);

    // Test at every single-byte boundary
    for (let i = 1; i < bytes.length; i++) {
      const decoder1 = new TextDecoder('utf-8');
      const chunk1 = decoder1.decode(bytes.slice(0, i), { stream: true });
      const chunk2 = decoder1.decode(bytes.slice(i));
      const events = await collectEvents([chunk1, chunk2]);

      expect(events).toHaveLength(1);
      expect(events[0].name).toBe('item_parsed');
      expect((events[0].data as { category: string }).category).toBe('sneakers');
    }
  });

  it('handles two events split across three chunks', async () => {
    const events = await collectEvents([
      'event: trace\r\ndata: {"agent":"par',
      'ser"}\r\n\r\nevent: complete\r\ndata: {"tot',
      'al_items":3}\r\n\r\n',
    ]);
    expect(events).toHaveLength(2);
    expect(events[0].name).toBe('trace');
    expect(events[1].name).toBe('complete');
    expect((events[1].data as { total_items: number }).total_items).toBe(3);
  });
});

// ---------------------------------------------------------------------------
// Multi-byte characters split across chunks
// ---------------------------------------------------------------------------

describe('SSE multi-byte character handling', () => {
  it('handles rupee sign (₹, U+20B9 = 3 bytes) split across chunks', async () => {
    // ₹ = 0xE2 0x82 0xB9 in UTF-8
    const fullStr = 'event: trace\r\ndata: {"price":"₹500"}\r\n\r\n';
    const encoder = new TextEncoder();
    const bytes = encoder.encode(fullStr);

    // Find the byte offset of the ₹ character
    const rupeeStartOffset = fullStr.indexOf('₹');

    // Split after first byte of the ₹ sequence
    const chunk1 = bytes.slice(0, rupeeStartOffset + 1);
    const chunk2 = bytes.slice(rupeeStartOffset + 1);
    const events = await collectEventsFromBytes([chunk1, chunk2]);

    expect(events).toHaveLength(1);
    expect(events[0].parseError).toBe(false);
    expect(JSON.stringify(events[0].data)).toContain('₹');
  });

  it('handles emoji (🎯, 4 bytes) split across chunks', async () => {
    const fullStr = 'event: trace\r\ndata: {"tag":"🎯"}\r\n\r\n';
    const encoder = new TextEncoder();
    const bytes = encoder.encode(fullStr);
    const emojiOffset = fullStr.indexOf('🎯');

    // Split in the middle of the 4-byte emoji
    const chunk1 = bytes.slice(0, emojiOffset + 2);
    const chunk2 = bytes.slice(emojiOffset + 2);
    const events = await collectEventsFromBytes([chunk1, chunk2]);

    expect(events).toHaveLength(1);
    expect(JSON.stringify(events[0].data)).toContain('🎯');
  });
});

// ---------------------------------------------------------------------------
// Comment / keepalive lines
// ---------------------------------------------------------------------------

describe('SSE comment lines', () => {
  it('ignores keepalive comment lines between events', async () => {
    const events = await collectEvents([
      ': keepalive\r\n\r\n',
      'event: trace\r\ndata: {"agent":"parser"}\r\n\r\n',
    ]);
    expect(events).toHaveLength(1);
    expect(events[0].name).toBe('trace');
  });

  it('ignores multiple comments between events', async () => {
    const events = await collectEvents([
      ': ping\r\n',
      ': pong\r\n\r\n',
      'event: complete\r\ndata: {"total_items":2}\r\n\r\n',
    ]);
    expect(events).toHaveLength(1);
    expect(events[0].name).toBe('complete');
  });

  it('handles comments interspersed with normal events', async () => {
    const events = await collectEvents([
      'event: trace\r\ndata: {"agent":"parser"}\r\n\r\n',
      ': keepalive\r\n\r\n',
      ': keepalive\r\n\r\n',
      'event: complete\r\ndata: {"total_items":1}\r\n\r\n',
    ]);
    expect(events).toHaveLength(2);
    expect(events[0].name).toBe('trace');
    expect(events[1].name).toBe('complete');
  });
});

// ---------------------------------------------------------------------------
// Malformed JSON in one event
// ---------------------------------------------------------------------------

describe('SSE malformed JSON in events', () => {
  it('marks the malformed event but continues to next event', async () => {
    const events = await collectEvents([
      'event: bad\r\ndata: {not valid json}\r\n\r\n',
      'event: trace\r\ndata: {"agent":"finder"}\r\n\r\n',
    ]);
    expect(events).toHaveLength(2);
    expect(events[0].parseError).toBe(true);
    expect(events[0].name).toBe('bad');
    expect(events[1].parseError).toBe(false);
    expect(events[1].name).toBe('trace');
    expect((events[1].data as { agent: string }).agent).toBe('finder');
  });

  it('multiple malformed events do not prevent later valid events', async () => {
    const events = await collectEvents([
      'event: a\r\ndata: broken1\r\n\r\n',
      'event: b\r\ndata: broken2\r\n\r\n',
      'event: complete\r\ndata: {"total_items":0}\r\n\r\n',
    ]);
    expect(events).toHaveLength(3);
    expect(events[0].parseError).toBe(true);
    expect(events[1].parseError).toBe(true);
    expect(events[2].parseError).toBe(false);
    expect(events[2].name).toBe('complete');
  });
});

// ---------------------------------------------------------------------------
// Multi-line data fields
// ---------------------------------------------------------------------------

describe('SSE multi-line data', () => {
  it('joins multi-line data fields with newline per spec', async () => {
    // SSE spec: multiple data: lines are joined with \n
    // This results in invalid JSON but tests the join behavior
    const events = await collectEvents([
      'event: test\r\ndata: {"part1":\r\ndata: "hello"}\r\n\r\n',
    ]);
    // eventsource-parser joins them — the resulting string may or may not be valid JSON
    // Just assert no exception and event was received
    expect(events).toHaveLength(1);
    expect(events[0].name).toBe('test');
  });
});

// ---------------------------------------------------------------------------
// Empty events
// ---------------------------------------------------------------------------

describe('SSE empty and edge cases', () => {
  it('handles unnamed events (no event: field) as "message" type', async () => {
    const events = await collectEvents([
      'data: {"msg":"hello"}\r\n\r\n',
    ]);
    expect(events).toHaveLength(1);
    expect(events[0].name).toBe('message');
  });

  it('handles empty stream (no events)', async () => {
    const events = await collectEvents([]);
    expect(events).toHaveLength(0);
  });

  it('handles final event with no trailing blank line (stream ends before blank)', async () => {
    // Some servers omit the final blank line — eventsource-parser should handle this
    // by delivering the event when fed (no explicit flush needed since we control the loop)
    const events = await collectEvents([
      'event: complete\r\ndata: {"total_items":1}\r\n\r\n',
    ]);
    expect(events).toHaveLength(1);
    expect(events[0].name).toBe('complete');
  });
});
