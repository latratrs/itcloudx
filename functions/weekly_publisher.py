"""
TradeShield AI — Weekly Blog Publisher Cloud Function
Triggered by Cloud Scheduler every Sunday 8am PT
Uses GitHub API to commit articles directly — no git conflicts
"""

import os, re, json, base64, time, feedparser
from datetime import datetime, timezone
from google import genai
from google.genai import types
import functions_framework
import requests

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GITHUB_TOKEN   = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO    = "latratrs/itcloudx"
GITHUB_BRANCH  = "main"
POST_DIR       = "astrowind/src/data/post"
IMAGE_DIR      = "astrowind/src/assets/images"

TOPIC_CLUSTERS = [
    {
        "name": "Sanctions & OFAC",
        "feeds": [
            "https://home.treasury.gov/system/files/126/ofac_recent_actions.xml",
            "https://feeds.reuters.com/reuters/businessNews",
        ],
        "angle": "OFAC/EU/UN sanctions enforcement, counterparty screening. Target: freight forwarders.",
        "tags": ["Sanctions", "OFAC", "Export Controls", "Trade Compliance"],
        "image_prompt": "Professional photojournalism, trade compliance operations center, analysts monitoring world map with flagged shipping routes, dark navy blue and teal, no text, ultra realistic",
    },
    {
        "name": "Tariffs & HS Codes",
        "feeds": [
            "https://feeds.reuters.com/reuters/businessNews",
            "https://www.cbp.gov/trade/rss/trade-news.xml",
        ],
        "angle": "Tariff changes, HS code risks, Section 301/232 surcharges. Target: importers.",
        "tags": ["Tariffs", "HS Code", "Section 301", "Import Compliance"],
        "image_prompt": "Professional photojournalism, international shipping port at golden hour, cargo containers, customs officers, no text, no signs, cinematic, ultra realistic",
    },
    {
        "name": "Global Trade Enforcement",
        "feeds": [
            "https://www.cbp.gov/trade/rss/trade-news.xml",
            "https://feeds.reuters.com/reuters/businessNews",
        ],
        "angle": "CBP enforcement, UFLPA supply chain risks. Target: manufacturers.",
        "tags": ["CBP Enforcement", "UFLPA", "Supply Chain", "Trade Compliance"],
        "image_prompt": "Professional photojournalism, US customs border inspection at port, cargo area, official atmosphere, no text, no signs, ultra realistic, wide angle",
    },
]


def github_get(path):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    r = requests.get(url, headers={
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }, params={"ref": GITHUB_BRANCH})
    return r.json() if r.status_code == 200 else None


def github_put(path, content_bytes, message, sha=None):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    payload = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode(),
        "branch": GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(url, headers={
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }, json=payload)
    if r.status_code not in (200, 201):
        print(f"GitHub PUT failed {r.status_code}: {r.text[:300]}")
    return r.status_code in (200, 201), r.status_code, r.text[:200]


def fetch_articles(cluster):
    articles = []
    for url in cluster["feeds"]:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                t = entry.get("title", "")
                if t:
                    articles.append({
                        "title": t,
                        "summary": entry.get("summary", ""),
                    })
        except Exception:
            pass
    seen, unique = set(), []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)
    # Always return at least topic-based fallback so article is always generated
    if not unique:
        month = datetime.now().strftime("%B %Y")
        unique = [
            {"title": f"{cluster['name']} enforcement update {month}", "summary": f"Latest {cluster['name']} regulatory changes affecting importers and freight forwarders in {month}."},
            {"title": f"2026 {cluster['name']} compliance requirements", "summary": f"New compliance requirements for {cluster['name']} that importers must follow in 2026."},
        ]
    return unique[:5]


def generate_article(client, cluster, articles):
    article_text = "\n".join([f"- {a['title']}: {a['summary'][:200]}" for a in articles])
    month_year = datetime.now().strftime("%B %Y")
    
    body_prompt = f"""You are a trade compliance expert writing for TradeShield AI (itcloudx.com).
Write a complete 1500-word blog article about: {cluster['name']}
Focus: {cluster['angle']}
Date: {month_year}

News sources:
{article_text}

Write ALL these sections completely:
## Key Takeaways (4 emoji bullets)
## The 2026 {cluster['name']} Landscape (400 words)
## Real-World Impact on Importers (300 words)  
## How to Stay Compliant (5 numbered steps, 300 words)
## FAQ (4 questions with answers)
End with CTA to [TradeShield AI free scan](https://itcloudx.com/audit).
Mention TradeShield AI 2+ times. Minimum 1400 words."""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=body_prompt,
        config=types.GenerateContentConfig(max_output_tokens=16384, temperature=1.0)
    )
    return response.text.strip()


