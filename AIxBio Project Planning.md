
With Claude 4.6/4.7

---

### Architecture: BioWatch Brief

The core idea is a **linear pipeline**: text in → enrichment → structured card out. No fancy infrastructure, no databases to stand up, no auth systems. Just a loop that works.

Here's how each layer actually works in practice, and what's realistic to build over a weekend:

**Input layer (Friday evening, ~2 hrs)** The UI is just a text area (paste) and optionally a URL field. If you fetch a URL, run a simple `fetch` + HTML-stripping step server-side. Nothing fancy — the goal is to get raw text into the pipeline.

**Enrichment layer (the core — Saturday)** Person A's whole job. The key insight is to use Claude's _tool use / structured output_ feature rather than asking for free-form prose. You define a JSON schema up front — something like `risk_level`, `pathogen_summary`, `regulatory_context`, `recommended_actions`, `uncertainty_flags` — and Claude fills it. This gives you a reliably parseable result that Person B can render without defensive spaghetti code.

The prompt template is where all the biosecurity domain knowledge lives. You don't need a biology PhD to write it — you just need to be explicit: _"You are a biosecurity risk analyst. Given the following incident report, classify the risk level on a scale of 1–5 and justify each field..."_

**RAG sidecar (Saturday stretch goal)** If you have time, Person C can set up a lightweight retrieval step — fetch the latest ProMED or WHO feeds, embed them, and inject the top-3 relevant snippets into the prompt as context. This dramatically improves accuracy for real incidents. But if time runs out, _skip it_ — the base LLM already knows a lot about pathogens.

**Output layer (Sunday morning)** The card should be scannable in 30 seconds. Color-coded risk level badge, bullet fields, and a collapsible "raw reasoning" section for judges who want to see the model's work.

---

