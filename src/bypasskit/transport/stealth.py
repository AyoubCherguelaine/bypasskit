INIT_JS = r"""
Object.defineProperty(Navigator.prototype, 'webdriver', { get: () => undefined });
Object.defineProperty(Navigator.prototype, 'plugins', {
  get: () => {
    const specs = [
      ['PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'],
      ['Chrome PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'],
      ['Chromium PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'],
      ['Microsoft Edge PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'],
      ['WebKit built-in PDF', 'internal-pdf-viewer', 'Portable Document Format'],
    ];
    const plugins = specs.map(([name, filename, description]) => {
      const p = Object.create(Plugin.prototype);
      Object.defineProperties(p, {
        name: { value: name, enumerable: true },
        filename: { value: filename, enumerable: true },
        description: { value: description, enumerable: true },
        length: { value: 0, enumerable: true },
      });
      return p;
    });
    plugins.item = (i) => plugins[i] || null;
    plugins.namedItem = (n) => plugins.find((p) => p.name === n) || null;
    return plugins;
  },
});
Object.defineProperty(Navigator.prototype, 'languages', { get: () => ['en-US', 'en'] });
window.chrome = window.chrome || { runtime: {} };
const _q = navigator.permissions.query.bind(navigator.permissions);
navigator.permissions.query = (p) =>
  p.name === 'notifications' ? Promise.resolve({ state: Notification.permission }) : _q(p);

const _patchWebGL = (proto) => {
  if (!proto || !proto.getParameter) return;
  const _get = proto.getParameter;
  proto.getParameter = function (p) {
    if (p === 37445) return 'Intel Inc.';
    if (p === 37446) return 'Intel Iris OpenGL Engine';
    return _get.call(this, p);
  };
};
_patchWebGL(typeof WebGLRenderingContext !== 'undefined' ? WebGLRenderingContext.prototype : null);
_patchWebGL(typeof WebGL2RenderingContext !== 'undefined' ? WebGL2RenderingContext.prototype : null);
"""
