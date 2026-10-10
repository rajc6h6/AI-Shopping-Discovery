// Set this to the deployed Paste-to-Product URL before recording; localhost is for development.
const SITE_URL = 'http://localhost:3000';
const MAX_URL_LENGTH = 1_000_000;

const statusElement = document.getElementById('status');
const previewElement = document.getElementById('preview');
const searchButton = document.getElementById('search');
let capturedText = '';

function isChatGPTUrl(url) {
  try {
    const hostname = new URL(url).hostname;
    return hostname === 'chatgpt.com' || hostname === 'chat.openai.com';
  } catch {
    return false;
  }
}

function extractConversation() {
  const messages = Array.from(document.querySelectorAll('[data-message-author-role]'))
    .map((node) => {
      const text = node.innerText.trim();
      if (!text) return null;
      const label = node.dataset.messageAuthorRole === 'user' ? 'User' : 'Assistant';
      return `${label}: ${text}`;
    })
    .filter(Boolean);

  if (messages.length > 0) {
    return { text: messages.join('\n\n'), status: `${messages.length} messages captured` };
  }

  const selection = window.getSelection()?.toString().trim();
  if (selection) return { text: selection, status: 'Using selected text' };

  const pageText = document.querySelector('main')?.innerText.trim() || document.body.innerText.trim();
  return { text: pageText, status: 'Using page text' };
}

function preview(text) {
  return text.split(/\r?\n/).filter(Boolean).slice(0, 2).join('\n').slice(0, 180) || 'No text found.';
}

function encodeBase64Url(text) {
  const bytes = new TextEncoder().encode(text);
  let binary = '';
  for (let start = 0; start < bytes.length; start += 8192) {
    binary += String.fromCharCode(...bytes.subarray(start, start + 8192));
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

async function captureActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !isChatGPTUrl(tab.url)) {
    statusElement.textContent = 'Open a ChatGPT conversation first';
    previewElement.textContent = 'This extension only reads the active ChatGPT tab.';
    return;
  }

  try {
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractConversation,
    });
    capturedText = result?.text || '';
    statusElement.textContent = result?.status || 'No conversation found';
    previewElement.textContent = preview(capturedText);
    searchButton.disabled = !capturedText;
  } catch {
    statusElement.textContent = 'Could not read this ChatGPT page';
    previewElement.textContent = 'Refresh the page and try again.';
  }
}

searchButton.addEventListener('click', async () => {
  if (!capturedText) return;

  try {
    await navigator.clipboard.writeText(capturedText);
  } catch {
    // Clipboard access is a backup only; the URL hand-off still works.
  }

  const encoded = encodeBase64Url(capturedText);
  const url = `${SITE_URL}#chat=${encoded}`;
  if (url.length > MAX_URL_LENGTH) {
    statusElement.textContent = 'Chat is too long for one-click. It was copied to your clipboard, paste it into the site.';
    await chrome.tabs.create({ url: SITE_URL });
    return;
  }

  await chrome.tabs.create({ url });
});

void captureActiveTab();
