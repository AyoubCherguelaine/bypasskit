INIT_JS = r"""
Object.defineProperty(Navigator.prototype, 'webdriver', { get: () => undefined });
(() => {
  const mimeSpecs = [
    ['application/pdf', 'Portable Document Format', 'pdf'],
    ['text/pdf', 'Portable Document Format', 'pdf'],
  ];
  const pluginSpecs = [
    ['PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'],
    ['Chrome PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'],
    ['Chromium PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'],
    ['Microsoft Edge PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'],
    ['WebKit built-in PDF', 'internal-pdf-viewer', 'Portable Document Format'],
  ];

  const mimes = mimeSpecs.map(([type, description, suffixes]) => {
    const m = Object.create(MimeType.prototype);
    Object.defineProperties(m, {
      type: { value: type, enumerable: true },
      description: { value: description, enumerable: true },
      suffixes: { value: suffixes, enumerable: true },
    });
    return m;
  });
  mimes.item = (i) => mimes[i] || null;
  mimes.namedItem = (n) => mimes.find((m) => m.type === n) || null;

  const plugins = pluginSpecs.map(([name, filename, description]) => {
    const p = Object.create(Plugin.prototype);
    Object.defineProperties(p, {
      name: { value: name, enumerable: true },
      filename: { value: filename, enumerable: true },
      description: { value: description, enumerable: true },
      length: { value: mimes.length, enumerable: true },
      0: { value: mimes[0], enumerable: true },
      1: { value: mimes[1], enumerable: true },
    });
    p.item = (i) => mimes[i] || null;
    p.namedItem = (n) => mimes.find((m) => m.type === n) || null;
    return p;
  });
  plugins.item = (i) => plugins[i] || null;
  plugins.namedItem = (n) => plugins.find((p) => p.name === n) || null;

  mimes.forEach((m) => {
    Object.defineProperty(m, 'enabledPlugin', { value: plugins[0], enumerable: true });
  });

  Object.defineProperty(Navigator.prototype, 'plugins', { get: () => plugins });
  Object.defineProperty(Navigator.prototype, 'mimeTypes', { get: () => mimes });
})();
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
