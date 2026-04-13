export function injectBase(html: string, baseUrl: string): string {
  const baseTag = `<base href="${baseUrl.replace(/"/g, '&quot;')}">`;

  if (/<head[^>]*>/i.test(html)) {
    return html.replace(/<head([^>]*)>/i, `<head$1>${baseTag}`);
  }

  if (/<html[^>]*>/i.test(html)) {
    return html.replace(/<html([^>]*)>/i, `<html$1><head>${baseTag}</head>`);
  }

  return `<!doctype html><html><head>${baseTag}</head><body>${html}</body></html>`;
}

export function stripActiveContent(html: string): string {
  let output = html;
  output = output.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
  output = output.replace(/\son[a-z]+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '');
  output = output.replace(/<meta[^>]+http-equiv\s*=\s*["']?refresh["']?[^>]*>/gi, '');
  return output;
}

export function buildPreviewDocument(html: string, pageUrl: string): string {
  return stripActiveContent(injectBase(html, pageUrl));
}
