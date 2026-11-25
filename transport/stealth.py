INIT_JS = r"""
Object.defineProperty(Navigator.prototype, 'webdriver', { get: () => undefined });
Object.defineProperty(Navigator.prototype, 'plugins', { get: () => [1,2,3,4,5] });
Object.defineProperty(Navigator.prototype, 'languages', { get: () => ['en-US','en'] });
window.chrome = window.chrome || { runtime: {} };
const _q = navigator.permissions.query.bind(navigator.permissions);
navigator.permissions.query = (p) =>
  p.name === 'notifications' ? Promise.resolve({ state: Notification.permission }) : _q(p);
const _get = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function (p) {
  if (p === 37445) return 'Intel Inc.';
  if (p === 37446) return 'Intel Iris OpenGL Engine';
  return _get.call(this, p);
};
"""

HUMAN_MOUSE_JS = r"""
async ([x, y]) => {
  const steps = 12 + Math.floor(Math.random() * 10);
  for (let i = 0; i < steps; i++) {
    const t = i / steps;
    const nx = x * t + (Math.random() - 0.5) * 6;
    const ny = y * t + (Math.random() - 0.5) * 6;
    document.elementFromPoint(nx, ny)?.dispatchEvent(
      new MouseEvent('mousemove', { clientX: nx, clientY: ny, bubbles: true }));
    await new Promise(r => setTimeout(r, 12 + Math.random() * 30));
  }
}
"""