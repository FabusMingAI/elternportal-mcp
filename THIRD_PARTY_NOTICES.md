# Third-party notices

## Adapted Home Assistant portal parsers

`src/elternportal_mcp/vendor/parsers.py` and `vendor/classes.py` contain code
adapted from `custom_components/eltern_portal_schulmanager/portal.py` and
`classes.py` in https://github.com/FabusMingAI/ha-schulmanager at commit
`fc1357caba5677358b70731650932b95140ad586`.

Copyright (c) 2026 FabusMingAI and contributors. Licensed under the MIT License,
whose complete text is included in this distribution as `LICENSE`.

Adaptations extract models and parsers from the Home Assistant integration;
this project implements its own transport, per-school synchronization, storage
and MCP interface. No Home Assistant runtime is required.

## pyelternportal

This project depends on `pyelternportal` 0.0.28 by michull and contributors,
https://github.com/michull/pyelternportal, distributed under the Unlicense.
It is a dependency, not vendored here. See its distribution for its complete
license. Thanks to its authors for making Eltern-Portal interoperability possible.

Other dependencies retain their respective licenses and are not relicensed by
this project. The separate `elternportal-mcp` package by Andrei Svirida was
evaluated for comparison; none of its implementation is included here.
