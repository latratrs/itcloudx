#!/bin/bash
source ~/tradeshield-env/bin/activate
python ~/itcloudx/news_scraper_v2.py
cd ~/itcloudx/astrowind && npm run build
cd ~/itcloudx && firebase deploy --only hosting
