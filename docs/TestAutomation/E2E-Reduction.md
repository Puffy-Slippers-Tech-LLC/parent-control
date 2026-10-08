# Suggested test reductions

First suggestion for review. Keep strong coverage of time limits and app limits,
with fewer repeated journeys for remembered request choices.

| Task name and link | What the task checks | Reason to cut or reduce |
| --- | --- | --- |
| Remember request choices: [desktop to station, first child first (156)](E2E-Tasks/156-case-58.md); [desktop to station, second child first (156b)](E2E-Tasks/156b-case-59.md); [station to desktop, first child first (157)](E2E-Tasks/157-case-60.md); [station to desktop, second child first (157b)](E2E-Tasks/157b-case-61.md) | Two children choose how much extra time to request and whether to ask for temporary app access. Their choices follow them between the request form on their desktop and the request station on the sign-in screen. Each screen remembers its own selected parent. | **Reduce four journeys to one.** Give the children different choices, check them at the other screen, change them there, then return and check again. Keep both children’s choices separate and check each screen’s remembered parent. The extra journeys mainly repeat these checks with a different child or screen first. Dropping them gives less coverage of problems that depend on starting order, but preserves both directions and both children. Remembering choices is a convenience; use the saved effort to check that time and app limits work. |
