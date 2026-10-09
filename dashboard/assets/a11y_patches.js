/* Accessibility patches for Dash 4.x component markup.
 *
 * Dash loads every .js file in assets/ automatically. Found in the accessibility pass (axe-core 4, WCAG 2.2 AA):
 *  1. dcc.RadioItems renders role="listbox" with <label role="option"> wrapping a real radio button, so screen
 *     readers hear a list box with nested controls and no name. Fix: the group becomes role="radiogroup", named
 *     by its <legend> or by an aria-label on the wrapper; the labels lose their option role, leaving the native
 *     radio buttons (which already have the right name, state and arrow-key behaviour).
 *  2. dcc.Dropdown's button is named only by its current value. Fix: prepend the visible <label for=…>.
 *  3. dcc.Slider's thumb and its number box have no accessible name. Fix: name both from the visible label and
 *     add aria-valuetext with the unit ("16.75 micrograms per cubic metre").
 *  4. dcc.Dropdown (Dash 4.4) puts focus on the selected option when it opens, so typing a suburb name does
 *     nothing until the user clicks into the small "Search" box. Fix: a printable key pressed anywhere in the
 *     open list is sent to the search box (type-to-search, as the placeholder promises).
 * Dash re-renders these components, so a MutationObserver re-applies the fixes (idempotent; no loops).
 */
(function () {
  function labelFor(id) {
    var lab = document.querySelector('label[for="' + id + '"]');
    if (lab && !lab.id) { lab.id = id + "-label"; }
    return lab;
  }

  function fixRadioGroups() {
    document.querySelectorAll(".dash-radioitems[role='listbox']").forEach(function (g) {
      g.setAttribute("role", "radiogroup");
      var fs = g.closest("fieldset"), legend = fs && fs.querySelector("legend");
      var wrap = g.parentElement && g.parentElement.getAttribute("aria-label");
      if (legend) {
        if (!legend.id) { legend.id = g.id + "-legend"; }
        g.setAttribute("aria-labelledby", legend.id);
      } else if (wrap) {
        g.setAttribute("aria-label", wrap);
        g.parentElement.removeAttribute("role");          // avoid a radiogroup inside a radiogroup
        g.parentElement.removeAttribute("aria-label");
      }
    });
    document.querySelectorAll(".dash-radioitems label[role='option']").forEach(function (l) {
      l.removeAttribute("role");
      l.removeAttribute("aria-selected");
    });
  }

  function fixDropdowns() {
    document.querySelectorAll("button.dash-dropdown[id]").forEach(function (b) {
      var lab = labelFor(b.id);
      var cur = b.getAttribute("aria-labelledby") || "";
      if (lab && cur.split(" ").indexOf(lab.id) === -1) {
        b.setAttribute("aria-labelledby", (lab.id + " " + cur).trim());
      }
    });
  }

  function fixSliders() {
    document.querySelectorAll(".dash-slider-container[id]").forEach(function (c) {
      var lab = labelFor(c.id);
      if (!lab) { return; }
      c.querySelectorAll("[role='slider'], input[type='number']").forEach(function (el) {
        if (el.getAttribute("aria-labelledby") !== lab.id) { el.setAttribute("aria-labelledby", lab.id); }
      });
      c.querySelectorAll("[role='slider']").forEach(function (t) {
        var text = t.getAttribute("aria-valuenow") + " micrograms per cubic metre";
        if (t.getAttribute("aria-valuetext") !== text) { t.setAttribute("aria-valuetext", text); }
      });
    });
  }

  function run() { fixRadioGroups(); fixDropdowns(); fixSliders(); }

  document.addEventListener("keydown", function (e) {
    if (e.key.length !== 1 || e.ctrlKey || e.metaKey || e.altKey) { return; }
    var t = e.target;
    var box = t && t.closest && t.closest(".dash-dropdown-content");
    if (!box || t.classList.contains("dash-dropdown-search")) { return; }
    var search = box.querySelector(".dash-dropdown-search");
    if (search) { search.focus(); }          // the key itself then lands in the search box
  }, true);

  var queued = false;
  new MutationObserver(function () {
    if (queued) { return; }
    queued = true;
    window.requestAnimationFrame(function () { queued = false; run(); });
  }).observe(document.documentElement, {
    childList: true, subtree: true, attributes: true,
    attributeFilter: ["role", "aria-selected", "aria-labelledby", "aria-valuenow"]
  });
  document.addEventListener("DOMContentLoaded", run);
})();
