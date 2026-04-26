import json
import os
from dotenv import load_dotenv
from openai import AzureOpenAI
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Any

#set up API
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# load environment
load_dotenv()

# get Azure OpenAI configuration
api_key            = os.getenv("AZURE_OPENAI_KEY")
azure_endpoint     = os.getenv("AZURE_OPENAI_ENDPOINT")
azure_deployment   = os.getenv("AZURE_OPENAI_DEPLOYMENT")
azure_api_version  = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")

if not api_key:
    raise ValueError("AZURE_OPENAI_KEY not found. Check your .env file.")
if not azure_endpoint:
    raise ValueError("AZURE_OPENAI_ENDPOINT not found. Check your .env file.")
if not azure_deployment:
    raise ValueError("AZURE_OPENAI_DEPLOYMENT not found. Check your .env file.")

# set up AI client
client = AzureOpenAI(
    api_key        = api_key,
    azure_endpoint = azure_endpoint,
    api_version    = azure_api_version,
)

"""Class to enforce structure of output to UI"""
class BioWatchBrief(BaseModel):
    brief_title: Optional[str] = None
    summary: Optional[str] = None
    risk_level: Optional[int] = None
    risk_label: Optional[str] = None
    risk_rationale: List[Any] = []
    historical_comparisons: List[Any] = []
    policy_context: List[Any] = []
    live_signal_assessment: Optional[str] = None
    recommended_next_steps: List[Any] = []
    uncertainty_flags: List[Any] = []
    sources_used: List[Any] = []

"""Pydantic model for the request body.
    Contains the text of the report to be analyzed.
    Example request:
    {
        "report_text": "The patient is a 21-year-old male with fever, cough, 
        and shortness of breath. He is currently in a critical condition and 
        is in a critical care unit. He is currently in a critical condition and is in a critical care unit."
    }"""
class AnalyzeRequest(BaseModel):
    report_text: str

"""Function to clean JSON text.
    Removes leading and trailing markdown and code blocks."""
def clean_json_text(text: str) -> str:
    text = text.strip()

    if text.startswith("```json"):
        text = text.removeprefix("```json").strip()

    if text.startswith("```"):
        text = text.removeprefix("```").strip()

    if text.endswith("```"):
        text = text.removesuffix("```").strip()

    return text

def safe_parse(text):
    try:
        return json.loads(text)
    except Exception as e:
        print("PARSE ERROR (DATA REQUEST):", e)
        print("BAD OUTPUT (DATA REQUEST):", text)
        return {"error": "Invalid JSON from model"}

"""Load the corpus of reports.
    This is a list of dictionaries, each containing a "report" key with the text of the report.
    The corpus is loaded from a JSON file.
    """
with open("biowatch_corpus_fixed.json", "r") as f:
    corpus = json.load(f)

"""Function to get context from a report.
    Returns a structured Data request."""
def build_rag_request(client, report: str) -> dict:
    prompt = f"""
    You are an outbreak intelligence extraction assistant.

    Convert the following report into a structured retrieval request.

    Return ONLY valid JSON.

    Use standardized, clean entity names. 
    Do not include qualifiers like "suspected", "possible", or commentary in field values.
    Examples:
    - Use "Ebola virus", not "Ebolavirus"
    - Use "SARS-CoV-2", not "Betacoronavirus"
    - Use "mpox virus", not "orthopoxvirus", unless the specific virus is unknown.


    Transmission modes: keep to high-level categories such as:
    - "human-to-human"
    - "zoonotic"
    - "respiratory"
    - "vector-borne"

    Do not include descriptive sentences. Include all applicable transmission categories
    if they can be reasonably inferred. For known pathogens, include known transmission modes
    if not explicitly stated.

    Tags: short and normal keywords (1-3 words) and should not duplicate pathogen
    or location fields.

    Schema:
    {{
      "pathogen_name": null,
      "pathogen_family": null,
      "pathogen_type": null,
      "location": {{"country": null, "region": null}},
      "transmission_modes": [],
      "tags": [],
      "context_snippet": null
    }}

    Report:
    \"\"\"{report}\"\"\"
    """

    response = client.responses.create(
        model=azure_deployment,
        input=prompt,
        max_output_tokens=2000
    )

    #clean the response
    clean = clean_json_text(response.output_text)

    return safe_parse(clean)

