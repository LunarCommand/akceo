// Draw each Mermaid diagram as inline SVG in place of its source. The build has already checked
// every diagram's syntax, so a failure here is one that only shows when drawing, such as a bad date.
(function() {
  var diagrams = Array.prototype.slice.call(document.querySelectorAll('.diagram'));
  var theme = JSON.parse(document.getElementById('mermaid-theme').textContent);
  // Mermaid sits in the page deflated and base64-encoded, which keeps the file under half the size.
  // Unpack it and run it as an inline script, which the page's Content-Security-Policy allows. A
  // browser without DecompressionStream fails here, and each diagram shows the message.
  function unpack() {
    var text = atob(document.getElementById('mermaid-packed').textContent);
    var bytes = new Uint8Array(text.length);
    for (var i = 0; i < text.length; i++) bytes[i] = text.charCodeAt(i);
    var stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('deflate'));
    return new Response(stream).text().then(function(code) {
      var script = document.createElement('script');
      script.textContent = code;
      document.head.appendChild(script);
    });
  }
  var loaded = Promise.resolve().then(unpack);
  // Whether a drawn diagram keeps this attribute. The page's Content-Security-Policy blocks every
  // outside load, and the build rejects outside links, so this only catches a link that still gets
  // through. A link stays when it can't leave the deck: a # anchor, or a data: URI on an <image>,
  // which the build allows and the policy loads. tests/test_mermaid.py runs this function in V8.
  function keepsLink(tag, name, value) {
    if (!/^(xlink:)?href$/i.test(name) || /^\s*#/.test(value)) return true;
    return tag.toLowerCase() === 'image' && /^\s*data:/i.test(value);
  }
  // Mermaid sizes its SVG as width="100%" with an inline max-width. Give it a pixel size from its
  // viewBox instead, so it scales to fit the frame the way an <img> does, under the same CSS rules.
  function sized(markup, node) {
    var holder = document.createElement('div');
    holder.innerHTML = markup;
    var svg = holder.querySelector('svg');
    if (!svg) throw new Error('Mermaid returned no SVG');
    var box = svg.viewBox && svg.viewBox.baseVal;
    if (box && box.width && box.height) {
      svg.setAttribute('width', Math.round(box.width));
      svg.setAttribute('height', Math.round(box.height));
      svg.style.maxWidth = '';
    }
    svg.querySelectorAll('*').forEach(function(el) {
      Array.prototype.slice.call(el.attributes).forEach(function(attr) {
        if (!keepsLink(el.localName, attr.name, attr.value)) el.removeAttributeNode(attr);
      });
    });
    node.classList.forEach(function(name){ svg.classList.add(name); });
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', node.getAttribute('aria-label'));
    return svg;
  }
  function failed(node, e) {
    // The image role and its label would hide this text from screen readers.
    node.removeAttribute('role');
    node.removeAttribute('aria-label');
    node.classList.add('failed');
    node.textContent = 'Mermaid could not draw this diagram: ' + ((e && e.message) || e);
  }
  // Never rejects: any error, from unpacking, from Mermaid or from sizing, marks this diagram failed
  // and leaves the rest to draw.
  function draw(node, n) {
    return loaded.then(function() {
      var source = node.querySelector('.diagram-src').textContent;
      // An unframed diagram takes the theme's colors; one in a frame keeps Mermaid's defaults.
      // initialize starts again from Mermaid's defaults each time, so one diagram can't leak into
      // the next. suppressErrorRendering stops Mermaid leaving its own error graphic in the page.
      var colors = node.dataset.mermaid === 'theme' ? theme : {};
      mermaid.initialize(Object.assign({ startOnLoad: false, suppressErrorRendering: true }, colors));
      return mermaid.render('diagram-' + n, source);
    }).then(function(result) {
      node.replaceWith(sized(result.svg, node));
    }).catch(function(e) {
      failed(node, e);
    });
  }
  // The theme's fonts change the size of the text, so wait for them before Mermaid measures it.
  // One at a time, because initialize sets Mermaid's config for the whole page.
  diagrams.reduce(function(done, node, n) {
    return done.then(function() { return draw(node, n); });
  }, document.fonts.ready);
})();
