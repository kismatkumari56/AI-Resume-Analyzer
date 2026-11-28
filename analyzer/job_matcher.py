"""Job description matching module.

Extracts technical requirements and skills from a job description, compares them
with the candidate's resume skills, calculates semantic text and section similarities
using sentence embeddings, and combines keyword matching with semantic analysis.
"""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple

from analyzer.semantic_matcher import (
    DEFAULT_SEMANTIC_THRESHOLD,
    calculate_semantic_job_match,
    identify_semantically_related_skills,
)
from analyzer.skill_dictionary import _compile_term

logger = logging.getLogger(__name__)

# Standard disclaimer stating scores are alignment metrics, not hiring guarantees
HIRING_DISCLAIMER = (
    "This match score indicates content and terminology alignment between your resume and "
    "the job description. It is an analytical indicator and does not represent guaranteed "
    "hiring probability, candidate qualification, or an employment outcome."
)

# Pre-defined list of skills and technical requirements.
# Reuses the core skills from skills_extractor and expands with standard tools/technologies.
JOB_SKILLS = [
    # Programming Languages
    "Python", "Java", "C++", "C", "C#", "JavaScript", "TypeScript",
    "Go", "Rust", "PHP", "Ruby", "Swift", "Kotlin", "R", "Scala",
    # Web & Frameworks
    "HTML", "CSS", "React", "Angular", "Vue", "Next.js", "Node.js",
    "Express", "Flask", "Django", "FastAPI", "Spring Boot", "ASP.NET",
    # Databases & Caching
    "SQL", "MySQL", "PostgreSQL", "MongoDB", "Redis", "SQLite",
    "Oracle", "Cassandra", "DynamoDB",
    # Cloud, DevOps & Tools
    "AWS", "Azure", "GCP", "Google Cloud", "Docker", "Kubernetes",
    "Git", "GitHub", "GitLab", "CI/CD", "Linux", "Terraform",
    # AI / ML & Data Science
    "Machine Learning", "Deep Learning", "NLP", "Computer Vision",
    "Data Analysis", "Pandas", "NumPy", "TensorFlow", "PyTorch", "Scikit-Learn",
    # Core Engineering & Concepts
    "REST API", "GraphQL", "Data Structures", "Algorithms", "OOP",
    "Microservices", "System Design", "Agile", "Scrum",
    # Soft & Professional Skills
    "Communication", "Problem Solving", "Teamwork", "Leadership"
]

# Aliases mapping variant skill terms to canonical skill names
SKILL_ALIASES: Dict[str, str] = {
    "js": "JavaScript",
    "ts": "TypeScript",
    "py": "Python",
    "react.js": "React",
    "reactjs": "React",
    "node": "Node.js",
    "nodejs": "Node.js",
    "vue.js": "Vue",
    "vuejs": "Vue",
    "golang": "Go",
    "postgres": "PostgreSQL",
    "mongo": "MongoDB",
    "k8s": "Kubernetes",
    "amazon web services": "AWS",
    "google cloud platform": "GCP",
    "ml": "Machine Learning",
    "dl": "Deep Learning",
    "natural language processing": "NLP",
    "restful api": "REST API",
    "restful apis": "REST API",
    "rest apis": "REST API",
    "rest": "REST API",
    "object oriented programming": "OOP",
    "object-oriented programming": "OOP",
}


# Pre-compile context-aware patterns once for JOB_SKILLS and SKILL_ALIASES
_JOB_SKILL_PATTERNS = [(skill, _compile_term(skill)) for skill in JOB_SKILLS]
_JOB_ALIAS_PATTERNS = [
    (canonical_name, _compile_term(alias))
    for alias, canonical_name in SKILL_ALIASES.items()
]


def extract_job_skills(text: Optional[str]) -> List[str]:
    """Extract unique relevant skills and requirements from a job description text.

    Args:
        text: Raw text of the job description.

    Returns:
        Sorted list of unique detected canonical skills.
    """
    if not text or not text.strip():
        return []

    found: Set[str] = set()

    # 1. Match canonical skills using context-aware boundaries
    for skill, pattern in _JOB_SKILL_PATTERNS:
        if pattern.search(text):
            found.add(skill)

    # 2. Match aliases using context-aware boundaries
    for canonical_name, pattern in _JOB_ALIAS_PATTERNS:
        if pattern.search(text):
            found.add(canonical_name)

    return sorted(found, key=lambda s: s.lower())


