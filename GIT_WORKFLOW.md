# Git Workflow for Claude Code Projects

This setup implements trunk-based development with advanced prototyping capabilities, perfectly integrated with Claude Code's parallel agent execution.

## 🎯 Core Principles

1. **Trunk stays green** - main/master must always be deployable
2. **Prototype branches are ephemeral** - create, test, merge/delete within days
3. **Everything is discoverable** - semantic versioning, conventional commits, clear naming
4. **Parallel experimentation** - use git worktrees with multiple Claude agents

## 🚀 Quick Start

### 1. Initialize Git Workflow
```bash
# Run after project setup
./scripts/setup-git-hooks.sh
```

This installs:
- Commit message validation (Conventional Commits)
- Pre-commit test runner
- Git commit template

### 2. Create a Prototype Branch
```bash
# Standard approach
./scripts/git-prototype.sh create JIRA-123 user-authentication

# This creates: prototype/JIRA-123-user-authentication
# Tags: v1.0.0-prototype.abc123
# Runs tests on main first
```

### 3. Parallel Development with Worktrees
```bash
# Create 5 parallel worktrees for different approaches
./scripts/git-prototype.sh worktree payment-system 5

# Then run Claude in each:
cd trees/payment-system-1 && claude
cd trees/payment-system-2 && claude
# etc...
```

## 📝 Commit Standards

### Conventional Commits Format
```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting (no code change)
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance

### Examples
```bash
git commit -m "feat(auth): add OAuth2 integration"
git commit -m "fix(api): handle null response from payment service"
git commit -m "refactor(db): optimize user query performance"
```

## 🏷️ Versioning & Tagging

### Semantic Versioning
```bash
# Create version tags
./scripts/git-prototype.sh tag major  # v2.0.0
./scripts/git-prototype.sh tag minor  # v1.3.0
./scripts/git-prototype.sh tag patch  # v1.2.4
./scripts/git-prototype.sh tag prototype  # v1.2.3-prototype.abc123
```

### Tag Demos & Experiments
```bash
# Tag specific demo builds
git tag v1.0.0-demo.1 -m "Demo for stakeholders"
git tag v1.0.0-experiment.nlp -m "NLP feature experiment"
git push --tags
```

## 🔄 Claude Code Integration

### 1. Single Agent Prototype
```bash
# Create prototype branch
./scripts/git-prototype.sh create FEAT-100 new-dashboard

# Use Claude with git checkpointing
claude /git-flow "Implement dashboard with regular commits"
```

### 2. Multi-Agent Parallel Development
```bash
# Setup worktrees
./scripts/git-prototype.sh worktree search-feature 3

# Run Claude slash command in each worktree
cd trees/search-feature-1
claude /parallel --plan=@specs/search.md --approach="elasticsearch"

cd trees/search-feature-2  
claude /parallel --plan=@specs/search.md --approach="postgresql-fts"

cd trees/search-feature-3
claude /parallel --plan=@specs/search.md --approach="algolia"
```

### 3. Compare & Merge Best Solution
```bash
# Review all implementations
git log --oneline --graph --all

# Checkout best approach
git checkout prototype/search-feature-approach-2

# Prepare for merge
./scripts/git-prototype.sh prepare

# Create PR and squash-merge
```

## 🛡️ Safety Patterns

### Feature Flags for Experiments
```javascript
// In code
if (featureFlags.isEnabled('experimental-ai-search')) {
    return aiSearchImplementation();
} else {
    return standardSearch();
}
```

### Checkpoint Before Risky Operations
```bash
# Before major refactor
./scripts/checkpoint.sh "before-major-refactor"

# Let Claude work
claude "Refactor the entire authentication system"

# If it goes wrong
git reset --hard HEAD
```

### Preview Environments
```yaml
# .github/workflows/preview.yml
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  deploy-preview:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to preview
        run: |
          # Deploy to preview-${{ github.event.number }}.example.com
```

## 📊 Workflow Comparison

| Approach | Use Case | Claude Integration |
|----------|----------|-------------------|
| Single Branch | Simple features | Standard Claude usage |
| Feature Branches | Team collaboration | Git checkpoints + `/git-flow` |
| Worktrees | Parallel experiments | Multiple Claude instances |
| Trunk + Flags | Continuous deployment | Incremental Claude changes |

## 🎭 Advanced Patterns

### 1. A/B Testing Implementations
```bash
# Create two implementations
git worktree add trees/algo-v1 -b prototype/algo-memory-optimized
git worktree add trees/algo-v2 -b prototype/algo-speed-optimized

# Have Claude implement both
# Then benchmark and choose
```

### 2. Automated Commit Generation
```bash
# Let Claude write meaningful commits
claude "Review the changes and create a conventional commit message"
```

### 3. Branch Protection with Claude
```bash
# Before merging, have Claude review
claude /verify "Review this branch for production readiness"
```

## 🧹 Cleanup

### After Successful Merge
```bash
# Delete local prototype branch
git branch -d prototype/JIRA-123-feature

# Delete remote branch
git push origin --delete prototype/JIRA-123-feature

# Clean up worktrees
git worktree remove trees/feature-1
git worktree prune
```

### Stale Branch Cleanup
```bash
# List branches older than 2 weeks
git for-each-ref --format='%(refname:short) %(committerdate)' refs/heads/ | grep prototype/

# Bulk delete old prototype branches
git branch -d $(git branch | grep prototype/ | grep -v $(git branch --show-current))
```

## 🔗 Integration with CI/CD

The setup includes hooks for:
- GitHub Actions (`.github/workflows/`)
- GitLab CI (`.gitlab-ci.yml`)
- Pre-commit validation
- Automated testing on prototype branches

## 💡 Pro Tips

1. **Always checkpoint before Claude experiments**
2. **Use worktrees for truly parallel development**
3. **Tag everything that stakeholders see**
4. **Squash-merge to keep main history clean**
5. **Let Claude handle the Git operations when possible**

Remember: The goal is to prototype fast while maintaining a clean, professional Git history that your team (and future you) will appreciate.