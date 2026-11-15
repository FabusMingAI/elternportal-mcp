# Roadmap

## Before calling the standalone server broadly validated

- Real-school smoke tests for every read area, with multiple children and schools.
- Compare the returned data with the visible portal, especially empty sections,
  poll details, calendar times and class-register/homework layouts.
- Check login expiry and unsupported MFA without retaining personal fixtures.
- Validate PDF receipt semantics only with the account owner's specific consent.

## Planned improvements

- More explicit empty-page recognizers and school-layout fixtures.
- Extract shared parser fixes into an upstream library so HA and MCP benefit.
- Configurable archive retention, cache cleanup and bulk export controls.
- Additional evidence checks and real-school analysis fixtures.
- More document areas and class-teacher communication reads.
- MFA after inspecting its actual authorized login flow.

## Requires separate investigation

Sick-note submission, leave applications, messages, voting and appointment
bookings. These are not included or promised in v0.2.0. There is no remote HTTP
hosting or PyPI publishing workflow in the initial release.
