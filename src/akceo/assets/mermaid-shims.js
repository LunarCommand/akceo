// Loaded into V8 before mermaid.min.js so that mermaid.parse() can run without a browser. Only the
// build-time diagram check uses this file; the built page never includes it.

// DOMPurify, finding no DOM, returns a bare object and sets isSupported = false on it. Catch that
// assignment and give the object no-op methods: checking syntax never sanitizes anything.
Object.defineProperty(Function.prototype, "isSupported", {
  configurable: true,
  set(value) {
    Object.defineProperty(this, "isSupported", { value, writable: true, configurable: true });
    if (!value) {
      const noop = () => {};
      Object.assign(this, {
        addHook: noop, removeHook: noop, removeHooks: noop, removeAllHooks: noop,
        setConfig: noop, clearConfig: noop, isValidAttribute: () => true, sanitize: (dirty) => dirty,
      });
    }
  },
});

// The parsers of the newer diagram types (pie, gitGraph, architecture and others) encode text.
globalThis.TextEncoder = class {
  get encoding() { return "utf-8"; }
  encode(text = "") {
    const out = [];
    for (const ch of text) {
      const c = ch.codePointAt(0);
      if (c < 0x80) out.push(c);
      else if (c < 0x800) out.push(0xc0 | (c >> 6), 0x80 | (c & 63));
      else if (c < 0x10000) out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
      else out.push(0xf0 | (c >> 18), 0x80 | ((c >> 12) & 63), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
    }
    return new Uint8Array(out);
  }
};

// Only plain parse results pass through here, so a recursive copy is enough.
globalThis.structuredClone = function clone(value) {
  if (value === null || typeof value !== "object") return value;
  if (Array.isArray(value)) return value.map(clone);
  if (value instanceof Map) return new Map([...value].map(([k, v]) => [clone(k), clone(v)]));
  if (value instanceof Set) return new Set([...value].map(clone));
  if (value instanceof Date) return new Date(value);
  return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, clone(v)]));
};

// Resolves to null when the diagram parses, or to Mermaid's error message when it doesn't.
globalThis.akceoCheck = async (source) => {
  try {
    await mermaid.parse(source);
    return null;
  } catch (e) {
    return String((e && e.message) || e);
  }
};
