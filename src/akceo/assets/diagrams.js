// Draw each Mermaid diagram as inline SVG in place of its source. The build has already checked
// every diagram's syntax, so a failure here is one that only shows when drawing, such as a bad date.
(function() {
  var diagrams = Array.prototype.slice.call(document.querySelectorAll('.diagram'));
  var theme = JSON.parse(document.getElementById('mermaid-theme').textContent);
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
    // The page's Content-Security-Policy blocks every outside load, and the build rejects outside
    // links. Drop any link that still gets through, so a click can't leave the deck.
    svg.querySelectorAll('*').forEach(function(el) {
      Array.prototype.slice.call(el.attributes).forEach(function(attr) {
        if (/^(xlink:)?href$/i.test(attr.name) && !/^\s*#/.test(attr.value)) el.removeAttributeNode(attr);
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
  // Never rejects: any error, from Mermaid or from sizing, marks this diagram failed and leaves the
  // rest to draw.
  function draw(node, n) {
    return Promise.resolve().then(function() {
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
