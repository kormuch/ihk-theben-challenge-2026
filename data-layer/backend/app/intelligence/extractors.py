"""
Stage 2: Specialized Extractor Agents.
Each document type gets its own pre-prompted agent that knows exactly what to look for.
Every extracted field includes a citation — where in the source document the value was found.
"""
import json
import re

from app.intelligence.llm import call_llm

# ── Base extraction prompt structure ─────────────────────────────────────────

_BASE = """You are a specialized {doc_type} extraction agent for an industrial product data platform.
Your job is to extract structured product information from this {doc_type}.

{specific_instructions}

Rules:
- Extract ALL products you can find in the document.
- For each product, extract as many attributes as you can find.
- For EVERY extracted value, provide a citation — quote the exact text or describe where in the document you found it (e.g., "Table on page 2, row 'Rated Voltage'", "Header: 'LUXA 500-360'").
- If you can identify which product family this belongs to (Timer, Motion Sensor, Room Thermostat, or suggest a new one), include it.
- If a value is ambiguous or uncertain, say so in the citation.

Respond ONLY with valid JSON (no markdown, no explanation outside the JSON):
{{
  "products": [
    {{
      "article_number": "...",
      "name": "...",
      "family_suggestion": "...",
      "attributes": {{
        "key": "value",
        ...
      }},
      "citations": {{
        "article_number": "where you found this",
        "name": "where you found this",
        "family_suggestion": "why you chose this family",
        "key": "where you found this value",
        ...
      }}
    }}
  ]
}}

<document>
{content}
</document>"""

# ── Per-type specific instructions ───────────────────────────────────────────

EXTRACTOR_PROMPTS: dict[str, str] = {
    "Datasheet": """This is a product datasheet — typically contains technical specifications.
Look for:
- Article/model number (often in header or title)
- Product name
- Electrical specs: voltage, current, power, switching capacity
- Physical specs: dimensions, weight, module width, mounting type
- Environmental: IP protection class, operating temperature range
- Certifications: CE, VDE, UL, KNX, etc.
- RoHS/REACH compliance
- Detection specs (for sensors): angle, range, follow-up time, light threshold
- Control specs (for thermostats): temperature range, switching differential, output type
- Communication: KNX, BLE, Zigbee, etc.
Pay attention to tables — datasheets typically present specs in tabular format.""",

    "Lab Report": """This is a laboratory test report — contains test results and measurements.
Look for:
- Product under test (article number, name)
- Test standard (IEC, EN, UL, etc.)
- Test conditions (temperature, humidity, voltage)
- Test results: pass/fail, measured values
- Deviations or non-conformities
- Testing laboratory name and accreditation
- Test date and report number
Map test results to product attributes where possible (e.g., "IP test passed at IP55" → protection_class: "IP 55").""",

    "Certificate": """This is a certification document — confirms compliance with standards.
Look for:
- Certificate number
- Issuing body (TÜV, VDE, UL, etc.)
- Certified product (article number, name)
- Standard(s) certified against (IEC 60730, EN 55014, etc.)
- Validity period (issue date, expiry date)
- Scope of certification
- Conditions or limitations
Map to attributes: certifications list, compliance flags (rohs_compliant, reach_compliant).""",

    "Software Documentation": """This is software/firmware documentation.
Look for:
- Product(s) this software applies to
- Firmware version
- Communication protocols supported (KNX, BLE, Modbus, etc.)
- Configuration parameters
- API endpoints or integration points
- Supported operating systems or platforms
Map to attributes where applicable (e.g., knx_capable, firmware_version).""",

    "Bill of Materials": """This is a Bill of Materials (BOM) — lists components of a product.
Look for:
- Parent product (article number, name)
- Component list with part numbers
- Materials used (relevant for RoHS/REACH/recycling)
- Quantities
- Supplier information
Map to attributes: materials list, component count, hazardous substances.""",

    "Marketing Material": """This is marketing or promotional material.
Look for:
- Product name and article number
- Key selling points and features
- Application areas / use cases
- Product family or category
- Any technical specs mentioned (often simplified)
Be careful: marketing materials may overstate capabilities. Flag uncertainty in citations.""",

    "Compliance Declaration": """This is a compliance or conformity declaration (e.g., EU Declaration of Conformity).
Look for:
- Product(s) covered
- Directives complied with (LVD, EMC, RED, RoHS, REACH, WEEE)
- Harmonized standards applied
- Manufacturer information
- Date of declaration
Map to attributes: certifications, rohs_compliant, reach_compliant.""",

    "Safety Data Sheet": """This is a Safety Data Sheet (SDS/MSDS).
Look for:
- Product identification
- Hazardous substances and their concentrations
- CAS numbers
- Safety classifications
- Disposal information
- Environmental impact data
Map to attributes: hazardous_substances, disposal_class, environmental_rating.""",

    "Product Specification": """This is a detailed product specification document.
Look for:
- All technical parameters with exact values
- Performance characteristics
- Electrical and mechanical specifications
- Environmental ratings
- Ordering information and variants
This is similar to a datasheet but typically more detailed and formal.""",

    "Test Report": """This is a test report — documents specific tests performed on a product.
Look for:
- Product under test
- Test procedure and methodology
- Measured values and tolerances
- Pass/fail criteria and results
- Test equipment used
- Environmental conditions during test
Map results to product attributes where possible.""",
}

# Fallback for Unknown or unrecognized types
_GENERIC_INSTRUCTIONS = """This document type was not specifically recognized.
Extract any product-related information you can find:
- Product identifiers (article numbers, model names)
- Technical specifications
- Compliance information
- Any structured data (tables, key-value pairs)"""


async def extract_from_document(doc_type: str, text_content: str) -> dict:
    """Run the specialized extractor for the given document type. Returns {products: [...]}."""
    content = text_content[:12000]
    specific = EXTRACTOR_PROMPTS.get(doc_type, _GENERIC_INSTRUCTIONS)

    prompt = _BASE.format(
        doc_type=doc_type,
        specific_instructions=specific,
        content=content,
    )

    raw = await call_llm(prompt)

    # Parse JSON
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("No JSON in extractor response")

    return json.loads(m.group(0))