**Suggested stack:** Python + FastAPI on the backend (Person A is comfortable here), Streamlit for the frontend (Person B can ship this in hours — it's designed for exactly this kind of prototype), and the Anthropic SDK for the LLM calls. No database needed — stateless per-request.

**My recommendation: ship a "thin RAG" architecture.** One curated corpus, prepared ahead of time, not live-fetched. More on this below.
### Suggested architecture

Here's how I'd organize it for three people working in parallel from hour one:

**Layer 1 — Input & orchestration (Python backend, FastAPI)** A single endpoint that takes pasted text and returns a structured JSON card. This is the contract the frontend and the LLM pipeline both code against, so define it first — before anyone writes real code. Something like:

```
{
  "pathogen": {...},
  "risk_classification": {level, rationale, confidence},
  "policy_context": [{citation, relevance, snippet}],
  "historical_analogs": [{event, year, similarity, outcome}],
  "recommended_actions": [{action, priority, rationale}],
  "uncertainty_flags": [...]
}
```

Lock this schema in the first hour. It's the interface everything else plugs into.

**Layer 2 — LLM pipeline (the reasoning work)** Don't do this as one giant prompt. Break it into 3–4 sequential Claude calls, each with a narrow job:

1. **Extraction** — pull structured facts from the input (pathogen name/family, location, case counts, transmission mode, date). Small, reliable, cheap.
2. **Classification** — given the extracted facts, assign risk level with rationale. This is where you want Claude to show reasoning.
3. **Context retrieval** — _now_ you hit your corpus (see Layer 3) with the extracted pathogen/keywords, not the raw pasted text.
4. **Synthesis** — assemble the final card, including uncertainty flags (which should be generated, not hardcoded — Claude flagging what it couldn't determine is the most valuable output).

The win here: each step is independently testable, failures are localized, and you can demo intermediate outputs if the full pipeline breaks during judging.

**Layer 3 — The "corpus" (not really RAG)** Instead of live-fetching, pre-build a small curated JSON file of ~50–100 entries: historical outbreaks (SARS, MERS, mpox, H5N1, Nipah, etc.) with structured fields (pathogen, year, case count, CFR, WHO response, lessons), plus ~20–30 policy snippets (BWC articles, US Select Agent list highlights, IHR core capacities, synthesis screening frameworks like IGSC). Your teammate on data spends Saturday morning building this, not wrestling with RSS feeds.

Then "retrieval" is just keyword/embedding match over this small corpus — could literally be cosine similarity on OpenAI embeddings with a JSON file, no vector DB needed. For 100 entries, a linear scan is instant.

This is intellectually honest (you cite real sources) and technically tractable (no scraping infrastructure). In the writeup, you frame it as "MVP corpus, extensible to live feeds" — which is true.

**Layer 4 — Frontend** Streamlit if your UI person is Python-native; Next.js if they're JS-native. Don't mix. For a 48hr demo, Streamlit gets you to a polished-looking card faster, but looks unmistakably like a hackathon tool. Next.js with a decent component library (shadcn) looks like a product but costs you ~4 extra hours. Given you mentioned "practitioner tools that don't exist yet" is the mandate — looking like a real tool probably wins over looking like a notebook.
### Team division (concrete)

- **Person A (LLM pipeline):** prompt engineering for the 4 stages, output schema validation, uncertainty flag generation. Owns `/assess` endpoint logic.
- **Person B (frontend + integration):** UI, the paste-report flow, rendering the card nicely, export-to-PDF button (judges love this). Owns the demo.
- **Person C (corpus + writeup):** builds the curated dataset on day 1, then shifts to writeup + demo scenarios on day 2. This person's job flips mid-hackathon, which is good — keeps them engaged through the whole sprint.
### Two things I'd push back on from your plan

**"Comparable historical incidents" is the hardest feature to do well.** Similarity matching on outbreaks is genuinely subtle (is mpox-2022 analogous to SARS-2003? in what dimension?). I'd either (a) have Claude generate the comparison narratively given retrieved candidates rather than trying to rank-score similarity, or (b) scope it down to "here are 2–3 outbreaks involving this pathogen family" which is much more tractable.

**Don't promise live data sources in the demo.** Judges will ask "is this pulling from ProMED right now?" and you want to honestly say "the v1 uses a curated corpus; live ingest is designed for but not wired up." Overpromising and having it fail live is worse than a tight, honest scope.
### One architectural thing worth getting right

Build a "scenario library" of 5–8 pre-tested input reports (a ProMED alert, a news article, an ambiguous lab finding, a clearly-nothing case, a clearly-serious case) that you _know_ produce good output. During judging, you demo from this library. Don't let judges paste arbitrary text into a fresh tool — that's how demos die. Have a "try an example" dropdown prominently in the UI.

https://molloy.libguides.com/c.php?g=58086&p=373380

Above is a Molloy University library page that aggregates RSS feeds from a bunch of public-health sources: CDC Travel Notices, CDC Weekly Disease Count, CDC Outbreaks Affecting International Travelers, MedlinePlus, Kaiser Global Health, NYT Health, EPA news, and some NLM bulletins.

**The page itself isn't what you want to use — but the list of sources behind it absolutely is.** Let me explain the distinction, because it matters for architecture.
### What this page actually is

It's a human-curated "directory" of health news RSS feeds, aggregated with LibGuides' embedded RSS widget (the "Loading..." placeholders are where the feeds render for a library patron). You don't want to scrape Molloy's page — that's a fragile dependency on a third party's widget. What you want is the **underlying sources** they've curated, which are reputable and all have their own public RSS/APIs:
- **CDC Travel Notices** — outbreak alerts by country
- **CDC Outbreaks Affecting International Travelers** — a cleaner version of the same
- **CDC NNDSS (National Notifiable Diseases)** — weekly US case counts by disease
- **MedlinePlus** — NIH plain-language disease info
- **Kaiser Global Health** — policy-flavored global health news
- **NYT Health** — general news signal

Molloy did the work of picking a decent signal-to-noise set of feeds for public health practitioners. You're piggybacking on their curation judgment, not their infrastructure.
### How to incorporate it — and where to be careful

This is where I'd push back on my own earlier advice slightly. In my last message I said "don't do live RSS ingest, use a curated JSON corpus." That's still right for **historical context** (the "comparable incidents" feature). But this set of sources suggests a second, genuinely valuable feature that I think is worth adding if one teammate has bandwidth:

**Feature: "Current signal check"** — when a user pastes a report about, say, a novel H5N1 cluster, the tool cross-references whether CDC Travel Notices, NNDSS, or Kaiser are currently flagging anything on the same pathogen/region. This is a legitimately useful practitioner workflow — "is this an isolated report or part of a broader signal?" — and it's exactly the kind of thing a biosecurity analyst would otherwise do by hand.
#### Revised architecture adjustment

Add a thin **"live signals" module** to Layer 3, separate from your curated historical corpus:

```
Layer 3: Knowledge
├── Historical corpus (static JSON, pre-built)
│   └── 50-100 outbreak records for "comparable incidents"
└── Live signals module (light RSS poll, on-demand)
    ├── CDC Travel Notices RSS
    ├── CDC Outbreak RSS  
    ├── NNDSS weekly data
    └── Kaiser Global Health RSS
```

The live signals module should be:

- **Cached aggressively** — poll each feed once every 30 min max, store in memory or a tiny SQLite file. Never hit live feeds during a demo.
- **Pre-warmed before judging** — run the poller Saturday night so your cache is full of real current alerts when judges are watching Sunday.
- **Queried, not retrieved** — when a report comes in, you extract the pathogen in Stage 1 of the LLM pipeline, then filter the cached feed items for matching keywords. No embeddings needed; regex/fuzzy match on pathogen names and locations is plenty.
#### Implementation note that will save you hours

Don't write custom RSS parsers. Use `feedparser` in Python — it handles all the format variants CDC/NYT/Kaiser serve. A functioning signals module is ~40 lines:

```python
import feedparser, time
FEEDS = {
  "cdc_travel": "https://tools.cdc.gov/api/v2/resources/media/...",
  "cdc_outbreaks": "...",
  "kaiser_gh": "...",
  # etc
}
cache = {}
def refresh():
    for name, url in FEEDS.items():
        cache[name] = feedparser.parse(url).entries[:20]
def search(pathogen, location):
    hits = []
    for feed_name, entries in cache.items():
        for e in entries:
            blob = (e.title + " " + e.get("summary","")).lower()
            if pathogen.lower() in blob or location.lower() in blob:
                hits.append({"source": feed_name, "title": e.title, 
                             "link": e.link, "date": e.get("published")})
    return hits
```

You'd spend more time hunting down the exact feed URLs than writing this code. The Molloy page is actually useful for that — click through each sub-page (CDC Travel Notices, Kaiser Global Health, etc.) to find the canonical RSS URLs they're pulling from.
#### What to put in the writeup
Don't cite Molloy directly ("we used a library guide" sounds unserious). Instead, in your "Data Sources" section, list the individual primary sources — CDC NNDSS, CDC Travel Notices, Kaiser Global Health, etc. — and note that you cross-reference pasted reports against these live feeds to distinguish isolated findings from emerging signals. That framing sounds exactly like the "practitioner tool" the sponsor is asking for.
#### One risk to flag
These feeds skew toward **travel health and general public-health news**, not biosecurity specifically. They won't cover things like dual-use research concerns, synthesis-screening issues, or lab incidents — which are more the biosecurity sweet spot than outbreak surveillance. So this module should be framed as "ambient outbreak signal," not "biosecurity intelligence." For the biosecurity-specific policy context (BWC, Select Agents, IGSC), you still want the curated static corpus I described before.

**The curated corpus** of a few dozen items is what your _system_ queries during the pipeline's context-retrieval step. It's the tool's internal knowledge base — the thing that gets searched when a user pastes in a report about, say, a Nipah outbreak and the LLM needs to pull in "what do we know about past Nipah events and relevant policy."

**The scenario library** is what your _users_ (the judges, in practice) paste into the tool during the demo. It's input, not knowledge. Each scenario is a fake-but-realistic ProMED alert or news snippet, maybe 150–400 words, that you've tested and know produces a clean output card.

They overlap in content but are shaped oppositely:

||Corpus entry|Scenario entry|
|---|---|---|
|Audience|The LLM (machine-readable)|The judge (human-readable)|
|Format|Structured JSON fields|Prose, messy, realistic|
|Length|100–200 words per entry|150–400 words per scenario|
|Purpose|Be retrieved and cited|Trigger the pipeline|

**The strategic insight:** you can build the scenario library almost for free _from_ the corpus, as a byproduct. If your corpus has a clean Nipah-Kerala-2018 entry, writing a scenario that's "a fictional ProMED alert describing a Nipah cluster in South India in 2026" is 15 minutes of work — and you _know_ it'll retrieve well because you wrote the retrieval target yourself. So don't treat these as two separate jobs. Build the corpus first, then spin 5–8 scenarios off it Sunday morning.

One caveat: you want at least one or two scenarios that _don't_ have a close corpus match, to demonstrate the tool handles uncertainty gracefully (those become your "uncertainty flag" demo cases). So the scenarios aren't a strict subset — 6 of 8 should map cleanly to corpus entries, 2 should be deliberately off-distribution.
### Now: making the corpus build faster

Honestly, the "50–100 entries" number I gave you was a gut estimate. Let me revise it — **40–60 is plenty for a hackathon demo**, and past ~50 you hit diminishing returns fast. Nobody's going to query your tool about 80 different pathogens in a 10-minute judging session.

Here's how I'd structure the day to make it tractable:

**Hour 1: Lock the schema.** Before you write a single entry, draft the JSON schema and get buy-in from your LLM-pipeline teammate. They need to know what fields to expect. Something like:

```json
{
  "id": "nipah_kerala_2018",
  "type": "outbreak",  // or "policy" or "framework"
  "pathogen": {"name": "Nipah virus", "family": "Paramyxoviridae", "type": "virus"},
  "location": {"country": "India", "region": "Kerala"},
  "year": 2018,
  "case_count": 19,
  "deaths": 17,
  "cfr_percent": 89,
  "transmission": ["bat-to-human", "human-to-human (limited)"],
  "key_facts": "Short paragraph, 2-4 sentences...",
  "response_summary": "What WHO/authorities did, 2-3 sentences...",
  "lessons_learned": "What this teaches, 2-3 sentences...",
  "tags": ["zoonotic", "bsl-4", "high-cfr", "respiratory"],
  "sources": ["https://who.int/...", "https://..."]
}
```

Fix it now. Schema churn mid-day is what will actually kill you.

**Hours 2–3: Use Claude to scaffold, you to verify.** This is the single biggest time-saver. Don't write entries from scratch — paste the schema into Claude (or use the API directly) with a prompt like:

> "Generate a corpus entry for the 2018 Nipah virus outbreak in Kerala, India, following this exact JSON schema: [...]. Use only well-established facts. Include 2–3 authoritative source URLs (WHO, CDC, peer-reviewed). Mark any field you're uncertain about with a `_verify` suffix."

Then your job becomes _verification_ rather than _authorship_ — spot-check the case counts against WHO's DON page, confirm the sources exist, fix hallucinations. A verify-pass takes ~5 min per entry vs. 20+ min to write from scratch. For 50 entries that's the difference between 4 hours and 16 hours.

**Critical caveat on this:** LLMs hallucinate case counts, CFRs, and especially specific source URLs with real confidence. You _must_ verify the numbers and _must_ check that every cited URL actually resolves. The `_verify` suffix trick helps — tell Claude to self-flag uncertainty and it tends to flag the fields most likely to be wrong. But don't skip the verification pass. A corpus full of plausible-looking fabrications is worse than a smaller accurate one, and judges with domain knowledge will catch it.

**Hours 4–6: The prioritized build list.** Don't try to cover everything. Aim for coverage across these axes, not quantity:

- **~20 outbreak entries:** SARS-2003, MERS, H1N1-2009, Ebola-2014 (West Africa), Ebola-2018 (DRC), Zika-2015, mpox-2022, H5N1-various, Nipah-Kerala-2018, COVID-19, Marburg-various, Lassa, Rift Valley, plague-Madagascar-2017, cholera-Yemen, polio-vaccine-derived, measles-Samoa-2019, yellow fever-Angola-2016, avian flu in dairy cattle (US 2024), a couple of deliberately obscure ones. Mix of viral/bacterial, high-CFR/high-spread, zoonotic/respiratory/vector-borne.
- **~15 policy/framework entries:** BWC (what it is + key articles), Select Agent list (structure + examples), IHR 2005 (core capacities), IGSC synthesis screening guidance, Australia Group controls, CWC (briefly, for dual-use framing), US 2024 dual-use research policy, WHO R&D Blueprint priority pathogens list, CDC bioterrorism agent categories (A/B/C), Nagoya Protocol (pathogen sharing), PHEIC declaration process, Global Health Security Agenda, Coalition for Epidemic Preparedness Innovations mandate.
- **~10 "comparison anchors":** generic entries like "respiratory zoonotic spillover pattern," "vector-borne emergence in new geography," "lab-acquired infection incidents" — these are short conceptual entries that the LLM can retrieve when no specific historical match exists. These are actually the most valuable for handling novel scenarios and judges will notice if you have them.

That's 45 entries, which is plenty.

**Hour 7+ (if time):** Embedding precomputation. If you're doing vector search over the corpus, precompute embeddings once and save them to the JSON — don't recompute at query time. OpenAI's `text-embedding-3-small` is fine and cheap. Concatenate `pathogen.name + key_facts + lessons_learned + tags` as the embedding text.
### Three efficiency traps to avoid

**Don't hunt for perfect sources.** WHO Disease Outbreak News + CDC fact sheets + Wikipedia for framing is 90% of what you need. Don't go down rabbit holes finding peer-reviewed primary sources for case counts — WHO's summary figures are fine and accepted as canonical.
**Don't write prose-heavy entries.** The LLM will paraphrase whatever you give it anyway. Terse, factual, structured. Your `key_facts` field should read like a trading card, not an essay.
**Don't build a tagging taxonomy.** I listed example tags above but do not sit and design a controlled vocabulary. Use freeform tags, consistently-ish. If you end up with both `high-cfr` and `high_cfr` in your corpus, who cares — the LLM will match both.
### One concrete workflow suggestion
Split your day: corpus _authoring_ in the morning (hours 2–5, when your brain is fresh), _verification pass_ after lunch (hours 5–7, more mechanical), _embedding + integration with the retrieval code_ in the evening (hours 7–9, pair with your LLM-pipeline teammate so you're not throwing it over a wall). Then Sunday morning you derive the scenario library from the corpus in an hour — which is your Sunday warm-up before the demo polish phase.

----
— — Person C is actually the most under-appreciated role in a hackathon like this, and a good one to have tonight because your work is almost entirely browser + reading + writing. No dev environment needed.

Here's your evening, broken into three concrete tasks:

---
### 1. Gather your test cases (1–2 hrs) — the most critical thing

Your eval plan (from the README) is to run 10–15 real archived ProMED alerts through the tool and compare the predicted risk level to what actually happened. You need to collect those alerts _now_, before the tool even exists, so Person A can start running them Saturday morning.

Go to **ProMED-mail archive**: [https://promedmail.org/promed-posts/](https://promedmail.org/promed-posts/)

Search for these events — they're ideal because outcomes are well-documented and they span the full risk spectrum:

|Event|Expected risk level|Why it's useful|
|---|---|---|
|Nipah Bangladesh 2023|4-high|High CFR, limited h2h, known pathogen|
|HPAI H5N1 US dairy farms 2024|3-moderate|Novel spillover, uncertain h2h|
|Mpox DRC clade Ib 2024|4-high|Novel variant, international spread|
|Marburg Rwanda 2024|4-high|Healthcare worker cluster, high CFR|
|Oropouche Brazil 2024|3-moderate|Expanding range, novel vertical transmission|
|A routine salmonella cluster|1-minimal|Tests the low end of the scale|
For each one, find the _earliest_ ProMED alert (before the outcome was known) and save the raw text to a folder. That's the input. Then note what WHO eventually classified it as — that's your ground truth for the eval.

---
### 2. Read the hackathon judging criteria tonight

The Apart Research rubrics usually weight **novelty + safety relevance + feasibility**. Re-read the event page and write two paragraphs (just in a notes doc) answering:
- What gap does BioWatch Brief fill that existing tools (HealthMap, ProMED itself, WHO EBS) don't?
- Who is the specific practitioner using this at 2 am with limited time?

That framing becomes the first paragraph of your research report and the opening of your Sunday demo pitch. Getting this clear in your head tonight means you're not writing it bleary-eyed Sunday morning.

---
### 3. Draft the research report skeleton (30 min)

The report is usually a 2–4 page PDF or structured doc. Outline it now so there's no blank-page paralysis Sunday:

```
1. Problem statement  (~150 words — you can write this tonight)
2. Approach & architecture  (Person A/B fill this Saturday)
3. Evaluation methodology  (you write this tonight — the test case plan)
4. Results  (you fill numbers in Sunday morning after running evals)
5. Limitations & future work  (~100 words — easy to draft tonight)
6. Relevance to biosecurity  (~100 words — tie to the track's stated goals)
```

Sections 1, 3, 5, and 6 you can write _right now_ with what you already know. That's roughly half the report done before the hackathon even starts.

---
### One more thing — grab the WHO DONS feed URL

This is the data source for the optional RAG stretch goal. Bookmark it and confirm it loads: [https://www.who.int/emergencies/disease-outbreak-news/rss2.xml](https://www.who.int/emergencies/disease-outbreak-news/rss2.xml)

If Person A gets to the RAG step Saturday afternoon, they'll need a clean RSS URL to pull from. Having it ready saves 20 minutes of hunting.

---

Your deliverable for tonight is: **a folder with 10 raw ProMED alert texts, a ground-truth notes file, and a half-drafted report skeleton.** That's a Person C who shows up Saturday morning already ahead.