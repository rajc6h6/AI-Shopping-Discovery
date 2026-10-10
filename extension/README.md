# Paste-to-Product Chrome Extension

Copies the currently open ChatGPT conversation to Paste-to-Product with a single click.

## How it works

When you click the extension button on a ChatGPT page, it extracts the conversation text and sends it directly to the Paste-to-Product site. 

**Note:** The extension only fills the text box on the site. It **does not** automatically start the search. You must manually review the pasted text and click "Search" on the site to begin.

## Installation (Unpacked)

1. Open Chrome and navigate to `chrome://extensions`.
2. Toggle **Developer mode** on (top right corner).
3. Click **Load unpacked** and select this `extension/` folder from your cloned repository.

## Configuration

In `popup.js`, set the `SITE_URL` constant to the deployed Paste-to-Product site before recording. It defaults to `http://localhost:3000` for local development.

## Privacy and Data Handling

- **No background running:** The extension runs strictly on-demand when you click its icon.
- **Local hand-off only:** It reads only the currently active ChatGPT tab. It makes zero network requests of its own and stores no data.
- **URL Hash:** The conversation is passed entirely within the browser via the destination URL fragment (`#chat=...`). Nothing leaves your browser during the hand-off. A plain-text clipboard copy is made only as a fallback for chats that exceed URL length limits.

## Known Limits

- **Structure Dependency:** The extension relies on the current CSS class structure of the ChatGPT website to identify and extract the chat. If OpenAI redesigns their interface, the extraction logic may break and require an update.
- **Single Page Context:** It only reads the conversation currently rendered in the active tab.
