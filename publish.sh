#!/bin/bash
# TradeShield AI — Weekly Publish Script
# Runs every Sunday: generates 3 articles, builds, deploys, commits
set -e

echo "🚀 TradeShield AI Weekly Publish — $(date)"

# Activate Python env
source ~/tradeshield-env/bin/activate

# Generate 3 new blog posts
python3 ~/itcloudx/news_scraper_v2.py

# Build Astro site
cd ~/itcloudx/astrowind && npm run build

# Deploy to Firebase
cd ~/itcloudx && firebase deploy --only hosting

# Commit new posts to GitHub
git add astrowind/src/data/post/
git commit -m "content: weekly 3-article publish $(date +%Y-%m-%d)" || echo "Nothing to commit"
git push origin main

echo "✅ Weekly publish complete!"
