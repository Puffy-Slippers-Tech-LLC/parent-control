# Do-Not-Touch-Portal-Mandate.md

Read this document only when touching feedback API-related application code.

- Never edit or deploy the portal checkout from a client task. Request portal API
  changes in a client `docs/` handoff that states the reason, old and proposed
  contracts, examples, compatibility, release dependencies and acceptance checks.
  Client-specific report presentation and metadata remain in this repository.
- Classify new integrations under [package update activation](../Publishing.md#package-update-activation).
  Ship required [data migrations](../SystemDesign/Data-Migration.md) before
  incompatible readers or writers.
