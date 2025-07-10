#!/bin/bash
# Advanced Git prototype workflow with best practices

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Function to create semantic version tag
create_version_tag() {
    local version_type=$1
    local current_version=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
    local version_parts=(${current_version//v/})
    version_parts=(${version_parts//./ })
    
    case $version_type in
        "major")
            ((version_parts[0]++))
            version_parts[1]=0
            version_parts[2]=0
            ;;
        "minor")
            ((version_parts[1]++))
            version_parts[2]=0
            ;;
        "patch")
            ((version_parts[2]++))
            ;;
        "prototype")
            local prototype_suffix="-prototype.$(git rev-parse --short HEAD)"
            ;;
    esac
    
    local new_version="v${version_parts[0]}.${version_parts[1]}.${version_parts[2]}${prototype_suffix:-}"
    echo $new_version
}

# Function to create prototype branch
create_prototype() {
    local ticket=$1
    local description=$2
    local branch_name="prototype/${ticket}-${description}"
    
    echo -e "${GREEN}Creating prototype branch: $branch_name${NC}"
    
    # Ensure main is clean
    git checkout main
    git pull origin main
    
    # Run tests on main first
    if [ -f "package.json" ] && grep -q "test" package.json; then
        echo -e "${YELLOW}Running tests on main...${NC}"
        npm test || { echo -e "${RED}Tests failed on main! Aborting.${NC}"; exit 1; }
    fi
    
    # Create branch
    git checkout -b "$branch_name"
    
    # Create initial commit
    echo "# Prototype: $description" > .prototype-notes.md
    echo "Ticket: $ticket" >> .prototype-notes.md
    echo "Created: $(date)" >> .prototype-notes.md
    git add .prototype-notes.md
    git commit -m "chore: initialize prototype for $ticket - $description"
    
    # Tag the start
    local tag=$(create_version_tag "prototype")
    git tag "$tag"
    
    echo -e "${GREEN}Prototype branch created and tagged as $tag${NC}"
    echo -e "${YELLOW}Remember to:${NC}"
    echo "  1. Make atomic commits with conventional format"
    echo "  2. Push regularly: git push -u origin $branch_name"
    echo "  3. Tag demos: git tag v1.0.0-demo.1"
    echo "  4. Squash-merge when ready"
}

# Function to prepare prototype for merge
prepare_merge() {
    local current_branch=$(git branch --show-current)
    
    if [[ ! "$current_branch" =~ ^(prototype|feature|fix)/ ]]; then
        echo -e "${RED}Not on a prototype/feature branch!${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}Preparing $current_branch for merge...${NC}"
    
    # Interactive rebase to clean history
    echo -e "${YELLOW}Opening interactive rebase to clean up commits...${NC}"
    git rebase -i main
    
    # Run tests
    if [ -f "package.json" ] && grep -q "test" package.json; then
        echo -e "${YELLOW}Running tests...${NC}"
        npm test || { echo -e "${RED}Tests failed! Fix before merging.${NC}"; exit 1; }
    fi
    
    # Create final tag
    local tag=$(create_version_tag "prototype")
    git tag "$tag-final"
    
    echo -e "${GREEN}Branch ready for merge!${NC}"
    echo -e "Next steps:"
    echo "  1. Push changes: git push --force-with-lease"
    echo "  2. Create PR with description"
    echo "  3. After approval, squash-merge"
    echo "  4. Delete remote branch"
}

# Function to setup worktree for parallel work
setup_worktree() {
    local feature=$1
    local count=${2:-3}
    
    echo -e "${GREEN}Setting up $count worktrees for feature: $feature${NC}"
    
    mkdir -p trees
    
    for i in $(seq 1 $count); do
        local worktree_path="trees/${feature}-${i}"
        local branch_name="prototype/${feature}-approach-${i}"
        
        git worktree add "$worktree_path" -b "$branch_name"
        
        # Copy any necessary config files
        if [ -f ".env" ]; then
            cp .env "$worktree_path/"
        fi
        
        echo -e "${GREEN}Created worktree $i at $worktree_path${NC}"
    done
    
    echo -e "${YELLOW}Worktrees ready! Run Claude in each:${NC}"
    for i in $(seq 1 $count); do
        echo "  cd trees/${feature}-${i} && claude"
    done
}

# Main command handler
case "$1" in
    "create")
        create_prototype "$2" "$3"
        ;;
    "prepare")
        prepare_merge
        ;;
    "worktree")
        setup_worktree "$2" "$3"
        ;;
    "tag")
        tag=$(create_version_tag "${2:-prototype}")
        git tag "$tag"
        echo -e "${GREEN}Created tag: $tag${NC}"
        ;;
    *)
        echo "Git Prototype Workflow Tool"
        echo ""
        echo "Usage:"
        echo "  $0 create <ticket-id> <description>  - Create prototype branch"
        echo "  $0 prepare                           - Prepare branch for merge"
        echo "  $0 worktree <feature> [count]        - Setup parallel worktrees"
        echo "  $0 tag [major|minor|patch|prototype] - Create semantic tag"
        echo ""
        echo "Examples:"
        echo "  $0 create JIRA-123 user-auth"
        echo "  $0 worktree payment-system 5"
        echo "  $0 tag prototype"
        ;;
esac