"""Mock life-sciences research tools.

These are PLACEHOLDER implementations that return synthetic data so the harness
is complete and runnable end-to-end. Each one represents a real integration
that would be backed by an MCP server or API in production (see mcp_config.json
for where those servers plug in). Swap the body of each function — or replace it
with a real MCP client call — without changing the agent wiring.

Every tool returns a `source` and `timestamp` so the model can cite provenance,
per the research system prompt. Identifiers below are illustrative and synthetic.
"""

from datetime import datetime, timezone
from typing import Any, Dict

from strands import tool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@tool
def search_literature(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Search the biomedical literature and return citations.

    Args:
        query: Free-text query, e.g. "KRAS G12C inhibitor resistance".
        max_results: Max papers to return (default 5).

    MOCK: replace with a real PubMed / Europe PMC MCP server.
    """
    return {
        "source": "MOCK:pubmed",
        "timestamp": _now(),
        "query": query,
        "results": [
            {
                "pmid": "00000001",
                "title": "Synthetic placeholder title relevant to the query",
                "journal": "J. Placeholder Res.",
                "year": 2025,
                "doi": "10.0000/placeholder.0001",
                "abstract_snippet": "Synthetic abstract snippet — not a real paper.",
            }
        ][:max_results],
        "note": "Synthetic data — do not cite as a real reference.",
    }


@tool
def lookup_gene(gene_symbol: str) -> Dict[str, Any]:
    """Look up gene, function, and associated variants/pathways.

    Args:
        gene_symbol: HGNC gene symbol, e.g. "TP53".

    MOCK: replace with a real NCBI Gene / Ensembl / UniProt MCP server.
    """
    return {
        "source": "MOCK:ncbi-gene",
        "timestamp": _now(),
        "gene_symbol": gene_symbol,
        "ncbi_gene_id": "0000",
        "uniprot_id": "P00000",
        "function": "Synthetic functional summary for the gene.",
        "pathways": ["MOCK-PATHWAY-1", "MOCK-PATHWAY-2"],
        "note": "Synthetic data.",
    }


@tool
def search_compounds(query: str) -> Dict[str, Any]:
    """Search small molecules by name/target and return bioactivity summary.

    Args:
        query: Compound name, target, or InChIKey, e.g. "sotorasib" or "KRAS".

    MOCK: replace with a real ChEMBL / PubChem MCP server.
    """
    return {
        "source": "MOCK:chembl",
        "timestamp": _now(),
        "query": query,
        "compounds": [
            {
                "chembl_id": "CHEMBL0000000",
                "pref_name": "PLACEHOLDER-COMPOUND",
                "inchikey": "AAAAAAAAAAAAAA-AAAAAAAAAA-A",
                "target": "MOCK-TARGET",
                "activity": {"standard_type": "IC50", "value_nm": 12.4},
            }
        ],
        "note": "Synthetic data.",
    }


@tool
def get_protein_structure(uniprot_id: str) -> Dict[str, Any]:
    """Return experimental / predicted structure metadata for a protein.

    Args:
        uniprot_id: UniProt accession, e.g. "P01116".

    MOCK: replace with a real PDB / AlphaFold DB MCP server.
    """
    return {
        "source": "MOCK:pdb-alphafold",
        "timestamp": _now(),
        "uniprot_id": uniprot_id,
        "pdb_ids": ["0XXX"],
        "alphafold_model": "AF-PLACEHOLDER-F1",
        "mean_plddt": 88.3,
        "note": "Synthetic data.",
    }


@tool
def get_assay_results(experiment_id: str) -> Dict[str, Any]:
    """Return assay / screening / omics results from the LIMS.

    Args:
        experiment_id: Internal experiment or plate identifier, e.g. "EXP-2026-0912".

    MOCK: replace with a real LIMS / screening-data MCP server.
    """
    return {
        "source": "MOCK:lims",
        "timestamp": _now(),
        "experiment_id": experiment_id,
        "assay_type": "dose-response (mock)",
        "readout": "% inhibition",
        "n_replicates": 3,
        "results": [
            {"conc_um": 10.0, "mean_inhibition_pct": 91.2, "stdev": 2.1},
            {"conc_um": 1.0, "mean_inhibition_pct": 63.5, "stdev": 3.4},
            {"conc_um": 0.1, "mean_inhibition_pct": 18.7, "stdev": 4.0},
        ],
        "ic50_um": 0.42,
        "qc_flag": "PASS",
        "note": "Synthetic data.",
    }


@tool
def search_clinical_trials(condition: str, intervention: str = "") -> Dict[str, Any]:
    """Search the clinical-trial landscape for a condition/intervention.

    Args:
        condition: Disease or indication, e.g. "non-small cell lung cancer".
        intervention: Optional drug/target filter.

    MOCK: replace with a real ClinicalTrials.gov MCP server.
    """
    return {
        "source": "MOCK:clinicaltrials",
        "timestamp": _now(),
        "condition": condition,
        "intervention": intervention,
        "trials": [
            {
                "nct_id": "NCT00000000",
                "title": "Synthetic placeholder trial",
                "phase": "Phase 2",
                "status": "Recruiting",
                "enrollment": 120,
            }
        ],
        "note": "Synthetic data.",
    }


@tool
def create_eln_entry(
    title: str, methods: str, results_summary: str
) -> Dict[str, Any]:
    """Draft a reproducible ELN entry for scientist review (does NOT sign/commit).

    Args:
        title: Experiment title.
        methods: Methods / protocol, parameters, and inputs.
        results_summary: Summary of observations and outcomes.

    MOCK: replace with a real ELN MCP server (Benchling, LabArchives, etc.).
    Returns a DRAFT only; the scientist must review, sign, and commit per
    ALCOA+ data-integrity requirements.
    """
    return {
        "source": "MOCK:eln",
        "timestamp": _now(),
        "status": "DRAFT_PENDING_SCIENTIST_SIGNOFF",
        "entry": {
            "title": title,
            "methods": methods,
            "results_summary": results_summary,
        },
        "note": "Draft only — not signed or committed. Requires scientist review.",
    }


# Registry consumed by agent.py.
RESEARCH_TOOLS = [
    search_literature,
    lookup_gene,
    search_compounds,
    get_protein_structure,
    get_assay_results,
    search_clinical_trials,
    create_eln_entry,
]
