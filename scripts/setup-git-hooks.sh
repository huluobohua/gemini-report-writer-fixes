#!/bin/bash
# Setup Git hooks for commit standards

# Create hooks directory
mkdir -p .git/hooks

# Commit message hook
cat > .git/hooks/commit-msg << 'EOF'
#!/bin/bash
# Validate commit message format

commit_regex='^(feat|fix|docs|style|refactor|test|chore)(\([a-z0-9-]+\))?: .{1,50}'

if ! grep -qE "$commit_regex" "$1"; then
    echo "Invalid commit message format!"
    echo "Format: <type>(<scope>): <subject>"
    echo "Example: feat(auth): add login functionality"
    echo ""
    echo "Types: feat, fix, docs, style, refactor, test, chore"
    exit 1
fi
EOF

chmod +x .git/hooks/commit-msg

# Pre-commit hook for tests
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
# Run tests before commit

if [ -f "package.json" ] && grep -q "test" package.json; then
    echo "Running tests..."
    npm test || {
        echo "Tests failed! Commit aborted."
        echo "Use --no-verify to skip (not recommended)"
        exit 1
    }
fi

# Check for console.log statements
if git diff --cached --name-only | grep -E '\.(js|ts|jsx|tsx)$' | xargs grep -l 'console\.log'; then
    echo "Warning: console.log statements found"
    echo "Remove them or use --no-verify to skip"
    exit 1
fi
EOF

chmod +x .git/hooks/pre-commit

# Setup git commit template
git config --local commit.template .gitmessage

echo "Git hooks installed successfully!"
echo "Commit message validation and pre-commit tests are now active."