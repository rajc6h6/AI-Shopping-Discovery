import { describe, expect, it } from 'vitest';
import { decodeChatFromHash } from '../extension-handoff';

describe('decodeChatFromHash', () => {
  it('decodes base64url UTF-8 chat text', () => {
    const text = 'User: Find ₹500 sneakers 🎯\n\nAssistant: Try white leather.';
    const encoded = Buffer.from(text, 'utf8').toString('base64url');

    expect(decodeChatFromHash(`#chat=${encoded}`)).toBe(text);
  });

  it('returns null for hashes that are not extension hand-offs', () => {
    expect(decodeChatFromHash('#section')).toBeNull();
  });

  it('returns null for malformed base64url input', () => {
    expect(decodeChatFromHash('#chat=%%%')).toBeNull();
  });
});
