import { buildSelectorOutput, getCssSelector, getXPath } from '@/utils/selector';

describe('selector utils', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <main>
        <section class="news-list">
          <article class="item-card">
            <a class="item-link" href="/a1"><h2>第一条新闻</h2></a>
          </article>
          <article class="item-card">
            <a class="item-link" href="/a2"><h2>第二条新闻</h2></a>
          </article>
        </section>
      </main>
    `;
  });

  it('builds a unique css selector for the selected element', () => {
    const target = document.querySelector('.news-list') as HTMLElement;
    const selector = getCssSelector(target);
    expect(selector).toBeTruthy();
    expect(document.querySelectorAll(selector)).toHaveLength(1);
  });

  it('builds xpath and meta text for selected element', () => {
    const target = document.querySelector('.item-link') as HTMLElement;
    const output = buildSelectorOutput(target);

    expect(output.xpathSelector).toContain('/html');
    expect(output.metaText).toContain('标签: a');
    expect(output.cssSelector).toBe(getCssSelector(target));
    expect(getXPath(target)).toBe(output.xpathSelector);
  });
});