"""Function to score a report entry against a structured Data request.
    Specifically for historical comparisons, returns a score based on relevance, confidence, and specificity.
    Scores are calculated based on the following criteria:
    - Pathogen name: 5 points if the pathogen name matches the request exactly
    - Location: 3 points if the location matches the request exactly
    - Transmission modes: 2 points for each matching transmission mode
    - Tags: 1 point for each matching tag"""
def score_outbreak(entry: dict, rag_request: dict) -> int:
    score = 0

    pathogen = rag_request.get("pathogen_name")
    location = rag_request.get("location", {})
    country = location.get("country")
    region = location.get("region")
    transmission_modes = rag_request.get("transmission_modes") or []
    tags = rag_request.get("tags") or []

    """score is a 5 because this is our pathogen"""
    if pathogen and pathogen.lower() == str(entry.get("pathogen_name", "")).lower():
        score += 5

    """score is a 3 because this is our location, but could or could not be relevant"""
    if country and country.lower() == str(entry.get("location", "")).lower():
        score += 3

    """score is a 2 because this is our general region, less specific than the country,
    but could or could not be relevant
    using "in" vs == because regions are less specific than countries"""
    if region and region.lower() in str(entry.get("location", "")).lower():
        score += 2

    """score transmission modes by iterating through
    score is a 2 because this is a known transmission mode, gives us an indication, but not a strong one"""
    entry_modes = [m.lower() for m in entry.get("transmission_modes") or []]

    for mode in transmission_modes:
        if mode.lower() in entry_modes:
            score += 2

    """score tags by iterating through
    score is a 1 because tags help us to refine our ranking, but not over the other criteria"""
    entry_tags = [t.lower() for t in entry.get("tags") or []]

    for tag in tags:
        if tag.lower() in entry_tags:
            score += 1

    return score

"""Function to score a report entry against a structured Data request.
    Specifically for policy guidance, returns a score based on number of terms that appear in the report.
    Scores are calculated based on relevance, confidence, and specificity."""
def score_policy(entry: dict, rag_request: dict) -> int:
    score = 0

    tags = rag_request.get("tags") or []
    transmission_modes = rag_request.get("transmission_modes") or []

    search_text = " ".join([
        str(entry.get("title") or ""),
        str(entry.get("context_snippet") or ""),
        str(entry.get("key_facts") or ""),
        str(entry.get("response_summary") or ""),
        str(entry.get("lessons_learned") or ""),
    ]).lower()

    for tag in tags:
        if tag.lower() in search_text:
            score += 2

    for mode in transmission_modes:
        if mode.lower() in search_text:
            score += 1

    response_terms = [
        "contact tracing",
        "isolation",
        "quarantine",
        "containment",
        "reporting",
        "laboratory confirmation"
    ]

    for term in response_terms:
        if term in search_text:
            score += 1

    return score

"""function to format a report entry into a dictionary for retrieval.
    Returns a dictionary with the following keys:
    - title: the title of the entry
    - summary: a short summary of the entry
    - relevance: a description of how the entry matches the request
    - source: a list of URLs where the entry was found
    - score: the score of the entry"""
def format_result(entry: dict, score: int) -> dict:

    return {
        "title": entry.get("title") or entry.get("pathogen_name", "untitled entry"),
        "summary": entry.get("context_snippet") or entry.get("summary", "No summary available."),
        "relevance": "Matched based on pathogen, location, transmission modes, and tags.",
        "source": entry.get("sources", []),
        "score": score
    }

"""function to retrieve context from a structured data request.
    Returns a dictionary of retrieved context."""
