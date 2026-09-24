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
    var box = svg.viewBox.baseVal;
    svg.setAttribute('width', Math.round(box.width));
    svg.setAttribute('height', Math.round(box.height));
    svg.style.maxWidth = '';
    node.classList.forEach(function(name){ svg.classList.add(name); });
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', node.getAttribute('aria-label'));
    return svg;
  }
  function draw(node, n) {
    var source = node.querySelector('.diagram-src').textContent;
    // An unframed diagram takes the theme's colors; one in a frame keeps Mermaid's defaults.
    // initialize starts again from Mermaid's defaults each time, so one diagram can't leak into the next.
    mermaid.initialize(Object.assign({ startOnLoad: false }, node.dataset.mermaid === 'theme' ? theme : {}));
    return mermaid.render('diagram-' + n, source).then(function(result) {
      node.replaceWith(sized(result.svg, node));
    }, function(e) {
      node.classList.add('failed');
      node.textContent = 'Mermaid could not draw this diagram: ' + ((e && e.message) || e);
    });
  }
  // The theme's fonts change the size of the text, so wait for them before Mermaid measures it.
  // One at a time, because initialize sets Mermaid's config for the whole page.
  diagrams.reduce(function(done, node, n) {
    return done.then(function() { return draw(node, n); });
  }, document.fonts.ready);
})();
