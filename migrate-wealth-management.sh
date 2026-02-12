#!/bin/bash
set -e

echo "🚀 Migrating wealth-management to independent repo..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Step 1: Copy wealth-management folder to parent directory
echo -e "${BLUE}📦 Step 1: Copying wealth-management to /Users/graham/Documents/repos/${NC}"
cp -r /Users/graham/Documents/repos/phd-practice/wealth-management /Users/graham/Documents/repos/

# Step 2: Remove from phd-practice git tracking
echo -e "${BLUE}🗑️  Step 2: Removing from phd-practice git tracking${NC}"
cd /Users/graham/Documents/repos/phd-practice
git rm -r --cached wealth-management

# Step 3: Add to phd-practice .gitignore
echo -e "${BLUE}🚫 Step 3: Adding to phd-practice .gitignore${NC}"
echo "" >> .gitignore
echo "# Wealth management app (now independent repo)" >> .gitignore
echo "wealth-management/" >> .gitignore

# Step 4: Commit the removal
echo -e "${BLUE}💾 Step 4: Committing removal from phd-practice${NC}"
git add .gitignore
git commit -m "Remove wealth-management folder - now independent repo"

# Step 5: Initialize git in new location
echo -e "${BLUE}🎯 Step 5: Initializing git in new location${NC}"
cd /Users/graham/Documents/repos/wealth-management
git init
git add .
git commit -m "Initial commit: Wealth Management App

- React 18.3.1 + IBM Carbon Design System
- FastAPI backend with PostgreSQL
- 5 pages: Dashboard, Holdings, Income, Import, Stock Prices
- Responsive 14-column grid
- Docker deployment ready"

echo ""
echo -e "${GREEN}✅ Migration complete!${NC}"
echo ""
echo "Next steps:"
echo "1. cd /Users/graham/Documents/repos/wealth-management"
echo "2. git remote add origin <your-remote-url>"
echo "3. git branch -M main"
echo "4. git push -u origin main"
echo ""
echo "Then update server paths:"
echo "• SSH to server and move /root/phd-practice/wealth-management to /root/wealth-management"
echo "• Update nginx config if needed"
echo "• Run deployment from new location"
