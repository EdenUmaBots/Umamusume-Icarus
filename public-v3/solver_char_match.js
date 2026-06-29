/* Pure trainee -> roster resolver for the Smart Race Solver "Character Preset".
   Shared by modals.js (browser) and tests/test_solver_char_sync_*.py (node).
   No DOM / no globals -- safe to require() in node.

   WHY this exists: /api/character-profile/active nests the active trainee's
   card_id under `resolved_from` (NOT top-level). The solver modal used to read
   top-level `a.card_id`, so the sync never fired and the picker silently fell
   back to the alphabetically-first roster entry ("Admire Vega"). This resolves
   an /active payload to a roster character id with a robust cascade:
     1. exact card_id            (player owns the roster's base card)
     2. same chara_id (id//100)  (player owns a different OUTFIT of the same uma)
     3. display name             (suffix like " (Christmas)" stripped)
   Returns null when nothing matches, so the caller can keep its own fallback. */
(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.IcarusSolverMatch = api;
})(typeof self !== 'undefined' ? self : (typeof window !== 'undefined' ? window : this), function () {
  'use strict';

  function resolveActiveToRoster(active, chars) {
    if (!active || typeof active !== 'object' || !Array.isArray(chars) || !chars.length) return null;
    var rf = active.resolved_from || {};
    // card_id lives under resolved_from on the real endpoint; tolerate a few
    // legacy/alternate shapes so the resolver is robust to future tweaks.
    var cid = +(rf.card_id || active.card_id || active.id ||
      (active.trainee && (active.trainee.card_id || active.trainee.id)) || 0);
    var charaId = +(rf.chara_id || active.chara_id ||
      (active.trainee && active.trainee.chara_id) || 0);
    var rawName = String(rf.selected_name || active.selected_name ||
      (active.trainee && (active.trainee.name || active.trainee.display_name)) || '').trim();

    // 1. exact card_id
    if (cid) {
      for (var i = 0; i < chars.length; i++) {
        if (+chars[i].id === cid) return +chars[i].id;
      }
      // 2. same character, different owned outfit (chara_id = card_id // 100)
      var chara = Math.floor(cid / 100);
      for (var j = 0; j < chars.length; j++) {
        if (Math.floor(+chars[j].id / 100) === chara) return +chars[j].id;
      }
    }

    // 2b. chara_id supplied directly (card_id missing)
    if (charaId) {
      for (var k = 0; k < chars.length; k++) {
        if (Math.floor(+chars[k].id / 100) === charaId) return +chars[k].id;
      }
    }

    // 3. by display name -- strip a trailing version suffix "Name (Version)"
    if (rawName) {
      var base = rawName.replace(/\s*\(.*\)\s*$/, '').toLowerCase();
      var lower = rawName.toLowerCase();
      for (var m = 0; m < chars.length; m++) {
        var n = String(chars[m].name || '').toLowerCase();
        if (n === base || n === lower) return +chars[m].id;
      }
    }

    return null;
  }

  return { resolveActiveToRoster: resolveActiveToRoster };
});