def match_resume_to_job(
    resume_skills: List[str],
    job_description: Optional[str],
    resume_text: Optional[str] = None,
    resume_sections: Optional[Dict[str, str]] = None,
) -> Dict:
    """Compare extracted resume skills and content with job description requirements.

    Combines traditional keyword matching with NLP sentence embedding similarity
    across resume text and sections, and identifies semantically related skills.

    Args:
        resume_skills: List of skills detected in the candidate's resume.
        job_description: Plain text job description pasted by the user.
        resume_text: Optional full plain text of the resume for semantic analysis.
        resume_sections: Optional dictionary of detected resume sections.

    Returns:
        Structured dictionary containing:
        - matching_skills: List of skills found directly in both resume and job.
        - semantically_related_skills: List of skills matched via semantic similarity.
        - missing_skills: List of required skills missing from the resume.
        - required_skills: List of all unique skills required by the job.
        - match_percentage: Integer percentage (0-100) combining keyword & semantic match.
        - keyword_match_percentage: Integer percentage of exact keyword overlap.
        - semantic_match_percentage: Integer percentage of semantic similarity or None.
        - section_similarities: Dict mapping section names to similarity percentages.
        - total_required: Total count of unique required skills.
        - total_matching: Total count of directly matching skills.
        - has_job_description: Boolean indicating if a non-empty JD was provided.
        - explanation: Transparent explanation of the calculation formula and breakdown.
        - disclaimer: Notice that scores are alignment metrics, not hiring guarantees.
        - semantic_status: 'available', 'unavailable', or 'error'.
    """
    is_empty_jd = not job_description or not job_description.strip()

    if is_empty_jd:
        return {
            "matching_skills": [],
            "semantically_related_skills": [],
            "missing_skills": [],
            "required_skills": [],
            "match_percentage": 0,
            "keyword_match_percentage": 0,
            "semantic_match_percentage": None,
            "section_similarities": {},
            "total_required": 0,
            "total_matching": 0,
            "has_job_description": False,
            "explanation": "No job description was provided for comparison.",
            "disclaimer": HIRING_DISCLAIMER,
            "semantic_status": "unavailable",
        }

    # Extract requirements from the job description
    required = extract_job_skills(job_description)

    # Handle case where no recognizable skills are detected in the job description early
    if not required:
        explanation = (
            "No recognizable technical skills were detected in the provided job description. "
            "Try including specific tools, technologies or languages. "
            f"{HIRING_DISCLAIMER}"
        )

        return {
            "matching_skills": [],
            "exact_matching_skills": [],
            "semantically_related_skills": [],
            "missing_skills": [],
            "required_skills": [],
            "match_percentage": 0,
            "keyword_match_percentage": 0,
            "semantic_match_percentage": None,
            "section_similarities": {},
            "total_required": 0,
            "total_matching": 0,
            "exact_matching_count": 0,
            "semantic_matching_count": 0,
            "has_job_description": True,
            "explanation": explanation,
            "disclaimer": HIRING_DISCLAIMER,
            "semantic_status": "unavailable",
        }

    # Normalize resume skills for case-insensitive and alias-aware comparison
    resume_skills_canonical: Set[str] = set()
    for s in (resume_skills or []):
        s_clean = s.strip()
        if not s_clean:
            continue
        canonical = SKILL_ALIASES.get(s_clean.lower(), s_clean)
        matched_title = next(
            (js for js in JOB_SKILLS if js.lower() == canonical.lower()),
            canonical
        )
        resume_skills_canonical.add(matched_title)

    # Keyword intersection (exact canonical matches)
    matching: List[str] = []
    initial_missing: List[str] = []
    resume_skills_lower = {s.lower() for s in resume_skills_canonical}

    for req in required:
        if req.lower() in resume_skills_lower:
            matching.append(req)
        else:
            initial_missing.append(req)

    total_required = len(required)
    exact_matching_count = len(matching)

    # Perform semantic matching with graceful error handling
    semantic_result = {
        "semantic_similarity": None,
        "section_similarities": {},
        "semantically_related_skills": [],
        "status": "unavailable",
        "error_message": None,
    }

    try:
        semantic_result = calculate_semantic_job_match(
            resume_text=resume_text,
            job_description=job_description,
            resume_sections=resume_sections,
            resume_skills=list(resume_skills_canonical),
            missing_skills=initial_missing,
        )
    except Exception as exc:
        logger.warning("Error running semantic matching: %s", exc)
        semantic_result = {
            "semantic_similarity": None,
            "section_similarities": {},
            "semantically_related_skills": [],
            "status": "error",
            "error_message": str(exc),
        }

    semantically_related = semantic_result.get("semantically_related_skills") or []
    section_similarities = semantic_result.get("section_similarities") or {}
    semantic_sim = semantic_result.get("semantic_similarity")
    semantic_status = semantic_result.get("status", "unavailable")
    semantic_error = semantic_result.get("error_message")

    # Filter out semantically related skills from missing list
    related_req_names = {r["required_skill"].lower() for r in semantically_related}
    final_missing = [m for m in initial_missing if m.lower() not in related_req_names]

    # Accounting consistency: total_matching includes both exact and semantically related skills
    semantic_matching_count = len(semantically_related)
    total_matching = exact_matching_count + semantic_matching_count

    # Weighted skill match score: 1.0 per exact match + proportional partial credit for semantic matches
    weighted_score = exact_matching_count + sum(
        (s.get("similarity", 60) / 100.0) for s in semantically_related
    )
    keyword_percentage = (
        round((weighted_score / total_required) * 100)
        if total_required > 0
        else 0
    )

    # Calculate combined match percentage and explanation
    if resume_text is not None and semantic_sim is not None:
        # Both keyword and semantic representations are available
        combined_percentage = round(0.5 * keyword_percentage + 0.5 * semantic_sim)
        match_percentage = combined_percentage

        explanation_parts = [
            f"Overall match score ({match_percentage}%) combines keyword matching ({keyword_percentage}%) "
            f"and semantic content similarity ({semantic_sim}%).",
            f"{exact_matching_count} of {total_required} required skills were exact matches."
        ]

        if semantically_related:
            related_items = [
                f"'{s['matched_skill']}' relates to '{s['required_skill']}' ({s['similarity']}%)"
                for s in semantically_related
            ]
            explanation_parts.append(
                f"Identified {len(semantically_related)} semantically related skill(s): "
                + ", ".join(related_items) + "."
            )

        explanation_parts.append(HIRING_DISCLAIMER)
        explanation = " ".join(explanation_parts)

    else:
        # Fallback to keyword-only matching (e.g. when resume_text was not passed, or model error)
        match_percentage = keyword_percentage

        if semantically_related:
            explanation_parts = [
                f"Match percentage measures skill overlap: "
                f"({exact_matching_count} exact + {semantic_matching_count} semantic / {total_required} required) = {keyword_percentage}%."
            ]
            related_items = [
                f"'{s['matched_skill']}' relates to '{s['required_skill']}' ({s['similarity']}%)"
                for s in semantically_related
            ]
            explanation_parts.append(
                f"Identified {len(semantically_related)} semantically related skill(s): "
                + ", ".join(related_items) + "."
            )
        else:
            explanation_parts = [
                f"Match percentage measures skill overlap: "
                f"({exact_matching_count} matching / {total_required} required) × 100 = {keyword_percentage}%."
            ]

        if semantic_status == "error":
            explanation_parts.append(
                f"Note: Semantic NLP analysis encountered an error ({semantic_error}); "
                "reverted to keyword-only matching."
            )

        explanation_parts.append(HIRING_DISCLAIMER)
        explanation = " ".join(explanation_parts)

    return {
        "matching_skills": matching,
        "exact_matching_skills": matching,
        "semantically_related_skills": semantically_related,
        "missing_skills": final_missing,
        "required_skills": required,
        "match_percentage": match_percentage,
        "keyword_match_percentage": keyword_percentage,
        "semantic_match_percentage": semantic_sim,
        "section_similarities": section_similarities,
        "total_required": total_required,
        "total_matching": total_matching,
        "exact_matching_count": exact_matching_count,
        "semantic_matching_count": semantic_matching_count,
        "has_job_description": True,
        "explanation": explanation,
        "disclaimer": HIRING_DISCLAIMER,
        "semantic_status": semantic_status,
    }
