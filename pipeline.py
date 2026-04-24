"""
BioWatch Brief — core pipeline
Paste an incident report (article, ProMED alert, lab note, or raw text) and
receive a structured rapid-assessment card.

Usage:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-...
    python pipeline.py
"""

import json
import anthropic

# ─── JSON schema (passed as a tool so Claude returns structured output) ────────

ASSESSMENT_TOOL = {
    "name": "submit_risk_assessment",
    "description": (
        "Submit a completed biosecurity risk assessment card. "
        "Call this exactly once after analysing the incident report."
    ),
    "input_schema": {
        "type": "object",
        "required": [
            "risk_level",
            "risk_rationale",
            "pathogen_summary",
            "transmission",
            "affected_populations",
            "geographic_scope",
            "regulatory_context",
            "recommended_actions",
            "uncertainty_flags",
            "sources_referenced",
        ],
        "properties": {
            # ── Tier 1: headline ────────────────────────────────────────────
            "risk_level": {
                "type": "string",
                "enum": ["1-minimal", "2-low", "3-moderate", "4-high", "5-critical"],
                "description": (
                    "Overall risk to public health or biosecurity. "
                    "1 = isolated, no spread potential; "
                    "5 = credible pandemic or CBRN threat."
                ),
            },
            "risk_rationale": {
                "type": "string",
                "description": (
                    "One or two sentences explaining the risk_level assignment. "
                    "Cite the single most important factor."
                ),
            },

            # ── Tier 2: pathogen profile ────────────────────────────────────
            "pathogen_summary": {
                "type": "object",
                "required": ["name", "type", "known_or_novel", "key_characteristics"],
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Best available name (ICTV-preferred if viral).",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["virus", "bacterium", "fungus", "prion", "toxin", "unknown", "not_biological"],
                    },
                    "known_or_novel": {
                        "type": "string",
                        "enum": ["well-characterised", "known-variant", "novel", "unknown"],
                    },
                    "key_characteristics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Up to 4 bullet points: R0 or attack rate, case fatality rate, "
                            "incubation period, notable features (e.g. aerosolisation, "
                            "environmental stability, antibiotic resistance)."
                        ),
                        "maxItems": 4,
                    },
                },
            },
            "transmission": {
                "type": "object",
                "required": ["routes", "human_to_human"],
                "properties": {
                    "routes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "e.g. ['respiratory droplet', 'fomite', 'vector-borne']",
                    },
                    "human_to_human": {
                        "type": "string",
                        "enum": ["confirmed", "suspected", "not-observed", "unknown"],
                    },
                },
            },

            # ── Tier 3: situational context ─────────────────────────────────
            "affected_populations": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Groups at elevated risk: immunocompromised, elderly, occupational "
                    "exposure, specific livestock species, etc."
                ),
                "maxItems": 5,
            },
            "geographic_scope": {
                "type": "object",
                "required": ["current_locations", "spread_trajectory"],
                "properties": {
                    "current_locations": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Countries or regions with confirmed cases/incidents.",
                    },
                    "spread_trajectory": {
                        "type": "string",
                        "enum": ["contained", "localised-spread", "regional-spread", "international-spread", "unknown"],
                    },
                },
            },
            "regulatory_context": {
                "type": "object",
                "required": ["select_agent_status", "ihr_notification", "relevant_frameworks"],
                "properties": {
                    "select_agent_status": {
                        "type": "string",
                        "enum": ["Tier-1", "Select-Agent", "Not-listed", "Unknown"],
                        "description": "US CDC/USDA Select Agent Program classification if applicable.",
                    },
                    "ihr_notification": {
                        "type": "string",
                        "enum": ["required", "consider-notifying", "not-required", "unknown"],
                        "description": "Whether this event may trigger IHR (2005) Article 6 notification.",
                    },
                    "relevant_frameworks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "e.g. ['WHO IHR 2005', 'US BSAT regulations', "
                            "'EU Directive 2000/54/EC', 'Australia SSBA Regulations']"
                        ),
                        "maxItems": 4,
                    },
                },
            },

            # ── Tier 4: actionable outputs ──────────────────────────────────
            "recommended_actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["priority", "action", "actor"],
                    "properties": {
                        "priority": {
                            "type": "string",
                            "enum": ["immediate", "24-48h", "this-week"],
                        },
                        "action": {
                            "type": "string",
                            "description": "Concrete, imperative action sentence.",
                        },
                        "actor": {
                            "type": "string",
                            "description": "Who should act: e.g. 'Lab director', 'Public health authority', 'Clinician'.",
                        },
                    },
                },
                "description": "Up to 5 prioritised recommendations, most urgent first.",
                "maxItems": 5,
            },

            # ── Tier 5: epistemic quality ───────────────────────────────────
            "uncertainty_flags": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["field", "flag", "note"],
                    "properties": {
                        "field": {
                            "type": "string",
                            "description": "Which field above this flag applies to.",
                        },
                        "flag": {
                            "type": "string",
                            "enum": [
                                "insufficient-source-data",
                                "single-unverified-source",
                                "conflicting-reports",
                                "model-knowledge-cutoff",
                                "requires-lab-confirmation",
                                "translation-uncertainty",
                            ],
                        },
                        "note": {
                            "type": "string",
                            "description": "Brief explanation of the uncertainty.",
                        },
                    },
                },
                "description": "Flags for fields where confidence is low.",
            },
            "sources_referenced": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Any sources named or implied in the input text "
                    "(ProMED post ID, WHO DONS URL, paper DOI, etc.). "
                    "Do not fabricate sources not present in the input."
                ),
                "maxItems": 6,
            },
        },
    },
}


