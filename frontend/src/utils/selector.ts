export interface SelectorOutput {
  cssSelector: string;
  xpathSelector: string;
  metaText: string;
}

function escapeCssIdentifier(value: string): string {
  if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') {
    return CSS.escape(value);
  }

  return value.replace(/[^a-zA-Z0-9_-]/g, (char) => `\\${char}`);
}

export function getXPath(el: Element | null): string {
  if (!el || el.nodeType !== Node.ELEMENT_NODE) {
    return '';
  }

  const element = el as HTMLElement;
  if (element.id) {
    return `//*[@id="${element.id.replace(/"/g, '\\"')}"]`;
  }

  const segments: string[] = [];
  let node: Element | null = element;
  while (node && node.nodeType === Node.ELEMENT_NODE) {
    const tag = node.tagName.toLowerCase();
    let index = 1;
    let sibling = node.previousElementSibling;
    while (sibling) {
      if (sibling.tagName === node.tagName) {
        index += 1;
      }
      sibling = sibling.previousElementSibling;
    }
    segments.unshift(`${tag}[${index}]`);
    node = node.parentElement;
  }

  return `/${segments.join('/')}`;
}

export function isUniqueSelector(selector: string, doc: Document): boolean {
  try {
    return doc.querySelectorAll(selector).length === 1;
  } catch {
    return false;
  }
}

export function getCssSelector(el: Element | null): string {
  if (!el || el.nodeType !== Node.ELEMENT_NODE) {
    return '';
  }

  const doc = el.ownerDocument;
  if (!doc) {
    return '';
  }

  const htmlEl = el as HTMLElement;
  if (htmlEl.id) {
    const selector = `#${escapeCssIdentifier(htmlEl.id)}`;
    if (isUniqueSelector(selector, doc)) {
      return selector;
    }
  }

  const path: string[] = [];
  let node: Element | null = el;

  while (node && node.nodeType === Node.ELEMENT_NODE && node.tagName.toLowerCase() !== 'html') {
    let segment = node.tagName.toLowerCase();
    const elementNode = node as HTMLElement;

    if (elementNode.id) {
      segment += `#${escapeCssIdentifier(elementNode.id)}`;
      path.unshift(segment);
      const selector = path.join(' > ');
      if (isUniqueSelector(selector, doc)) {
        return selector;
      }
      node = node.parentElement;
      continue;
    }

    const classes = Array.from(node.classList).filter(Boolean).slice(0, 3);
    if (classes.length) {
      const classSelector = classes
        .map((className) => `.${escapeCssIdentifier(className)}`)
        .join('');
      const candidate = `${segment}${classSelector}`;
      path.unshift(candidate);
      const selector = path.join(' > ');
      if (isUniqueSelector(selector, doc)) {
        return selector;
      }
      path.shift();
    }

    let index = 1;
    let sibling = node.previousElementSibling;
    while (sibling) {
      if (sibling.tagName === node.tagName) {
        index += 1;
      }
      sibling = sibling.previousElementSibling;
    }

    segment += `:nth-of-type(${index})`;
    path.unshift(segment);
    const selector = path.join(' > ');
    if (isUniqueSelector(selector, doc)) {
      return selector;
    }

    node = node.parentElement;
  }

  return path.join(' > ');
}

export function buildElementMeta(el: Element): string {
  const rect = el.getBoundingClientRect();
  const text = (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 180);
  const attrs = Array.from(el.attributes)
    .slice(0, 10)
    .map((attr) => `${attr.name}="${attr.value}"`)
    .join('\n');

  return [
    `标签: ${el.tagName.toLowerCase()}`,
    `类名: ${Array.from(el.classList).join(' ') || '(无)'}`,
    `尺寸: ${Math.round(rect.width)} × ${Math.round(rect.height)}`,
    `文本: ${text || '(无文本)'}`,
    `属性:\n${attrs || '(无属性)'}`,
  ].join('\n\n');
}

export function buildSelectorOutput(el: Element): SelectorOutput {
  return {
    cssSelector: getCssSelector(el),
    xpathSelector: getXPath(el),
    metaText: buildElementMeta(el),
  };
}
