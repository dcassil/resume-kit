"""Resume Kit Facade — the single in-process capability boundary for Phase 5.

Every Phase 5 transport (CLI, MCP, API, bridge) calls the capabilities in this
package instead of touching engine functions directly, so all surfaces stay in
parity and every result flows through the ``resume_kit_core`` interface
substrate.

The public export surface is defined in a later task (RIT-T-0048); this module
intentionally stays minimal.
"""

__version__ = "0.0.0"