# ─── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are BioWatch Brief, a rapid biosecurity risk assessment tool used by \
public health practitioners, biosecurity analysts, and first responders.

Your task is to read an incident report (which may be a ProMED alert, a WHO Disease Outbreak \
News item, a news article, a lab note, or raw field intelligence) and produce a structured \
risk assessment card by calling the submit_risk_assessment tool.

## Assessment standards

RISK LEVEL — follow this rubric strictly:
  1-minimal   : Isolated case(s), well-understood pathogen, no spread potential, no novel features
  2-low       : Limited cluster, known pathogen, contained setting, standard PPE adequate
  3-moderate  : Unexplained cluster OR novel variant OR community transmission in one region
  4-high      : Multi-region spread OR significant CFR OR credible weaponisation context
  5-critical  : Pandemic trajectory, CBRN-capable pathogen, or credible mass-casualty threat

PATHOGEN IDENTIFICATION — prefer ICTV-accepted names for viruses. If genus/family is known but \
species uncertain, say so. If the agent is not yet characterised, set known_or_novel to "novel" \
or "unknown" and flag it in uncertainty_flags.

REGULATORY CONTEXT — apply only the frameworks that are plausibly relevant given the incident's \
geography and pathogen type. Do not pad with inapplicable frameworks.

RECOMMENDED ACTIONS — be concrete and imperative. "Consider enhanced surveillance" is vague. \
"Notify the state epidemiologist and submit environmental samples to the CDC within 24 hours" \
is actionable. Tailor actor to whoever is most likely reading this report.

UNCERTAINTY FLAGS — intellectual honesty is a first-class output. Flag any field where the source \
data is thin, contradictory, or outside your training knowledge. A well-flagged moderate-confidence \
assessment is more useful than an overconfident one.

SCOPE — you are providing an initial rapid assessment, not a definitive diagnosis or legal \
determination. Note this implicitly through uncertainty_flags where relevant.

## What you must NOT do
- Do not fabricate case counts, dates, or locations not mentioned in the input.
- Do not recommend specific pharmaceutical treatments or dosing.
- Do not identify or speculate about the identity of individuals in the report.
- Do not provide synthesis routes, enhancement techniques, or any dual-use technical detail.

Call submit_risk_assessment exactly once. Do not produce any other text output."""


# ─── Pipeline function ─────────────────────────────────────────────────────────

def assess(report_text: str) -> dict:
    """
    Run a report through the BioWatch Brief pipeline.
    Returns the parsed assessment dict, or raises on failure.
    """
    client = anthropic.Anthropic()

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        tools=[ASSESSMENT_TOOL],
        tool_choice={"type": "tool", "name": "submit_risk_assessment"},
        messages=[
            {
                "role": "user",
                "content": f"<incident_report>\n{report_text.strip()}\n</incident_report>",
            }
        ],
    )

    # Extract the tool_use block
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_risk_assessment":
            return block.input

    raise ValueError("Model did not call submit_risk_assessment — check tool_choice config.")


# ─── Quick smoke test ──────────────────────────────────────────────────────────

SAMPLE_REPORT = """
ProMED-mail Archive Number 20240315.8712341
Published Date: 2024-03-15
Subject: UNDIAGNOSED FEBRILE ILLNESS, SEVERE - CAMEROON (NORTHWEST): ALERT

A cluster of 14 cases of severe febrile illness with haemorrhagic features has been reported
in Bamenda, Northwest Region, Cameroon over the past 10 days. Six patients have died (CFR 43%).
Most cases are healthcare workers at the regional referral hospital. Symptoms include sudden-onset
high fever, myalgia, and bleeding from mucous membranes appearing 4-6 days after onset.
Samples have been sent to the Institut Pasteur in Yaounde; results are pending.
No travel history to known Ebola-affected areas has been documented. Local authorities have
initiated contact tracing. WHO has been notified informally; a formal IHR notification is
under consideration.
"""

if __name__ == "__main__":
    print("Running BioWatch Brief on sample report...\n")
    result = assess(SAMPLE_REPORT)
    print(json.dumps(result, indent=2))
