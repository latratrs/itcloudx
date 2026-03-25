#!/usr/bin/env python3
"""
TradeShield AI — Weekly Blog Generator v3.3
Generates 3 articles + Imagen 4 cover images per run.
Run: source ~/tradeshield-env/bin/activate && python3 ~/itcloudx/news_scraper_v2.py
"""

import os, re, json, feedparser, time
from datetime import datetime, timezone
from google import genai
from google.genai import types
import pkg_resources

def check_libraries():
    try:
        dist = pkg_resources.get_distribution("google-generativeai")
        print(f"   ✅ google-generativeai version: {dist.version}")
    except pkg_resources.DistributionNotFound:
        print("   ⚠ google-generativeai not found")


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OUTPUT_DIR = os.path.expanduser("~/itcloudx/astrowind/src/data/post/")
IMAGE_DIR  = os.path.expanduser("~/itcloudx/astrowind/src/assets/images/")

TOPIC_CLUSTERS = [
    {
        "name": "Sanctions & OFAC",
        "feeds": [
            "https://news.google.com/rss/search?q=OFAC+sanctions+enforcement+2026&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=US+Treasury+sanctions+trade+violation+fine&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=EU+UN+sanctions+list+export+controls+2026&hl=en-US&gl=US&ceid=US:en",
        ],
        "angle": "OFAC/EU/UN sanctions enforcement, new designations, counterparty screening. Target: freight forwarders, compliance officers.",
        "tags": ["Sanctions", "OFAC", "Export Controls", "Trade Compliance", "Customs"],
        "image_prompt": "Cinematic aerial view of busy US customs border crossing checkpoint, long line of cargo trucks waiting for inspection, border patrol vehicles, official government facility, golden hour lighting, no text, no signs, photorealistic wide angle shot",
    },
    {
        "name": "Tariffs & HS Codes",
        "feeds": [
            "https://news.google.com/rss/search?q=US+tariff+changes+Section+301+232+2026&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=HTS+HS+code+misclassification+customs+penalty&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=China+trade+war+tariff+importer+2026&hl=en-US&gl=US&ceid=US:en",
        ],
        "angle": "Tariff changes, HS code classification risks, Section 301/232 surcharges. Target: Amazon FBA sellers, importers, customs brokers.",
        "tags": ["Tariffs", "HS Code", "Section 301", "Import Compliance", "Customs Duties"],
        "image_prompt": "Professional photojournalism, customs officer in uniform carefully inspecting commercial cargo inside a warehouse, packages on conveyor belt, scanning equipment, official inspection facility, bright clean lighting, no text, no signs, ultra realistic",
    },
    {
        "name": "Global Trade Enforcement",
        "feeds": [
            "https://news.google.com/rss/search?q=CBP+customs+enforcement+seizure+detention+2026&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=UFLPA+forced+labor+supply+chain+Xinjiang+2026&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=global+trade+compliance+freight+forwarder+risk+2026&hl=en-US&gl=US&ceid=US:en",
        ],
        "angle": "CBP enforcement, UFLPA supply chain risks, shipment detentions, AI compliance tools. Target: logistics, manufacturers.",
        "tags": ["CBP Enforcement", "UFLPA", "Supply Chain", "Trade Compliance", "Import Audit"],
        "image_prompt": "Bird eye view of major international logistics hub, dozens of semi trucks and cargo vehicles on highway interchange near distribution center, complex road network, dusk lighting, no text, no signs, cinematic drone photography, ultra realistic",
    },
]


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
                        "link": entry.get("link", ""),
                    })
        except Exception as e:
            print(f"   ⚠ Feed error: {e}")
    seen, unique = set(), []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)
    return unique[:6]