def generate_metadata(client, cluster, body):
    meta_prompt = f"""Generate SEO metadata for this trade compliance article.
Topic: {cluster['name']}
Excerpt: {body[:400]}
Return ONLY valid JSON:
{{"seo_title":"keyword-first 55 chars include 2026","slug":"lowercase-hyphens-50-chars","excerpt":"155 chars benefit or risk","category":"Trade Compliance News"}}"""
    
    r = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=meta_prompt,
        config=types.GenerateContentConfig(max_output_tokens=512, temperature=0.2)
    )
    raw = re.sub(r'^```json\s*|^```\s*|\s*```$', '', r.text.strip()).strip()
    try:
        return json.loads(raw)
    except Exception:
        slug = cluster['name'].lower().replace(' ', '-').replace('&', 'and')
        return {"seo_title": f"{cluster['name']} Guide 2026", "slug": slug,
                "excerpt": f"{cluster['name']} compliance guidance for 2026.", "category": "Trade Compliance News"}


def generate_image(client, slug, image_prompt):
    prompts = [image_prompt, image_prompt + " Wide angle, no text, photorealistic."]
    for prompt in prompts:
        try:
            r = client.models.generate_images(
                model="imagen-4.0-generate-001",
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="16:9",
                    safety_filter_level="block_low_and_above",
                    person_generation="dont_allow",
                )
            )
            if r.generated_images:
                img_bytes = r.generated_images[0].image.image_bytes
                if img_bytes:
                    return img_bytes, f"weekly-cover-{slug[:35]}.jpg"
        except Exception as e:
            print(f"Image error: {e}")
        time.sleep(2)
    return None, None


def build_markdown(meta, body, tags, image_path, faq_items):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tags_str = "[" + ", ".join(tags) + "]"
    faq_yaml = "\n".join([
        f"  - question: \"{q.replace(chr(34), chr(39))}\"\n    answer: \"{a.replace(chr(34), chr(39))}\""
        for q, a in faq_items
    ])
    return f"""---
title: "{meta['seo_title']}"
excerpt: "{meta['excerpt']}"
publishDate: {today}
image: {image_path}
category: {meta.get('category', 'Trade Compliance News')}
tags: {tags_str}
author: TradeShield AI
draft: false
faq:
{faq_yaml}
---

{body}
""".encode('utf-8')


@functions_framework.http
def weekly_publish(request):
    """HTTP trigger — called by Cloud Scheduler every Sunday"""
    
    if not GEMINI_API_KEY:
        return json.dumps({"error": "GEMINI_API_KEY not set"}), 500
    if not GITHUB_TOKEN:
        return json.dumps({"error": "GITHUB_TOKEN not set"}), 500

    client = genai.Client(api_key=GEMINI_API_KEY)
    results = []

    for cluster in TOPIC_CLUSTERS:
        try:
            print(f"Processing: {cluster['name']}")
            articles = fetch_articles(cluster)
            if not articles:
                results.append({"cluster": cluster['name'], "status": "skipped", "reason": "no sources"})
                continue

            body    = generate_article(client, cluster, articles)
            meta    = generate_metadata(client, cluster, body)
            slug    = meta["slug"]
            
            # Generate image and commit to GitHub
            img_bytes, img_filename = generate_image(client, slug, cluster["image_prompt"])
            if img_bytes and img_filename:
                img_path = f"{IMAGE_DIR}/{img_filename}"
                img_sha = None
                existing = github_get(img_path)
                if existing:
                    img_sha = existing.get("sha")
                ok, code, msg = github_put(img_path, img_bytes, f"content: add cover image {img_filename}", img_sha)
                print(f"Image commit: {code} {msg}")
                image_frontmatter = f"~/assets/images/{img_filename}"
            else:
                image_frontmatter = "~/assets/images/TradeShield-AI.jpg"

            # Build markdown
            faq_items = [
                (f"What are main {cluster['name']} risks in 2026?", "Importers face increased enforcement and penalties."),
                ("What fines apply?", "Penalties can reach $1M+ per violation."),
                (f"How does TradeShield AI help?", "Real-time OFAC screening, 10-digit HTS codes, Section 301 calculation."),
                ("What should importers do now?", "Audit HS codes, screen counterparties, run a free TradeShield AI scan.")
            ]
            md_content = build_markdown(meta, body, cluster["tags"], image_frontmatter, faq_items)

            # Commit markdown to GitHub
            post_path = f"{POST_DIR}/{slug}.md"
            existing_post = github_get(post_path)
            post_sha = existing_post.get("sha") if existing_post else None
            
            success, code, msg = github_put(post_path, md_content, f"content: weekly publish {slug}", post_sha)
            print(f"Post commit: {code} {msg}")
            
            results.append({
                "cluster": cluster['name'],
                "status": "success" if success else "failed",
                "slug": slug,
                "words": len(body.split())
            })
            time.sleep(3)

        except Exception as e:
            results.append({"cluster": cluster['name'], "status": "error", "error": str(e)})

    return json.dumps({"results": results, "timestamp": datetime.now().isoformat()}), 200
