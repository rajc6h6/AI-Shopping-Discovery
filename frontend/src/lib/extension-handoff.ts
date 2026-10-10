/** Decode a chat passed from the Chrome extension without persisting it. */
export function decodeChatFromHash(hash: string): string | null {
  if (!hash.startsWith('#chat=')) return null;

  try {
    const encoded = hash.slice('#chat='.length);
    if (!/^[A-Za-z0-9_-]*$/.test(encoded)) return null;

    const base64 = encoded.replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
    const binary = atob(padded);
    const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
    return new TextDecoder('utf-8', { fatal: true }).decode(bytes);
  } catch {
    return null;
  }
}
