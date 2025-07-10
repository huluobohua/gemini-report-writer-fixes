Git workflow management with trunk-based development principles.

Variables: FEATURE_NAME, COMMIT_TYPE

## Branch Creation
Create prototype branch following naming convention:
- prototype/<ticket>-<description> for experiments
- feature/<ticket>-<description> for features
- fix/<ticket>-<description> for bug fixes

## Commit Standards
Follow Conventional Commits:
- feat: new feature
- fix: bug fix
- docs: documentation
- style: formatting
- refactor: code restructuring
- test: tests
- chore: maintenance

## Workflow
1. Ensure trunk/main is clean and tests pass
2. Create feature branch or worktree
3. Make atomic, focused commits
4. Tag experimental builds (v1.0.0-alpha.1)
5. Push and create PR with clear description
6. Squash-merge to maintain clean history
7. Delete branch after merge

## Feature Flags
For risky experiments, implement behind flags:
- Add flag check before experimental code
- Document flag in CLAUDE.md
- Remove flag after validation