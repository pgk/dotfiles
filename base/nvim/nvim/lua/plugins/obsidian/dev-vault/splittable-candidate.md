# Home Lab Migration

Notes that started as one entry and never got split up. Synthetic fixture --
the splittable case for :ObsidianGraphHealth: several headed sections, low
out-degree, and not itself acting as an index the way the hub note does.

## Background

The old NAS is failing and needs replacing before it takes the backups with
it. Options considered so far, in no particular order.

## Bare metal replacement

Buy another off-the-shelf NAS, restore from the last known-good backup, and
keep the same mount points so nothing else has to change.

## Container-based rebuild

Move to a small server running containers instead, one per service, so
individual pieces can be upgraded without touching the rest.

## Open questions

Which approach survives a power outage better, and whether the backup
strategy needs to change either way.

Related: [[hub-note]].
