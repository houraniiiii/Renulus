"""Reviewed Updates search concepts for exact installed curriculum identities.

These bounded editorial choices are not an ontology or exhaustive synonyms.
Review: docs/implementation/finish-topic-discovery-20261007.md. Only fixed
concepts leave the app for these ID/title pairs; other labels remain literal.
"""


def _phrase(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'TITLE_ABS:"{escaped}"'


def _or(*expressions: str) -> str:
    return "(" + " OR ".join(expressions) + ")"


def _phrases(*values: str) -> str:
    return _or(*(_phrase(value) for value in values))


_KIDNEY_SCOPE = _phrases("kidney", "renal", "hemodialysis", "haemodialysis", "peritoneal dialysis")


def _kidney_scoped(*concepts: str) -> str:
    # Every broad alternative is inside the AND, never an unscoped OR branch.
    return f"({_KIDNEY_SCOPE} AND {_phrases(*concepts)})"


# Keys deliberately include the exact installed title, not just a reusable ID.
# Already useful literal headings T08, T10 and T21 keep their phrase contract.
_TOPIC_QUERIES = {
    ("T01", "Foundations of kidney science"): _kidney_scoped(
        "physiology", "anatomy", "histology", "tubular transport"),
    ("T02", "Clinical assessment and diagnostics"): _kidney_scoped(
        "diagnosis", "diagnostics", "biopsy", "urinalysis", "glomerular filtration"),
    ("T03", "Sodium, water and volume"): _kidney_scoped(
        "hyponatremia", "hyponatraemia", "hypernatremia", "hypernatraemia",
        "fluid overload", "water balance", "volume depletion"),
    ("T04", "Potassium and acid-base"): _kidney_scoped(
        "hyperkalemia", "hyperkalaemia", "hypokalemia", "hypokalaemia", "acidosis", "alkalosis"),
    ("T05", "Mineral metabolism and bone"): _kidney_scoped(
        "mineral metabolism", "bone disorder", "hyperparathyroidism", "osteodystrophy"),
    ("T06", "Acute kidney injury and acute kidney disease"): _phrases(
        "acute kidney injury", "acute kidney disease"),
    ("T07", "Critical care nephrology"): _kidney_scoped(
        "critical care", "intensive care", "sepsis"),
    ("T09", "Hypertension and vascular kidney disease"): _kidney_scoped(
        "hypertension", "renovascular disease", "renal artery stenosis"),
    ("T11", "Tubular and interstitial disease"): _phrases(
        "interstitial nephritis", "tubulointerstitial nephritis", "tubulointerstitial disease",
        "renal tubular disorders", "renal tubular acidosis", "Fanconi syndrome",
        "tubulopathy", "tubulopathies", "acute tubular injury"),
    ("T12", "Cystic and inherited kidney disease"): _phrases(
        "polycystic kidney disease", "cystic kidney disease", "inherited kidney disease",
        "hereditary nephropathy", "Alport syndrome"),
    ("T13", "Stones and obstruction"): _phrases(
        "kidney stones", "nephrolithiasis", "urolithiasis", "obstructive uropathy", "hydronephrosis"),
    ("T14", "Diabetes and metabolic kidney disease"): _or(
        _phrase("diabetic nephropathy"),
        _kidney_scoped("diabetes", "diabetic", "metabolic syndrome", "obesity")),
    ("T15", "Thrombotic microangiopathy and complement"): _kidney_scoped(
        "thrombotic microangiopathy", "complement", "hemolytic uremic syndrome",
        "haemolytic uraemic syndrome"),
    ("T16", "Kidney disease in systemic illness"): _or(
        _phrase("lupus nephritis"), _kidney_scoped("vasculitis", "systemic sclerosis", "scleroderma")),
    ("T17", "Infection in nephrology"): _kidney_scoped("infection", "infections", "vaccination"),
    ("T18", "Onconephrology and paraproteins"): _phrases(
        "onconephrology", "monoclonal gammopathy of renal significance", "cast nephropathy",
        "paraprotein related kidney disease"),
    ("T19", "Medicines and nephrotoxicity"): _or(
        _phrases("nephrotoxicity", "nephrotoxic", "drug induced kidney injury"),
        _kidney_scoped("drug dosing", "pharmacokinetics")),
    ("T20", "Dialysis and kidney failure therapies"): _phrases(
        "hemodialysis", "haemodialysis", "peritoneal dialysis", "kidney replacement therapy",
        "renal replacement therapy", "kidney failure"),
    ("T22", "Procedures and interventional nephrology"): _phrases(
        "kidney biopsy", "renal biopsy", "dialysis access", "interventional nephrology"),
    ("T23", "Extracorporeal therapies and apheresis"): _kidney_scoped(
        "apheresis", "plasma exchange", "extracorporeal therapy", "extracorporeal therapies"),
    ("T24", "Life-course and special populations"): _kidney_scoped(
        "pregnancy", "pediatric", "paediatric", "frailty", "older adults", "transition"),
    ("T25", "Nutrition, prevention and rehabilitation"): _kidney_scoped(
        "nutrition", "diet", "exercise", "rehabilitation", "prevention"),
    ("T26", "Supportive care, ethics and evidence"): _kidney_scoped(
        "supportive care", "conservative management", "palliative care", "shared decision making",
        "ethics", "evidence based practice"),
    ("T27", "Kidney interfaces with other specialties"): _phrases(
        "cardiorenal syndrome", "hepatorenal syndrome", "pulmonary renal syndrome"),
}


def topic_expression(topic_id: str, title: str) -> str:
    """Compile only an installed ID/title pair; never consume prompts or cases."""
    return _TOPIC_QUERIES.get((topic_id, title)) or _phrase(title)
