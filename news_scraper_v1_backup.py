import feedparser
import datetime
import os
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "itcloudx", "astrowind", "src", "data", "post")
MAX_ARTICLES = 8

RSS_QUERIES = [
    "OFAC+sanctions+SDN+list+update",
    "US+EU+customs+import+export+regulations+tariffs",
    "BIS+export+controls+semiconductor",
    "EU+sanctions+package+Russia+Belarus",
]

def fetch_rss_news():
    all_items = []
    seen_titles = set()
    for query in RSS_QUERIES:
        url = f"https://news.google.com/rss/search?q={query}+when:7d&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]:
            title = entry.get("title", "").strip()
            if title and title not in seen_titles:
                seen_titles.add(title)
                all_items.append(f"Title: {title}\nLink: {entry.get('link','')}\nPublished: {entry.get('published','N/A')}\nSummary: {entry.get('summary','N/A')[:300]}\n")
    print(f"✓ Fetched {len(all_items)} articles")
    return "\n---\n".join(all_items[:MAX_ARTICLES])

def generate_astrowind_post(news_context):
    client = genai.Client(api_key=GEMINI_API_KEY)
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    today_iso = datetime.datetime.now().strftime("%Y-%m-%dT00:00:00Z")
    prompt = f"""You are a trade compliance journalist for TradeShield AI (itcloudx.com).
Your readers are everyday importers, Amazon sellers, freight forwarders and small business owners
who ship goods internationally. They are NOT lawyers. Write clearly, avoid jargon, explain everything.

Analyze the raw news below and produce a publish-ready AstroWind blog post.

RAW NEWS:
{news_context}

OUTPUT EXACTLY this structure:

---
title: "[Plain-English SEO title about this week's most important trade compliance story]"
excerpt: "[One sentence: what changed and why a typical importer should care]"
publishDate: {today_iso}
image: ~/assets/images/default.png
category: Compliance News
tags: [Customs, Sanctions, Global Trade, OFAC, Export Controls]
author: TradeShield AI
---

## Key Takeaways
- ⚠️ [Specific action or risk #1]
- 🚨 [Specific action or risk #2]
- 📋 [Specific action or risk #3]
- 💰 [Financial risk or cost impact]
- ✅ [Most important thing to do this week]

## Week in Review
[Exactly 3 sentences written like a newspaper lead. What happened, who it affects, what it means for trade.]

## [Name of most important story this week]

[Write exactly 5 sentences:
Sentence 1 - What exactly changed (name the specific regulation, country, or agency)
Sentence 2 - Why this change was made (geopolitical or enforcement reason)
Sentence 3 - Which specific businesses or products are affected
Sentence 4 - What the financial or legal risk is if ignored (use dollar amounts if available)
Sentence 5 - The single most important action to take this week]

**Risk Level:** HIGH / MEDIUM / LOW
**Who is affected:** [specific business types]
**Act by:** [timeframe]

## [Name of second most important story]

[Same 5-sentence format]

**Risk Level:** HIGH / MEDIUM / LOW
**Who is affected:** [specific business types]
**Act by:** [timeframe]

## Frequently Asked Questions

**Q: [Question a confused importer would Google]**
A: [Clear 2-3 sentence answer in plain English]

**Q: [Question about tariffs, HS codes, or OFAC]**
A: [Answer]

**Q: [Question about what action to take]**
A: [Answer]

**Q: [Question about penalties or fines]**
A: [Answer]

**Q: [Question about a specific country or product mentioned in the news]**
A: [Answer]

RULES: Write for a 10th grade reading level. No jargon without explanation. Use specific dollar amounts, percentages and entity names. DO NOT add any text before the opening --- block. Output markdown only.
"""

    print("✓ Sending to Gemini 2.0 Flash...")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text

def save_post(content):
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    # Generate SEO slug from title
    import re
    title_match = re.search(r'title: "([^"]+)"', post_content)
    if title_match:
        raw_title = title_match.group(1)
        slug = re.sub(r'[^a-z0-9]+', '-', raw_title.lower()).strip('-')[:80]
    else:
        slug = f"trade-compliance-{date_str}"
    filename = f"{slug}.md"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✓ Saved → {filepath}")
    return filepath

if __name__ == "__main__":
    print("\n🛡️  TradeShield AI – News Pipeline Starting...\n")
    print("Step 1/3 · Fetching RSS...")
    raw_data = fetch_rss_news()
    if not raw_data.strip():
        print("⚠ No news fetched.")
        exit(1)
    print("Step 2/3 · Generating with Gemini 2.0 Flash...")
    post_content = generate_astrowind_post(raw_data)
    print("Step 3/3 · Saving...")
    filepath = save_post(post_content)
    print(f"\n✅ Done! File: {filepath}\nNow run: cd ~/itcloudx && npm run build\n")