def generate_article_body(client, cluster, articles):
    """Generate long article body separately — not inside JSON."""
    article_text = "\n\n".join([
        f"SOURCE {i+1}: {a['title']}\n{a['summary']}"
        for i, a in enumerate(articles)
    ])
    month_year = datetime.now().strftime("%B %Y")

    prompt = f"""You are a senior trade compliance analyst writing for TradeShield AI (itcloudx.com).

Write a complete 1600-word blog article about: {cluster['name']}
Editorial focus: {cluster['angle']}
Date: {month_year}

Real news sources to reference:
{article_text}

Write the COMPLETE article with ALL these sections:

## Key Takeaways
- 🚨 (key risk point)
- 💰 (financial impact)
- 📋 (compliance requirement)
- 🛡️ (how AI helps)

## The 2026 {cluster['name']} Landscape
(Write 400 words covering the current regulatory environment, specific enforcement actions, countries involved, and dollar amounts from the sources above.)

## Real-World Impact on Importers and Freight Forwarders
(Write 300 words on specific business impacts, operational risks, case examples, and financial exposure.)

## Why Customs Brokers and Compliance Teams Are on Alert
(Write 250 words on liability shifts, documentation requirements, and audit risk.)

## How to Stay Compliant: 5 Steps for 2026
1. (Step with 2-3 sentences of detail)
2. (Step with 2-3 sentences of detail)
3. (Step with 2-3 sentences of detail)
4. (Step with 2-3 sentences of detail)
5. (Step with 2-3 sentences of detail)

## Frequently Asked Questions

### What are the biggest {cluster['name']} risks in 2026?
(Write a detailed 3-sentence answer.)

### What fines and penalties apply?
(Write specific figures. Use "up to" if unsure of exact amounts.)

### How does TradeShield AI help with {cluster['name']}?
(Explain specifically: real-time OFAC/EU/UN screening, 10-digit HTS codes, Section 301/232 surcharge calculation, PDF compliance reports.)

### What should importers do right now?
(3 concrete actionable steps with timelines.)

---
Ready to protect your shipments? Run a [free compliance scan with TradeShield AI](https://itcloudx.com/audit) and get your full risk report in 60 seconds.

IMPORTANT: Write every section completely. Do not summarize or skip. Minimum 1400 words."""

    best_body = ""
    for attempt in range(3):
        model_name = "gemini-2.5-flash"
        response = client.models.generate_content(
            model=model_name,
            contents=prompt if attempt == 0 else prompt + f"\n\nNote: Previous attempt was {len(best_body.split())} words. Write all sections completely to reach 1400+ words.",
            config=types.GenerateContentConfig(
                max_output_tokens=16384,
                temperature=1.0
            )
        )
        body = response.text.strip()
        words = len(body.split())
        print(f"   📝 Attempt {attempt+1} ({model_name}): {words} words")
        if words > len(best_body.split()):
            best_body = body
        if words >= 1200:
            break
        time.sleep(3)
    return best_body


def generate_metadata(client, cluster, body):
    """Generate SEO metadata as small reliable JSON."""
    prompt = f"""Based on this trade compliance article, generate SEO metadata.
Topic: {cluster['name']}
Article excerpt: {body[:600]}

Return ONLY valid JSON, no markdown fences:
{{
  "seo_title": "keyword-first title 55 chars max include 2026",
  "slug": "lowercase-hyphens-only-50-chars-max",
  "excerpt": "155 chars max, lead with risk or benefit, include primary keyword",
  "category": "one of: Trade Compliance News | Sanctions | Tariffs | UFLPA | Export Controls | Customs Filing"
}}"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(max_output_tokens=512, temperature=0.2)
    )
    raw = re.sub(r'^```json\s*|^```\s*|\s*```$', '', response.text.strip()).strip()
    try:
        return json.loads(raw)
    except Exception:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {
            "seo_title": f"{cluster['name']} Compliance Guide 2026",
            "slug": f"{cluster['name'].lower().replace(' ', '-').replace('&', 'and')}-2026",
            "excerpt": f"Essential {cluster['name']} compliance guidance for 2026 importers and freight forwarders.",
            "category": "Trade Compliance News"
        }


def generate_faq(client, cluster, body):
    """Generate FAQ pairs for schema markup."""
    prompt = f"""Generate 4 FAQ pairs for this trade compliance article about {cluster['name']}.
Article excerpt: {body[:400]}

