# Owner decision —25 October2026

The owner explicitly permits initial UNSIGNED Customer distribution and possible SmartScreen warnings. No paid Authenticode purchase or Store route is required. This replaces the project's signing-only condition; it is not a security/license waiver. Never disable Defender/SmartScreen or claim a verified publisher/reputation.

UNSIGNED mode requires schema2, the exact owner decision reference, actual PE unsigned state, Customer manifest/bytes/hash/source/lock identity, a clean bound RustSec audit, complete corresponding-source/license review, payload closure and separate real Windows/protections/artifact review evidence. The existing native authorization, consent, termination and device gates remain. Unknown modes fail closed. The legacy signed path remains available without weakening its verification.

New source or binary changes need distinct version/provenance and physical regression;73 is preserved as fallback. Browser/public download checks remain required and bound to the final artifact. Metadata validation is not cryptographic proof that a human performed a test. No existing PASS evidence is invented by this decision.

## Raw advisory applicability records

The raw Cargo audit is retained without ignores. A nonzero raw count is not
automatically a Windows release vulnerability, nor permission to ignore it.
`security_audit_gate.py` requires an exact artifact/source/lock/target/audit-bound
review of every finding, with hashed evidence for target or actual API exclusion.
Unknown reachability, low likelihood and risk acceptance do not satisfy this gate.
An excluded advisory is explicitly **not fixed at package level**. The review is
human evidence; the gate verifies bindings and cannot establish exploitability.
New findings, changed artifacts or changed evidence invalidate the review.