def retrieve_context(rag_request: dict) -> dict:

    #get relevent entries in corpus
    scored_outbreaks = []
    scored_policy = []

    #score required to be relevant
    outbreak_threshold = 3
    policy_threshold = 2

    for entry in corpus:

        if entry.get("type") == "outbreak":
            score = score_outbreak(entry, rag_request)
            scored_outbreaks.append({"entry": entry, "score": score})
        elif entry.get("type") in ["policy", "framework"]:
            score = score_policy(entry, rag_request)
            scored_policy.append({"entry": entry, "score": score})
        else:
            continue

    #sorts the entries
    scored_outbreaks.sort(key=lambda x: x["score"], reverse=True)
    scored_policy.sort(key=lambda x: x["score"], reverse=True)

    # lists for two categories
    historical = []
    policy = []

    for item in scored_outbreaks:
        entry = item["entry"]
        score = item["score"]
        if(score > outbreak_threshold):
            historical.append(format_result(entry, score))

        if(len(historical) > 2):
            break

    for item in scored_policy:
        entry = item["entry"]
        score = item["score"]

        if(score > policy_threshold):
            policy.append(format_result(entry, score))

        if(len(policy) > 1):
            break

    if not historical:
        historical = [{
            "title": "No Historical Comparisons available.",
            "summary": "No relevant historical outbreaks were found that match the request.",
            "relevance": "No sufficiently relevant historical outbreaks were found.",
            "source": [],
            "score": 0
        }]

    if not policy:
        policy = [{
            "title": "No Policy Guidance available.",
            "summary": "No relevant policy guidance was found that matches the request.",
            "relevance": "No sufficiently relevant policy guidance was found.",
            "source": [],
            "score": 0
        }]

    return {"historical_comparisons": historical, "policy_context": policy}

"""function to analyze a report and structured Data request.
    Returns a dictionary of analysis results."""
def analyze_report(client, report: str, rag_request: dict, retrieved_context:dict) -> dict:
    analysis_prompt = f"""
    You are an outbreak intelligence analysis assistant.
    
    Use the original report, structured extraction, and retrieved context to produce a rapid risk assessment.
    
    Follow these rules:
    - Do not fabricate missing data
    - Use only provided context and report
    - Flag uncertainty explicitly
    - Keep outputs concise and actionable
    - Use a 1–5 risk scale:
        1 = minimal
        2 = low
        3 = moderate
        4 = high
        5 = critical
    

    Return ONLY valid JSON.
    Do not include markdown or explanations outside JSON.
    
    Schema:
    {{
        "brief_title": null,
        "summary": null,
        "risk_level": null,
        "risk_label": null,
        "risk_rationale": [],
        "historical_comparisons": [],
        "policy_context": [],
        "live_signal_assessment": null,
        "recommended_next_steps": [],
        "uncertainty_flags": [],
        "sources_used": []
    }}

    Report:
    \"\"\"{report}\"\"\"
    
    Structured Extraction:
    \"\"\"{json.dumps(rag_request, indent=2)}\"\"\"
    
    Data Results:
    Retrieved context will contain:
    - historical_comparisons: prior outbreak/event examples
    - policy_context: public health guidance, reporting frameworks, or response guidance
    - Preserve all retrieved_context historical_comparisons and policy_context entries in the final output.
    - If retrieved context contains a placeholder entry such as "No Policy Documents Applicable" or 
    "No Historical Comparisons Available", include that placeholder unchanged in the corresponding 
    output field.
    \"\"\"{json.dumps(retrieved_context, indent=2)}\"\"\"
    """

    result = client.responses.create(
        model=azure_deployment,
        max_output_tokens=2000,
        input=analysis_prompt
    )

    return safe_parse(result.output_text)



"""API endpoint to analyze a report.
    Returns a dictionary of analysis results.
    Example request:
    {
        "report_text": "The patient is a 21-year-old male with fever, cough, 
        and shortness of breath. He is currently in a critical condition and 
        is in a critical care unit. He is currently in a critical condition and is in a critical care unit."
    }"""
@app.post("/analyze_report", response_model=BioWatchBrief)
def analyze(request: dict) -> dict:
    report = request.get("report_text")

    if not report or not report.strip():
        raise HTTPException(status_code=400, detail="No report provided.")

    try:
        return run_pipeline(report)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="Model returned invalid JSON")
    except Exception as e:
        print("Pipeline error:", repr(e))
        raise HTTPException(status_code=500, detail="Pipeline failure.")

    #return run_pipeline(report)


"""Main function to run the entire pipeline.
    Returns a dictionary of analysis results."""
def run_pipeline(report: str) -> dict:

    rag_request = build_rag_request(client, report)

    retrieved_context = retrieve_context(rag_request)

    print("RETRIEVED CONTEXT:")
    print(json.dumps(retrieved_context, indent=2))

    analysis = analyze_report(client, report, rag_request, retrieved_context)

    return analysis
