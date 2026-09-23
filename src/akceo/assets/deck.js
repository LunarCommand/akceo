var slides = Array.prototype.slice.call(document.querySelectorAll('.slide'));
var i = 0;
var bar = document.getElementById('bar');
var count = document.getElementById('count');
function render() {
  slides.forEach(function(s, n){ s.classList.toggle('active', n === i); });
  bar.style.width = (slides.length > 1 ? i / (slides.length - 1) * 100 : 100) + '%';
  count.textContent = (i + 1) + ' / ' + slides.length;
  // replaceState keeps slide steps out of the browser history and doesn't fire hashchange.
  history.replaceState(null, '', '#' + (i + 1));
}
function go(n){ i = Math.max(0, Math.min(slides.length - 1, n)); render(); }
// The hash holds the 1-based slide number, so a link or a reload opens that slide.
function fromHash(){
  var m = location.hash.match(/^#(\d+)$/);
  return m ? parseInt(m[1], 10) - 1 : 0;
}
window.addEventListener('hashchange', function(){ go(fromHash()); });
document.addEventListener('keydown', function(e){
  if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') { e.preventDefault(); go(i + 1); }
  else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); go(i - 1); }
  else if (e.key === 'Home') { go(0); }
  else if (e.key === 'End') { go(slides.length - 1); }
  else if (e.key === 'f' || e.key === 'F') {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen();
    else document.exitFullscreen();
  }
});
document.addEventListener('click', function(e){
  if (String(window.getSelection())) return;
  if (e.clientX > window.innerWidth * 0.5) go(i + 1); else go(i - 1);
});
go(fromHash());
