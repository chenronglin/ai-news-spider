const TOKEN_STORAGE_KEY = 'ai-news-spider.api-token';

export function readApiTokenFromStorage(): string {
  if (typeof window === 'undefined') {
    return '';
  }
  return window.localStorage.getItem(TOKEN_STORAGE_KEY) ?? '';
}

export function writeApiTokenToStorage(token: string): void {
  if (typeof window === 'undefined') {
    return;
  }

  const normalized = token.trim();
  if (normalized) {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, normalized);
  } else {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}
