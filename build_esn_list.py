#!/usr/bin/env python3
"""
build_esn_list.py
Pipeline: SIRENE (entreprise.data.gouv.fr) -> enrichissement site -> HTML scan -> scoring -> export CSV

Notes:
- Public endpoints: https://entreprise.data.gouv.fr/api/sirene/v3
- Respect rate limits. For large runs, add exponential backoff and use a job queue.
- CLI flags let you cap pages for quick tests.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
import tldextract
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv
import os
import sys

# ---------------- Defaults (can be overridden by CLI) ----------------
DEFAULT_OUTFILE = "esn_candidates.csv"
DEFAULT_PER_PAGE = 100
DEFAULT_MAX_PAGES = 5  # safe default for a smoke test
DEFAULT_SLEEP = 0.6
# Default collection NAF codes (user-targeted)
DEFAULT_NAF_CODES = ["62.02A", "71.12B"]
DEFAULT_MIN_EMP = 10
DEFAULT_MAX_EMP = 500
DEFAULT_EXCLUDE_OVER_EMP = 2000  # hard exclusion threshold on very large companies

# Target NAF prefixes for pertinence scoring (refined)
NAF_CODES_TARGET = ["71.12", "62.02", "70.22", "78"]

# Keywords (French)
NAME_KEYWORDS = [
    "esn", "ssii", "société de service", "bureau d'études", "ingenierie", "ingénierie",
    "conseil", "consulting", "staffing", "placement", "staff augmentation", "intérim",
    "recrutement"
]
SITE_KEYWORDS = [
    "consultant", "consultants", "mission", "missions", "recrutement",
    "ingénieur d'affaires", "ingenieur d'affaires", "business developer", "account manager",
    "commercial sédentaire", "placement", "staffing", "consulting", "bureau d'études",
    "solutions engineering", "staff augmentation", "assistance technique"
]

SCORE_RULES = {
    "naf": 3,
    "name_keyword": 2,
    "site_keyword": 3,
    "job_posting": 4,
    "size": 2,
}

# Candidate site paths to probe lightly
CANDIDATE_PATHS = [
    "/services", "/service", "/recrutement", "/carriere", "/carrieres", "/careers",
    "/jobs", "/offres", "/offres-demploi", "/offre", "/join-us"
]

# Shared HTTP session
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "ESN-Discovery/1.0 (+https://example.com)"
})

# Load environment variables (for INSEE OAuth)
load_dotenv()

# Allow overriding via env
INSEE_TOKEN_URL = os.getenv("SIRENE_TOKEN_URL", "https://api.insee.fr/token")
# Per your note, use the 3.11 API base by default; can be overridden via env
INSEE_SIRENE_BASE = os.getenv("SIRENE_API_BASE", "https://api.insee.fr/api-sirene/3.11")
INSEE_API_KEY = os.getenv("SIRENE_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")


# ---------------- Utilities ----------------

def call_api(url: str, params: Optional[dict] = None, max_tries: int = 3, sleep: float = DEFAULT_SLEEP) -> Optional[dict]:
    for i in range(max_tries):
        try:
            r = SESSION.get(url, params=params, timeout=20)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 503):
                time.sleep(2 + i * 2)
                continue
            return None
        except Exception:
            time.sleep(1 + i)
    return None

def naf_search_terms(code: str) -> List[str]:
    """
    Build a small list of NAF query terms to try.
    If code looks like a full code with letter (e.g., 62.02A), try exact first, then with wildcard.
    Else, use prefix with wildcard.
    """
    c = str(code).strip()
    terms: List[str] = []
    # full code pattern like NN.NNX (with trailing letter)
    if re.match(r"^\d{2}\.\d{2}[A-Z]$", c, re.IGNORECASE):
        terms.append(c)
        terms.append(c + "*")
    else:
        # prefix
        if c.endswith("*"):
            terms.append(c)
        else:
            terms.append(c + "*")
    return terms

def indicates_zero_employees(tranche: Optional[str]) -> bool:
    """Return True if the tranche/effectif string clearly indicates 0 employees.
    Handles INSEE code '00' and textual variants like '0', '0-0', '0 salarié'.
    """
    if tranche is None:
        return False
    s = str(tranche).strip()
    if not s:
        return False
    up = s.upper()
    if up in {"00"}:
        return True
    low = s.lower()
    if low in {"0", "0-0"}:
        return True
    if "0 salari" in low:  # salarié / salaries
        return True
    # If all numeric mentions are 0, treat as zero employees
    nums = [int(n) for n in re.findall(r"\d+", low)]
    return bool(nums) and max(nums) == 0

# Approximate SIRENE tranche codes to upper bounds
TRANCHE_CODE_UPPER = {
    "00": 0,
    "01": 2,
    "02": 5,
    "03": 9,
    "11": 19,
    "12": 49,
    "21": 99,
    "22": 199,
    "31": 249,
    "32": 499,
    "41": 999,
    "42": 1999,
    "51": 4999,
    "52": 9999,
    "53": 1000000,  # open-ended 10000+
}

def tranche_above_threshold(tranche: Optional[str], threshold: int) -> bool:
    if tranche is None:
        return False
    code = str(tranche).strip().upper()
    # Accept numeric code mapping first
    if code in TRANCHE_CODE_UPPER:
        return TRANCHE_CODE_UPPER[code] > threshold
    # Fallback: parse any numbers
    nums = [int(n) for n in re.findall(r"\d+", code)]
    return bool(nums) and max(nums) > threshold

def allowed_tranche_codes(max_emp: int) -> List[str]:
    """Return list of tranche codes whose upper bound <= max_emp.
    Include 'NN' (unknown) to keep uncertain cases.
    """
    allowed = [code for code, ub in TRANCHE_CODE_UPPER.items() if ub <= max_emp]
    # Keep deterministic ordering roughly ascending by upper bound
    allowed_sorted = sorted(allowed, key=lambda c: TRANCHE_CODE_UPPER[c])
    # Include 'NN' (non renseigné) when API uses it
    allowed_sorted.append('NN')
    return allowed_sorted

def fetch_establishments_by_naf_prefix_recherche(
    naf_code: str,
    per_page: int,
    max_pages: int,
    sleep: float,
    etat_administratif: str = "A",
    minimal: bool = True,
    include: str = "siege",
    exclude_over_emp: Optional[int] = None,
) -> List[dict]:
    """
    Fetch enterprises from Recherche d'entreprises API by exact NAF code at UL level.
    Endpoint: https://recherche-entreprises.api.gouv.fr/search
    Params of interest: activite_principale, etat_administratif, page, per_page (<=25), minimal/include
    """
    base = "https://recherche-entreprises.api.gouv.fr/search"
    results: List[dict] = []
    page_size = max(1, min(per_page, 25))
    for page in range(1, max_pages + 1):
        params = {
            "activite_principale": naf_code,
            "etat_administratif": etat_administratif,
            "page": page,
            "per_page": page_size,
            "minimal": str(minimal).lower(),
            "include": include if minimal else None,
        }
        if exclude_over_emp is not None and exclude_over_emp >= 0:
            codes = allowed_tranche_codes(exclude_over_emp)
            if codes:
                params["tranche_effectif_salarie"] = ",".join(codes)
        # Remove include if None to avoid sending 'include=None'
        if params["include"] is None:
            params.pop("include")
        j = call_api(base, params=params, sleep=sleep)
        if not j or "results" not in j:
            break
        batch = j.get("results", [])
        if not batch:
            break
        # Normalize to our internal structure
        for r in batch:
            ul_naf = r.get("activite_principale")
            siege = r.get("siege") or {}
            etab_naf = siege.get("activite_principale")
            tranche = r.get("tranche_effectif_salarie") or siege.get("tranche_effectif_salarie")
            normalized = {
                "siren": r.get("siren"),
                "unite_legale": {"denomination": r.get("nom_raison_sociale") or r.get("nom_complet")},
                "activite_principale": ul_naf or etab_naf,
                "tranche_effectif_salarie": tranche,
                "est_siege": True,
                "nom_raison_sociale": r.get("nom_raison_sociale") or r.get("nom_complet"),
                "nom_complet_annuaire": r.get("nom_complet"),
            }
            results.append(normalized)
        total = j.get("total_results")
        if total and page * page_size >= int(total):
            break
        time.sleep(sleep)
    return results

def normalize_string(s: Optional[str]) -> str:
    if not s:
        return ""
    s = s.strip().lower()
    # minimal accent folding
    s = (
        s.replace("é", "e").replace("è", "e").replace("ê", "e").replace("ë", "e")
         .replace("à", "a").replace("â", "a")
         .replace("î", "i").replace("ï", "i")
         .replace("ô", "o").replace("ö", "o")
         .replace("ù", "u").replace("û", "u")
    )
    s = re.sub(r"\s+", " ", s)
    return s

def guess_domain_from_name(name: str) -> List[str]:
    base = normalize_string(name)
    base = re.sub(r"[^a-z0-9\- ]", "", base)
    parts = [p for p in base.split() if len(p) > 1]
    if not parts:
        return []
    candidates = [
        "".join(parts) + ".fr",
        "".join(parts) + ".com",
        parts[0] + "".join(parts[1:]) + ".fr",
        "".join(parts[:2]) + ".fr",
        "-".join(parts) + ".fr",
        "-".join(parts) + ".com",
    ]
    # unique while preserving order
    seen = set()
    uniq: List[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq

def extract_domain_from_url(url: str) -> Optional[str]:
    try:
        return urlparse(url).netloc
    except Exception:
        return None

def ensure_http(url: str) -> str:
    if not url.startswith("http://") and not url.startswith("https://"):
        return "http://" + url
    return url

def http_get_html(url: str, timeout: int = 15) -> Optional[str]:
    try:
        r = SESSION.get(url, timeout=timeout, allow_redirects=True)
        if r.status_code == 200 and "text/html" in r.headers.get("Content-Type", ""):
            return r.text
    except Exception:
        return None
    return None

def find_keywords_in_text(text: str, keyword_list: List[str]) -> List[str]:
    text_norm = normalize_string(text)
    found = []
    for k in keyword_list:
        if normalize_string(k) in text_norm:
            found.append(k)
    return found


def serpapi_find_domain(
    query: str,
    api_key: str,
    engine: str = "google",
    num: int = 5,
    hl: str = "fr",
    gl: str = "fr",
) -> Optional[str]:
    """
    Query SerpAPI for the company and try to infer the official domain from organic results.
    Preference: .fr domains and domains whose tokens match the company name; skip social/aggregator sites.
    """
    try:
        resp = SESSION.get(
            "https://serpapi.com/search.json",
            params={
                "engine": engine,
                "q": query,
                "num": num,
                "hl": hl,
                "gl": gl,
                "api_key": api_key,
            },
            timeout=20,
        )
        if resp.status_code != 200:
            return None
        data = resp.json() or {}
        results = data.get("organic_results") or []
        if not isinstance(results, list):
            return None
        bad_hosts = {
            "linkedin.com", "fr.linkedin.com", "facebook.com", "twitter.com", "x.com",
            "societe.com", "societeinfo.com", "verif.com", "manageo.fr", "bloomberg.com",
            "wikipedia.org", "lefigaro.fr", "lemonde.fr", "indeed.fr", "welcometothejungle.com"
        }
        qnorm = normalize_string(query)
        qtokens = {t for t in re.findall(r"[a-z0-9]+", qnorm) if len(t) > 2}
        candidates: List[Tuple[int, str]] = []
        for r in results:
            link = r.get("link") or r.get("url")
            if not link:
                continue
            host = extract_domain_from_url(link)
            if not host:
                continue
            host_l = host.lower()
            if any(host_l.endswith(bad) or host_l == bad for bad in bad_hosts):
                continue
            # score the host by TLD and name overlap
            score = 0
            if host_l.endswith(".fr"):
                score += 2
            # tokens overlap
            tokens = set(re.findall(r"[a-z0-9]+", host_l))
            overlap = len(qtokens & tokens)
            score += min(overlap, 3)
            candidates.append((score, host))
        if not candidates:
            return None
        candidates.sort(reverse=True)
        return candidates[0][1]
    except Exception:
        return None

def serper_find_domain(
    query: str,
    api_key: str,
    num: int = 5,
    hl: str = "fr",
    gl: str = "fr",
) -> Optional[str]:
    """
    Query serper.dev for the company and infer the official domain from organic results.
    Endpoint: POST https://google.serper.dev/search with JSON body.
    """
    try:
        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
        }
        payload = {"q": query, "num": num, "hl": hl, "gl": gl}
        resp = SESSION.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code != 200:
            return None
        data = resp.json() or {}
        results = data.get("organic") or []
        if not isinstance(results, list):
            return None
        # Take the first acceptable organic result to maximize chances,
        # while skipping obvious social/aggregator domains.
        bad_hosts = {
            "linkedin.com", "fr.linkedin.com", "facebook.com", "twitter.com", "x.com",
            "societe.com", "societeinfo.com", "verif.com", "manageo.fr", "bloomberg.com",
            "wikipedia.org", "indeed.fr", "welcometothejungle.com"
        }
        for r in results:
            link = r.get("link") or r.get("url")
            if not link:
                continue
            host = extract_domain_from_url(link)
            if not host:
                continue
            host_l = host.lower()
            if any(host_l.endswith(bad) or host_l == bad for bad in bad_hosts):
                continue
            return host
        return None
    except Exception:
        return None


# ---------------- API interactions ----------------

def fetch_establishments_by_naf_prefix(
    naf_prefix: str,
    per_page: int,
    max_pages: int,
    sleep: float,
) -> List[dict]:
    """
    entreprise.data.gouv.fr SIRENE V3, établissements search.
    We use q=activite_principale:<prefix>* to match NAF codes by prefix.
    Docs: https://entreprise.data.gouv.fr/api_doc/sirene
    """
    base = "https://entreprise.data.gouv.fr/api/sirene/v3/etablissements"
    results: List[dict] = []
    terms = naf_search_terms(naf_prefix)
    for page in range(1, max_pages + 1):
        got_any = False
        for term in terms:
            q = f"activite_principale:{term}"
            params = {"q": q, "per_page": per_page, "page": page}
            j = call_api(base, params=params, sleep=sleep)
            if not j or "etablissements" not in j:
                continue
            batch = j.get("etablissements", [])
            if not batch:
                continue
            results.extend(batch)
            got_any = True
            total = j.get("total_results")
            # We cannot combine pages across terms reliably; break on first successful term per page
            break
        if not got_any:
            break
        time.sleep(sleep)
    return results


def fetch_establishments_by_naf_prefix_fallback_recherche(
    naf_prefix: str,
    per_page: int,
    max_pages: int,
    sleep: float,
) -> List[dict]:
    """
    Fallback using recherche-entreprises.api.gouv.fr, which often works even if
    entreprise.data.gouv.fr has connectivity hiccups. This API supports "naf" filtering.
    Docs: https://recherche-entreprises.api.gouv.fr/
    """
    base = "https://recherche-entreprises.api.gouv.fr/search"
    results: List[dict] = []
    for page in range(1, max_pages + 1):
        params = {
            # This API currently requires either a 3+ char q or some strict filters.
            # Use a neutral query to enable results, then locally filter by NAF prefix.
            "q": "informatique",
            "page": page,
            "per_page": per_page,
        }
        j = call_api(base, params=params, sleep=sleep)
        if not j:
            break
        batch = j.get("results", [])
        if not batch:
            break
        # Normalize fields to look like SIRENE etablissements enough for our processing
        for r in batch:
            naf = r.get("activite_principale") or ""
            # For fallback, accept exact or prefix match
            if str(naf).startswith(naf_prefix):
                normalized = {
                    "siren": r.get("siren"),
                    "unite_legale": {"denomination": r.get("nom_complet")},
                    "activite_principale": naf,
                    "tranche_effectif_salarie": r.get("tranche_effectif_salarie"),
                    "est_siege": r.get("est_siege"),
                    "nom_raison_sociale": r.get("nom_complet"),
                    "nom_complet_annuaire": r.get("nom_complet"),
                }
                results.append(normalized)
        total = j.get("total_results") or j.get("total")
        if total and page * per_page >= int(total):
            break
        time.sleep(sleep)
    return results


def get_insee_access_token(client_id: str, client_secret: str, token_url: str) -> Optional[str]:
    try:
        r = SESSION.post(
            token_url,
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            headers={"Accept": "application/json"},
            timeout=20,
        )
        if r.status_code == 200:
            return r.json().get("access_token")
        else:
            print(f"   INSEE token error: HTTP {r.status_code}")
            try:
                print("   Response:", r.json())
            except Exception:
                pass
            return None
    except Exception as ex:
        print("   INSEE token exception:", ex)
        return None


def fetch_establishments_by_naf_prefix_insee(
    naf_prefix: str,
    per_page: int,
    max_pages: int,
    sleep: float,
    token: str,
    base_url: str,
) -> List[dict]:
    """
    Use INSEE SIRENE V3 API (OAuth2) to retrieve establishments by NAF prefix.
    Endpoint: /siret?q=activitePrincipale:{prefix}*&nombre={per_page}&debut={offset}
    """
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    results: List[dict] = []
    field_options = ["activitePrincipaleUniteLegale", "activitePrincipaleEtablissement"]
    for page in range(1, max_pages + 1):
        success_this_page = False
        for field in field_options:
            # Try exact then wildcard for the provided naf_prefix
            for term in naf_search_terms(naf_prefix):
                offset = (page - 1) * per_page
                params = {
                    "q": f"{field}:{term}",
                    "nombre": per_page,
                    "debut": offset,
                }
                url = f"{base_url}/siret"
                try:
                    r = SESSION.get(url, headers=headers, params=params, timeout=25)
                    if r.status_code != 200:
                        # Try next term/field on error
                        continue
                    j = r.json()
                    etablissements = j.get("etablissements", [])
                    if not etablissements:
                        success_this_page = True
                        break
                    # Normalize a subset of fields to our format
                    for et in etablissements:
                        ul = et.get("uniteLegale", {}) or {}
                        naf = ul.get("activitePrincipaleUniteLegale") or et.get("activitePrincipaleEtablissement")
                        normalized = {
                            "siren": et.get("siren"),
                            "unite_legale": {"denomination": ul.get("denominationUniteLegale") or ul.get("nomUniteLegale")},
                            "activite_principale": naf,
                            "tranche_effectif_salarie": ul.get("trancheEffectifsUniteLegale") or et.get("trancheEffectifsEtablissement"),
                            "est_siege": et.get("etablissementSiege"),
                            "nom_raison_sociale": ul.get("denominationUniteLegale") or ul.get("nomUniteLegale"),
                        }
                        results.append(normalized)
                    success_this_page = True
                    break
                except Exception:
                    continue
            if success_this_page:
                break
        if not success_this_page:
            print("   INSEE fetch error: no valid query field worked for this page")
            break
        time.sleep(sleep)
    return results


def fetch_establishments_by_naf_prefix_insee_apikey(
    naf_prefix: str,
    per_page: int,
    max_pages: int,
    sleep: float,
    api_key: str,
    base_url: str,
) -> List[dict]:
    """
    Use INSEE SIRENE 3.11 API with public API key header (X-INSEE-Api-Key-Integration).
    Endpoint: /siret?q=activitePrincipale:{prefix}*&nombre={per_page}&debut={offset}
    """
    headers = {
        "X-INSEE-Api-Key-Integration": api_key,
        "Accept": "application/json",
    }
    results: List[dict] = []
    field_options = ["activitePrincipaleUniteLegale", "activitePrincipaleEtablissement"]
    for page in range(1, max_pages + 1):
        success_this_page = False
        for field in field_options:
            for term in naf_search_terms(naf_prefix):
                offset = (page - 1) * per_page
                params = {
                    "q": f"{field}:{term}",
                    "nombre": per_page,
                    "debut": offset,
                }
                url = f"{base_url}/siret"
                try:
                    r = SESSION.get(url, headers=headers, params=params, timeout=25)
                    if r.status_code != 200:
                        continue
                    j = r.json()
                    etablissements = j.get("etablissements", [])
                    if not etablissements:
                        success_this_page = True
                        break
                    for et in etablissements:
                        ul = et.get("uniteLegale", {}) or {}
                        naf = ul.get("activitePrincipaleUniteLegale") or et.get("activitePrincipaleEtablissement")
                        normalized = {
                            "siren": et.get("siren"),
                            "unite_legale": {"denomination": ul.get("denominationUniteLegale") or ul.get("nomUniteLegale")},
                            "activite_principale": naf,
                            "tranche_effectif_salarie": ul.get("trancheEffectifsUniteLegale") or et.get("trancheEffectifsEtablissement"),
                            "est_siege": et.get("etablissementSiege"),
                            "nom_raison_sociale": ul.get("denominationUniteLegale") or ul.get("nomUniteLegale"),
                        }
                        results.append(normalized)
                    success_this_page = True
                    break
                except Exception as ex:
                    print("   INSEE API key exception:", ex)
                    continue
            if success_this_page:
                break
        if not success_this_page:
            print("   INSEE API key fetch error: no valid query field worked for this page")
            break
        time.sleep(sleep)
    return results


def get_enterprise_by_siren(siren: str, sleep: float) -> Optional[dict]:
    base = f"https://entreprise.data.gouv.fr/api/sirene/v3/entreprises/{siren}"
    j = call_api(base)
    time.sleep(sleep)
    return j


# ---------------- Data structures ----------------

@dataclass
class ProcessedCandidate:
    siren: Optional[str]
    nom: str
    nom_complet_annuaire: Optional[str]
    naf: Optional[str]
    tranche_effectif: Optional[str]
    site: Optional[str]
    site_source: Optional[str]
    score: int
    # pertinence indicators
    naf_ok: bool
    name_keyword_found: bool
    site_keyword_found: bool
    job_posting_present: bool
    size_ok: bool
    score_pertinence: int
    pertinent_for_clustor: bool
    signals: Dict[str, Any]


# ---------------- Processing ----------------

def process_candidate(
    e: dict,
    naf_prefixes: List[str],
    min_emp: int,
    max_emp: int,
    sleep: float,
    web_scan: bool = True,
    use_serpapi: bool = False,
    serpapi_key: Optional[str] = None,
    serpapi_num: int = 5,
    serpapi_engine: str = "google",
    serpapi_hl: str = "fr",
    serpapi_gl: str = "fr",
    use_serper: bool = False,
    serper_key: Optional[str] = None,
) -> ProcessedCandidate:
    siren = e.get("siren")
    ul = e.get("unite_legale", {})
    denom = (
        ul.get("denomination")
        or (ul.get("periodes", [{}])[0] or {}).get("denomination")
        or ul.get("denomination_usuelle")
        or e.get("nom_complet")
        or e.get("nom_raison_sociale")
        or e.get("nom")
        or ""
    )
    denom_norm = normalize_string(denom)

    nom_complet_annuaire = e.get("nom_complet_annuaire")

    naf = e.get("activite_principale") or e.get("nomenclature_activite_principale")

    tranche = (
        e.get("tranche_effectif_salarie")
        or e.get("tranche_effectifs")
        or None
    )

    website: Optional[str] = None
    if web_scan:
        # enterprise-level fetch (rarely provides website in SIRENE, but try)
        enterprise = get_enterprise_by_siren(siren, sleep)
        if enterprise and isinstance(enterprise, dict):
            # Non-standard: some datasets mirror a website; SIRENE itself usually doesn't
            website = (
                (enterprise.get("entreprise", {}) or {}).get("site_web")
                or (enterprise.get("entreprise", {}) or {}).get("website")
            )

    tried_domain: Optional[str] = None
    homepage_html: Optional[str] = None
    domain: Optional[str] = None
    signals: Dict[str, Any] = {"name_keywords": [], "site_keywords": [], "job_posting": False}
    site_source: Optional[str] = None
    score = 0
    naf_ok = False
    name_keyword_found = False
    site_keyword_found = False
    job_posting_present = False
    size_ok_flag = False
    score_pertinence = 0
    pertinent_for_clustor = False

    # Score: NAF
    if naf and any(str(naf).startswith(code) for code in naf_prefixes):
        score += SCORE_RULES["naf"]
    # pertinence naf_ok based on refined target list
    if naf and any(str(naf).startswith(code) for code in NAF_CODES_TARGET):
        naf_ok = True

    # Score: name keywords
    for k in NAME_KEYWORDS:
        if normalize_string(k) in denom_norm:
            signals["name_keywords"].append(k)
    if signals["name_keywords"]:
        score += SCORE_RULES["name_keyword"]
        name_keyword_found = True

    if web_scan:
        # Try to get real website URL
        if website and isinstance(website, str) and website.strip():
            website = ensure_http(website.strip())
            tried_domain = extract_domain_from_url(website)
            html = http_get_html(website)
            if html:
                homepage_html = html
                domain = tried_domain
                site_source = "api"

        # If no confirmed site, guess from company name
        if not homepage_html:
            guessed_domains: List[str] = []
            # SerpAPI first if enabled
            if use_serpapi and serpapi_key:
                search_name = (e.get("nom_complet_annuaire") or denom).strip()
                # Tailor query keywords by NAF to improve precision
                naf_str = (naf or "").strip().upper()
                extra = ""
                if naf_str.startswith("71.12B"):
                    extra = " conseil"
                elif naf_str.startswith("62.02A"):
                    extra = " ESN SSII"
                q = f"{search_name}{extra} site officiel"
                serp_dom = serpapi_find_domain(q, serpapi_key, engine=serpapi_engine, num=serpapi_num, hl=serpapi_hl, gl=serpapi_gl)
                if serp_dom:
                    guessed_domains.append(serp_dom)
            # serper.dev next if enabled
            if use_serper and serper_key:
                search_name = (e.get("nom_complet_annuaire") or denom).strip()
                # Tailor query keywords by NAF for serper.dev (France locale via hl/gl=fr)
                naf_str = (naf or "").strip().upper()
                extra = ""
                if naf_str.startswith("71.12B"):
                    extra = " conseil"
                elif naf_str.startswith("62.02A"):
                    extra = " ESN SSII"
                q = f"{search_name}{extra} site officiel"
                # We only need the first result; request 1 to reduce cost.
                sp_dom = serper_find_domain(q, serper_key, num=1, hl=serpapi_hl, gl=serpapi_gl)
                if sp_dom:
                    guessed_domains.append(sp_dom)
            # Heuristic guesses
            guessed_domains.extend(guess_domain_from_name(search_name))
            # De-dup while preserving order
            seen = set()
            ordered = []
            for d in guessed_domains:
                if d not in seen:
                    seen.add(d)
                    ordered.append(d)
            for g in ordered:
                url = ensure_http(g)
                html = http_get_html(url)
                if html:
                    homepage_html = html
                    domain = extract_domain_from_url(url)
                    site_source = (
                        "serpapi" if 'serp_dom' in locals() and g == serp_dom else
                        ("serper" if 'sp_dom' in locals() and g == sp_dom else "guess")
                    )
                    break
                time.sleep(0.3)

        # If homepage found, lightly probe a few candidate paths for stronger signals
        pages_scanned = 0
        texts_to_scan: List[str] = []
        if homepage_html:
            texts_to_scan.append(homepage_html)
            pages_scanned += 1
            if domain:
                base = f"http://{domain}"
                for p in CANDIDATE_PATHS:
                    if pages_scanned >= 5:  # cap to be polite
                        break
                    url = urljoin(base, p)
                    html = http_get_html(url)
                    if html and len(html) > 1000:  # avoid tiny stubs
                        texts_to_scan.append(html)
                        pages_scanned += 1
                    time.sleep(0.2)

        # Analyze collected texts
        if texts_to_scan:
            combined = "\n\n".join(texts_to_scan)
            found_site = find_keywords_in_text(combined, SITE_KEYWORDS)
            signals["site_keywords"] = sorted(set(found_site))
            if found_site:
                score += SCORE_RULES["site_keyword"]
                site_keyword_found = True

            # crude job posting check
            job_found = any(t in combined.lower() for t in [
                "offre", "recrutement", "carriere", "carri\u00e8res", "careers", "job",
                "poste", "recrute", "candidat", "join us"
            ])
            signals["job_posting"] = bool(job_found)
            if job_found:
                score += SCORE_RULES["job_posting"]
                job_posting_present = True

    # Size scoring (heuristic; SIRENE tranche parsing varies)
    size_ok = False
    if tranche:
        # Accept any tranche as present -> treat as within typical target unless clearly 0
        if isinstance(tranche, str):
            if tranche not in {"00", "0", "0-0"}:
                size_ok = True
                # pertinence: try to detect if numbers suggest range 10-500
                nums = [int(n) for n in re.findall(r"\d+", tranche)]
                if nums:
                    # If any numeric hint within range, accept
                    if any(DEFAULT_MIN_EMP <= n <= DEFAULT_MAX_EMP for n in nums):
                        size_ok_flag = True
        else:
            size_ok = True
            size_ok_flag = True
    else:
        # Some payloads might have a concrete number (rare)
        n = e.get("nombre_salaries") or e.get("effectif")
        try:
            if n and int(n) >= min_emp and int(n) <= max_emp:
                size_ok = True
                size_ok_flag = True
        except Exception:
            size_ok = False
    if size_ok:
        score += SCORE_RULES["size"]

    # Compute pertinence score per requested weights (max ~8)
    score_pertinence += 2 if naf_ok else 0
    score_pertinence += 1 if name_keyword_found else 0
    score_pertinence += 2 if site_keyword_found else 0
    score_pertinence += 2 if job_posting_present else 0
    score_pertinence += 1 if size_ok_flag else 0
    pertinent_for_clustor = score_pertinence >= 6

    return ProcessedCandidate(
        siren=siren,
        nom=denom,
        nom_complet_annuaire=nom_complet_annuaire,
        naf=naf,
        tranche_effectif=tranche,
        site=domain,
        site_source=site_source,
        score=score,
        naf_ok=naf_ok,
        name_keyword_found=name_keyword_found,
        site_keyword_found=site_keyword_found,
        job_posting_present=job_posting_present,
        size_ok=size_ok_flag,
        score_pertinence=score_pertinence,
        pertinent_for_clustor=pertinent_for_clustor,
        signals=signals,
    )


# ---------------- Main ----------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build a prioritized ESN candidate list from SIRENE + web signals")
    p.add_argument("--naf-codes", type=str, default=",".join(DEFAULT_NAF_CODES), help="Comma-separated NAF codes or prefixes (e.g. 62.02A,71.12B or 62,71)")
    p.add_argument("--min-emp", type=int, default=DEFAULT_MIN_EMP, help="Minimum employees (heuristic)")
    p.add_argument("--max-emp", type=int, default=DEFAULT_MAX_EMP, help="Maximum employees (heuristic)")
    p.add_argument("--per-page", type=int, default=DEFAULT_PER_PAGE, help="Results per API page (<=100 recommended)")
    p.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES, help="Max pages per NAF prefix to fetch")
    p.add_argument("--sleep", type=float, default=DEFAULT_SLEEP, help="Sleep between network calls (seconds)")
    p.add_argument("--outfile", type=str, default=DEFAULT_OUTFILE, help="Output CSV path")
    # Recherche d'entreprises API
    p.add_argument("--use-recherche", action="store_true", help="Use Recherche d'entreprises API as primary data source")
    p.add_argument("--exclude-over-emp", type=int, default=DEFAULT_EXCLUDE_OVER_EMP, help="Exclude companies whose tranche suggests more than N employees (default: 2000). Set to -1 to disable.")
    p.add_argument("--use-insee", action="store_true", help="Use INSEE SIRENE API with OAuth2 if credentials available")
    p.add_argument("--insee-client-id", type=str, default=os.getenv("SIRENE_CLIENT_ID"), help="INSEE client id (env SIRENE_CLIENT_ID if omitted)")
    p.add_argument("--insee-client-secret", type=str, default=os.getenv("SIRENE_CLIENT_SECRET"), help="INSEE client secret (env SIRENE_CLIENT_SECRET if omitted)")
    p.add_argument("--insee-token-url", type=str, default=os.getenv("SIRENE_TOKEN_URL", INSEE_TOKEN_URL), help="INSEE OAuth token URL (env SIRENE_TOKEN_URL if omitted)")
    p.add_argument("--insee-base", type=str, default=os.getenv("SIRENE_API_BASE", INSEE_SIRENE_BASE), help="INSEE SIRENE API base URL (env SIRENE_API_BASE if omitted)")
    p.add_argument("--insee-api-key", type=str, default=os.getenv("SIRENE_API_KEY"), help="INSEE public API key (env SIRENE_API_KEY if omitted)")
    p.add_argument("--insee-only", action="store_true", help="Do not use any fallback; fail if INSEE is unavailable")
    p.add_argument("--no-web-scan", action="store_true", help="Skip website fetching/scanning to validate API connectivity quickly")
    p.add_argument("--ping-insee", action="store_true", help="Connectivity test: perform a minimal INSEE call and exit")
    p.add_argument("--include-zero-employees", action="store_true", help="Include companies with 0-employee tranche (default: excluded)")
    # SerpAPI options
    p.add_argument("--use-serpapi", action="store_true", help="Use SerpAPI to find company homepage from raison sociale")
    p.add_argument("--serpapi-key", type=str, default=os.getenv("SERPAPI_KEY"), help="SerpAPI key (env SERPAPI_KEY if omitted)")
    p.add_argument("--serpapi-num", type=int, default=5, help="Number of results to inspect from SerpAPI")
    p.add_argument("--serpapi-engine", type=str, default="google", help="SerpAPI engine (default: google)")
    p.add_argument("--serpapi-hl", type=str, default="fr", help="SerpAPI hl (language)")
    p.add_argument("--serpapi-gl", type=str, default="fr", help="SerpAPI gl (country)")
    # serper.dev options
    p.add_argument("--use-serper", action="store_true", help="Use serper.dev to find company homepage from raison sociale")
    p.add_argument("--serper-key", type=str, default=os.getenv("SERPER_API_KEY"), help="serper.dev API key (env SERPER_API_KEY if omitted)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    naf_codes = [c.strip() for c in args.naf_codes.split(",") if c.strip()]
    print("Collecting from SIRENE by NAF prefixes:", naf_codes)

    # Optional connectivity ping
    if args.ping_insee:
        insee_base = args.insee_base or INSEE_SIRENE_BASE
        # Try API key first
        if args.insee_api_key:
            test = fetch_establishments_by_naf_prefix_insee_apikey(
                naf_prefix=naf_codes[0], per_page=1, max_pages=1, sleep=args.sleep,
                api_key=args.insee_api_key, base_url=insee_base
            )
            ok = len(test) > 0
            print("INSEE API key connectivity:", "OK" if ok else "FAIL")
            sys.exit(0 if ok else 2)
        # Else try OAuth if creds present
        if args.insee_client_id and args.insee_client_secret:
            token = get_insee_access_token(args.insee_client_id, args.insee_client_secret, args.insee_token_url or INSEE_TOKEN_URL)
            if token:
                test = fetch_establishments_by_naf_prefix_insee(
                    naf_prefix=naf_codes[0], per_page=1, max_pages=1, sleep=args.sleep,
                    token=token, base_url=insee_base
                )
                ok = len(test) > 0
                print("INSEE OAuth connectivity:", "OK" if ok else "FAIL")
                sys.exit(0 if ok else 2)
        print("No INSEE credentials provided for ping.")
        sys.exit(2)

    all_estabs: List[dict] = []
    for naf in naf_codes:
        print(f"Fetching NAF prefix: {naf}")
        ests: List[dict] = []

        insee_base = args.insee_base or INSEE_SIRENE_BASE
        insee_token_url = args.insee_token_url or INSEE_TOKEN_URL

        # 0) Recherche d'entreprises (primary if requested)
        if args.use_recherche:
            ests = fetch_establishments_by_naf_prefix_recherche(
                naf_code=naf,
                per_page=args.per_page,
                max_pages=args.max_pages,
                sleep=args.sleep,
                exclude_over_emp=args.exclude_over_emp,
            )

        # 1) INSEE (API Key) if requested and key provided and nothing fetched yet
        if not ests and args.use_insee and args.insee_api_key:
            ests = fetch_establishments_by_naf_prefix_insee_apikey(
                naf, args.per_page, args.max_pages, args.sleep, args.insee_api_key, insee_base
            )

        # 2) INSEE (OAuth2) if requested and creds provided (fallback option if key not given)
        if not ests and args.use_insee and args.insee_client_id and args.insee_client_secret:
            token = get_insee_access_token(args.insee_client_id, args.insee_client_secret, insee_token_url)
            if token:
                ests = fetch_establishments_by_naf_prefix_insee(naf, args.per_page, args.max_pages, args.sleep, token, insee_base)
            else:
                print("   INSEE token retrieval failed; will try public endpoints…")

        # 3) Public entreprise.data.gouv.fr (may be blocked on some networks)
        if not ests and not args.insee_only:
            ests = fetch_establishments_by_naf_prefix(naf, args.per_page, args.max_pages, args.sleep)

        # 4) Fallback recherche-entreprises (open endpoint, then local filter)
        if not ests and not args.insee_only:
            print("   Primary endpoint returned 0 or failed; trying fallback API…")
            ests = fetch_establishments_by_naf_prefix_fallback_recherche(
                naf, args.per_page, args.max_pages, args.sleep
            )
        if not ests and args.insee_only:
            print("   INSEE-only mode: no data fetched from INSEE; exiting.")
            sys.exit(2)
        print(f" -> got {len(ests)} rows for prefix {naf}")
        all_estabs.extend(ests)

    print("Total raw establishments:", len(all_estabs))

    # De-dup by SIREN (enterprise level)
    by_siren: Dict[str, dict] = {}
    for e in all_estabs:
        s = e.get("siren")
        if s:
            # Prefer siège if multiple establishments show up
            if s not in by_siren or (e.get("est_siege") is True):
                by_siren[s] = e

    print("Unique SIREN:", len(by_siren))

    processed: List[ProcessedCandidate] = []
    total = len(by_siren)
    for i, (siren, e) in enumerate(by_siren.items(), start=1):
        # Early filter: drop companies with zero employees unless explicitly included
        tranche_pre = (
            e.get("tranche_effectif_salarie")
            or e.get("tranche_effectifs")
            or None
        )
        if not args.include_zero_employees and indicates_zero_employees(tranche_pre):
            print(f"Skipping SIREN {siren} - zero employees (tranche={tranche_pre})")
            continue
        if args.exclude_over_emp is not None and args.exclude_over_emp >= 0 and tranche_above_threshold(tranche_pre, args.exclude_over_emp):
            print(f"Skipping SIREN {siren} - above {args.exclude_over_emp} employees (tranche={tranche_pre})")
            continue
        display_name = (
            (e.get("unite_legale", {}) or {}).get("denomination")
            or e.get("nom_raison_sociale")
            or ""
        )
        print(f"[{i}/{total}] Processing SIREN {siren} - {display_name[:40]}")
        try:
            row = process_candidate(
                e,
                naf_codes,
                args.min_emp,
                args.max_emp,
                args.sleep,
                web_scan=not args.no_web_scan,
                use_serpapi=args.use_serpapi,
                serpapi_key=args.serpapi_key,
                serpapi_num=args.serpapi_num,
                serpapi_engine=args.serpapi_engine,
                serpapi_hl=args.serpapi_hl,
                serpapi_gl=args.serpapi_gl,
                use_serper=args.use_serper,
                serper_key=args.serper_key,
            )
            processed.append(row)
        except Exception as exc:
            print("Error processing", siren, exc)
        time.sleep(args.sleep)

    # Export CSV
    rows: List[Dict[str, Any]] = []
    for pc in processed:
        d = asdict(pc)
        # stringify signals for CSV readability
        d["signals"] = json.dumps(d["signals"], ensure_ascii=False)
        rows.append(d)

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("score", ascending=False)
    out_path = Path(args.outfile)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)

    # Also write filtered relevant file as requested
    try:
        df_filtered = df[df["pertinent_for_clustor"] == True] if not df.empty else df
        filtered_path = out_path.parent / "esn_relevant_for_clustor.csv"
        df_filtered.to_csv(filtered_path, index=False)
        print("Done. Saved to", out_path)
        print("Relevant subset saved to", filtered_path)
    except Exception as ex:
        print("Saved main CSV but failed to write filtered subset:", ex)


if __name__ == "__main__":
    main()
