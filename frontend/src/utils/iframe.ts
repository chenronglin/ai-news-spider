export function getIframeEventElementTarget(
  target: EventTarget | null,
  doc: Document,
): Element | null {
  const nodeCtor = doc.defaultView?.Node ?? globalThis.Node;

  if (!target || !nodeCtor || !(target instanceof nodeCtor)) {
    return null;
  }

  if (target.nodeType === nodeCtor.ELEMENT_NODE) {
    const element = target as Element;
    return element.ownerDocument === doc ? element : null;
  }

  if (target.nodeType === nodeCtor.TEXT_NODE) {
    const parent = (target as Text).parentElement;
    return parent?.ownerDocument === doc ? parent : null;
  }

  return null;
}
