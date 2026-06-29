# Pre Icarus v5.27 Preset System Cleanup

Pre Icarus v5.27 resets the bundled settings preset list to a neutral `Default` preset and sanitizes old bundled preset names when existing installs are loaded.

Removed bundled legacy preset names:

- Fan Farming
- Maru Fan Farming
- Oguri
- Parent Farming
- xguri
- xguri parent

User-created presets are preserved unless their name exactly matches one of those normalized legacy names. If every preset in an install is removed by the sanitizer, Pre Icarus creates a neutral `Default` preset automatically.

The frontend now prefers the backend `active` preset when local browser storage does not point to a valid preset. Career runs and race saves also use the active backend preset when no preset name is supplied, rather than falling back to a hard-coded legacy preset.

The Smart Race Solver `Optimization Mode` remains a frontend macro. It adjusts scoring weights and is not a separate backend solver parameter.
