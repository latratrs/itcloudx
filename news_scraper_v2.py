#!/usr/bin/env python3
"""
TradeShield AI — Weekly Blog Post Generator v2
Run: source ~/tradeshield-env/bin/activate && python ~/itcloudx/news_scraper_v2.py
"""

import os
import re
import json
import feedparser
from datetime import datetime, timezone
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OUTPUT_DIR = os.path.expanduser("~/itcloudx/astrowind/src/data/post/")

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=OFAC+sanctions+trade+compliance+2026&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=HS+code+tariff+customs+misclassification+2026&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=US+import+tariff+changes+freight+forwarder+2026&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=customs+compliance+fine+penalty+importer+2026&hl=en-US&gl=US&ceid=US:en",
]

TAGS = ["Customs", "HS Code", "OFAC", "Tariffs", "Import Compliance", "Trade Compliance", "Sanctions"]

def fetch_articles():
    articles = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]:
            articles.append({
                "title": entry.get("title", ""),
                "summary": entry.get("summary", ""),
                "link": entry.get("link", ""),
            })
    seen = set()
    unique = []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)
    return unique[:8]

def generate_post(articles):
    client = genai.Client(api_key=GEMINI_API_KEY)
    article_text = "\n\n".join([
        f"SOURCE {i+1}: {a['title']}\n{a['summary']}\nURL: {a['link']}"
        for i, a in enumerate(articles)
    ])
    month_year = datetime.now().strftime("%B %Y")
    prompt = f"""You are the content strategist for TradeShield AI (itcloudx.com), an AI customs compliance tool.

Write ONE SEO blog post using these news sources. Be authoritative and specific.

NEWS SOURCES:
{article_text}

Return ONLY valid JSON, no markdown fences, no preamble:
{{
  "seo_title": "Primary keyword first, 55 chars max, include 2026",
  "slug": "lowercase-hyphens-only-50-chars-max",
  "excerpt": "155 chars max. State the main benefit or risk. Include primary keyword.",
  "body": "Full blog post in Markdown. 900-1200 words. Include: opening lede, ## Key Takeaways with 4 emoji bullets, ## main section, ## Why This Matters for Importers, ## How to Stay Compliant with numbered steps, ## Frequently Asked Questions with 4 H3 questions. End with CTA linking to [TradeShield AI free scan](https://itcloudx.com/audit).",
  "faq": [
    {{"question": "specific question importers search about this topic", "answer": "2-3 sentence direct answer"}},
    {{"question": "What penalty or fine is involved?", "answer": "specific answer with dollar amounts if known"}},
    {{"question": "How does TradeShield AI help with this?", "answer": "specific feature explanation"}},
    {{"question": "What steps should importers take?", "answer": "actionable 2-3 sentence answer"}}
  ]
}}

Rules: mention TradeShield AI at least twice naturally. Do not invent fine amounts. Tone: expert, direct. Date context: {month_year}"""

    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    raw = response.text.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    return json.loads(raw)

def write_post(post):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    faq_yaml = "\n".join([
        f"  - question: \"{item['question'].replace(chr(34), chr(39))}\"\n    answer: \"{item['answer'].replace(chr(34), chr(39))}\""
        for item in post.get("faq", [])
    ])
    tags_str = "[" + ", ".join(TAGS) + "]"
    frontmatter = f"""---
title: "{post['seo_title']}"
excerpt: "{post['excerpt']}"
publishDate: {today}
image: /assets/images/default.png
category: Trade Compliance News
tags: {tags_str}
author: TradeShield AI
draft: false
faq:
{faq_yaml}
---
"""
    content = frontmatter + "\n" + post["body"]
    filepath = os.path.join(OUTPUT_DIR, f"{post['slug']}.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Post written: {filepath}")
    print(f"   Title: {post['seo_title']}")
    print(f"   URL: itcloudx.com/blog/{post['slug']}")
    return filepath

def main():
    print("🔍 Fetching trade compliance news...")
    articles = fetch_articles()
    print(f"   Found {len(articles)} articles")
    print("🤖 Generating post with Gemini 2.5 Flash...")
    post = generate_post(articles)
    print("💾 Writing .md file...")
    write_post(post)
    print("\n✨ Done! Run ~/itcloudx/publish.sh to build and deploy.")

if __name__ == "__main__":
    main()