Return ONLY valid JSON array, no markdown:
[
  {{"question": "specific importer question about {cluster['name']}", "answer": "2-3 sentence direct answer"}},
  {{"question": "what fines or penalties apply in 2026", "answer": "specific regulatory figures"}},
  {{"question": "how does TradeShield AI help with {cluster['name']}", "answer": "specific feature: OFAC screening, HTS codes, Section 301 calculation"}},
  {{"question": "what should importers do immediately", "answer": "3 concrete steps"}}
]"""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(max_output_tokens=1024, temperature=0.2)
    )
    raw = re.sub(r'^```json\s*|^```\s*|\s*```$', '', response.text.strip()).strip()
    try:
        return json.loads(raw)
    except Exception:
        return [
            {"question": f"What are the main {cluster['name']} risks in 2026?", "answer": "Importers face increased enforcement, higher penalties, and stricter documentation requirements in 2026."},
            {"question": "What fines apply for non-compliance?", "answer": "Penalties can reach $1M+ per violation depending on the regulatory framework involved."},
            {"question": "How does TradeShield AI help?", "answer": "TradeShield AI provides real-time OFAC/EU/UN screening, 10-digit HTS classification, and Section 301/232 surcharge calculation."},
            {"question": "What should importers do now?", "answer": "1. Audit your current HS codes. 2. Screen all counterparties against sanctions lists. 3. Run a free TradeShield AI compliance scan."}
        ]


def generate_image(client, slug, image_prompt):
    """Generate cover image using Imagen 4."""
    prompts = [
        image_prompt,
        image_prompt + " Professional wide angle shot, no text anywhere, photorealistic.",
        "Wide angle aerial view of international cargo port, shipping containers, cranes, global trade, no text, cinematic, ultra realistic, deep blue tones",
    ]
    for attempt, prompt in enumerate(prompts):
        try:
            print(f"   🖼 Image attempt {attempt+1}...")
            response = client.models.generate_images(
                model="imagen-4.0-generate-001",
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="16:9",
                    safety_filter_level="block_low_and_above",
                    person_generation="dont_allow",
                )
            )
            if not response.generated_images:
                print(f"   ⚠ No images in response")
                time.sleep(2)
                continue
            img_bytes = response.generated_images[0].image.image_bytes
            if not img_bytes:
                print(f"   ⚠ image_bytes empty")
                continue
            filename = f"weekly-cover-{slug[:35]}.jpg"
            filepath = os.path.join(IMAGE_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(img_bytes)
            print(f"   ✅ Image saved: {filename}")
            return f"~/assets/images/{filename}"
        except Exception as e:
            print(f"   ⚠ Imagen error: {e}")
            time.sleep(3)
    print("   ⚠ Using fallback image")
    return "~/assets/images/TradeShield-AI.jpg"


def slug_exists(slug):
    return os.path.exists(os.path.join(OUTPUT_DIR, f"{slug}.md"))


def write_post(meta, faq, body, tags_str, image_path):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    slug = meta["slug"]
    if slug_exists(slug):
        slug += "-" + datetime.now().strftime("%m%d")

    faq_yaml = "\n".join([
        f"  - question: \"{item['question'].replace(chr(34), chr(39))}\"\n"
        f"    answer: \"{item['answer'].replace(chr(34), chr(39))}\""
        for item in faq
    ])

    content = f"""---
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
"""
    filepath = os.path.join(OUTPUT_DIR, f"{slug}.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    word_count = len(body.split())
    print(f"  ✅ {meta['seo_title']} ({word_count} words)")
    print(f"     → itcloudx.com/blog/{slug}")
    return filepath


def main():
    print("🌐 TradeShield AI — Weekly Blog Generator v3.3")
    print("   3 articles · 1400-2000 words · Imagen 4 covers")
    check_libraries()
    print("")

    client = genai.Client(api_key=GEMINI_API_KEY)
    written = []

    for i, cluster in enumerate(TOPIC_CLUSTERS):
        print(f"📰 [{i+1}/3] {cluster['name']}")
        articles = fetch_articles(cluster)
        print(f"   Found {len(articles)} sources")
        if not articles:
            print("   ⚠ Skipping — no sources")
            continue
        try:
            body = generate_article_body(client, cluster, articles)
            meta = generate_metadata(client, cluster, body)
            faq  = generate_faq(client, cluster, body)
            tags_str = "[" + ", ".join(cluster["tags"]) + "]"
            image_path = generate_image(client, meta["slug"], cluster["image_prompt"])
            filepath = write_post(meta, faq, body, tags_str, image_path)
            written.append(filepath)
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            import traceback; traceback.print_exc()

        if i < len(TOPIC_CLUSTERS) - 1:
            time.sleep(4)

    print(f"\n✨ {len(written)}/3 articles written.")
    print("   Run ~/itcloudx/publish.sh to build and deploy.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⛔ Interrupted safely")
