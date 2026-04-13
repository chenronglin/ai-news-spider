import { JSDOM } from 'jsdom';
import { getIframeEventElementTarget } from '@/utils/iframe';

describe('iframe utils', () => {
  it('accepts elements from the iframe document realm', () => {
    const iframeDom = new JSDOM('<!doctype html><html><body><div class="item">news</div></body></html>');
    const doc = iframeDom.window.document;
    const target = doc.querySelector('.item');

    expect(target).toBeTruthy();
    expect(target instanceof Node).toBe(false);
    expect(getIframeEventElementTarget(target, doc)).toBe(target);
  });

  it('maps text nodes to their parent element within the iframe document', () => {
    const iframeDom = new JSDOM('<!doctype html><html><body><p>headline</p></body></html>');
    const doc = iframeDom.window.document;
    const textNode = doc.querySelector('p')?.firstChild ?? null;

    expect(getIframeEventElementTarget(textNode, doc)?.tagName).toBe('P');
  });
});
