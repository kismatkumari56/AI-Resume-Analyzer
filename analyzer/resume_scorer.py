"""Resume scoring module with explainable multi-category breakdown.

Calculates an overall resume score based on 7 documented evaluation criteria:
Contact Information, Professional Summary, Technical Skills, Education,
Experience, Projects, and Readability & Formatting. Provides detailed,
transparent explanations and improvement suggestions for each category.
"""

import re
from typing import Dict, List, Optional, Any

from analyzer.skills_extractor import get_skill_dictionary_manager

# Maximum points allocated to each category (total = 100)
CATEGORY_MAX_SCORES: Dict[str, int] = {
    "Contact Information": 10,
    "Professional Summary": 10,
    "Technical Skills": 20,
    "Education": 15,
    "Experience": 15,
    "Projects": 20,
    "Readability": 10,
}

# Explicitly documented scoring formula for each category
CATEGORY_FORMULAS: Dict[str, str] = {
    "Contact Information": "Email address (5 pts) + Phone number (5 pts) = 10 pts max.",
    "Professional Summary": "Presence of professional summary or career objective heading/statement = 10 pts max.",
    "Technical Skills": "2 pts per unique detected technical skill, capped at 20 pts max (10 skills for full credit).",
    "Education": "Presence of education section, university, or degree credentials = 15 pts max.",
    "Experience": "Presence of professional experience, work history, or internship keywords = 15 pts max.",
    "Projects": "Presence of projects section, project work, or code repositories = 20 pts max.",
    "Readability": "Substantial content (>= 100 words, 5 pts) + standard section structure (>= 3 headings, 5 pts) = 10 pts max.",
}

# Documented overall scoring formula summary
SCORING_FORMULA_SUMMARY: str = (
    "Overall Score (0-100) = Contact Information (max 10) + Professional Summary (max 10) + "
    "Technical Skills (max 20) + Education (max 15) + Experience (max 15) + Projects (max 20) + "
    "Readability & Formatting (max 10)."
)


def calculate_resume_score(text: Optional[str]) -> Dict[str, Any]:
    """Calculate an explainable resume score with multi-category breakdown.

    Args:
        text: Plain text extracted from candidate's resume.

    Returns:
        Structured dictionary containing:
        - score: Total integer score (0-100).
        - breakdown: Dict mapping category names to integer points earned.
        - category_details: Dict mapping category names to rich explanation dicts.
        - overall_explanation: Transparent explanation of the overall score calculation.
        - scoring_formula: Documented overall scoring formula string.
        - category_formulas: Dict of category-specific formulas.
        - improvement_areas: List of specific category deficits and improvement tips.
        - detected_skills: List of detected technical skills.
        - word_count: Total word count in resume text.
    """
    if not text:
        text = ""

    text_lower = text.lower()
    score = 0
    breakdown: Dict[str, int] = {}
    category_details: Dict[str, Dict[str, Any]] = {}
    improvement_areas: List[Dict[str, Any]] = []

    # 1. Contact Information (10 Marks)
    contact_score = 0
    email = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
    phone = re.search(r'(?<!\w)(?:\+?\d[\d\s()-]{8,}\d)(?!\w)', text)

    if email:
        contact_score += 5
    if phone:
        contact_score += 5

    breakdown["Contact Information"] = contact_score
    score += contact_score

    if email and phone:
        contact_explanation = f"Found email address ({email.group(0)}) and phone number ({phone.group(0)}), earning full credit (+10/10)."
        contact_improvement = None
        contact_status = "full"
    elif email:
        contact_explanation = f"Found email address ({email.group(0)}) (+5/10), but no phone number was detected (0/5)."
        contact_improvement = "Add a telephone number with country/area code in the header."
        contact_status = "partial"
    elif phone:
        contact_explanation = f"Found phone number ({phone.group(0)}) (+5/10), but no email address was detected (0/5)."
        contact_improvement = "Add a professional email address in the header."
        contact_status = "partial"
    else:
        contact_explanation = "Neither an email address nor a phone number was detected (0/10)."
        contact_improvement = "Add both a professional email and a telephone number with country/area code in the header."
        contact_status = "missing"

    category_details["Contact Information"] = {
        "score": contact_score,
        "max": CATEGORY_MAX_SCORES["Contact Information"],
        "explanation": contact_explanation,
        "formula": CATEGORY_FORMULAS["Contact Information"],
        "improvement": contact_improvement,
        "status": contact_status,
    }
    if contact_improvement:
        improvement_areas.append({
            "category": "Contact Information",
            "points_lost": CATEGORY_MAX_SCORES["Contact Information"] - contact_score,
            "suggestion": contact_improvement,
        })

    # 2. Professional Summary (10 Marks)
    summary_keywords = [
        "professional summary",
        "career objective",
        "profile summary",
        "about me",
        "summary",
        "objective",
    ]

    matched_summary_keyword = next(
        (kw for kw in summary_keywords if kw in text_lower),
        None
    )
    summary_score = 10 if matched_summary_keyword else 0

    breakdown["Professional Summary"] = summary_score
    score += summary_score

    if summary_score == 10:
        summary_explanation = f"Detected professional summary or career objective section ('{matched_summary_keyword}'), earning full credit (+10/10)."
        summary_improvement = None
        summary_status = "full"
    else:
        summary_explanation = "No professional summary or career objective section was detected (0/10)."
        summary_improvement = "Add a concise 2-3 sentence professional summary at the top outlining your background and career goals."
        summary_status = "missing"

    category_details["Professional Summary"] = {
        "score": summary_score,
        "max": CATEGORY_MAX_SCORES["Professional Summary"],
        "explanation": summary_explanation,
        "formula": CATEGORY_FORMULAS["Professional Summary"],
        "improvement": summary_improvement,
        "status": summary_status,
    }
    if summary_improvement:
        improvement_areas.append({
            "category": "Professional Summary",
            "points_lost": CATEGORY_MAX_SCORES["Professional Summary"] - summary_score,
            "suggestion": summary_improvement,
        })

    # 3. Technical Skills (20 Marks)
    # Use the centralized skill dictionary (excluding Soft Skills) so modern
    # stacks and aliases are recognized without double-counting C++ as C.
    skill_manager = get_skill_dictionary_manager()
    tech_categories = {
        cat: skills
        for cat, skills in skill_manager.get_categories().items()
        if cat.lower() != "soft skills"
    }
    detected_skills = skill_manager.extract_skills(
        text,
        custom_dictionary=tech_categories if tech_categories else None,
    )

    skills_score = min(len(detected_skills) * 2, 20)

    breakdown["Technical Skills"] = skills_score
    score += skills_score

    if skills_score == 20:
        skills_explanation = f"Detected 10+ technical skills ({', '.join(detected_skills[:6])}...), earning full credit (+20/20)."
        skills_improvement = None
        skills_status = "full"
    elif skills_score > 0:
        skills_explanation = f"Detected {len(detected_skills)} technical skill(s) ({', '.join(detected_skills)}), earning {skills_score}/20 points (2 pts per skill, max 20)."
        skills_improvement = f"Add at least {10 - len(detected_skills)} more relevant tools, frameworks, or languages to reach full credit."
        skills_status = "partial"
    else:
        skills_explanation = "No standard technical skills detected in the resume text (0/20)."
        skills_improvement = "Add a dedicated Technical Skills section listing programming languages, frameworks, databases, and tools."
        skills_status = "missing"

    category_details["Technical Skills"] = {
        "score": skills_score,
        "max": CATEGORY_MAX_SCORES["Technical Skills"],
        "explanation": skills_explanation,
        "formula": CATEGORY_FORMULAS["Technical Skills"],
        "improvement": skills_improvement,
        "status": skills_status,
    }
    if skills_improvement:
        improvement_areas.append({
            "category": "Technical Skills",
            "points_lost": CATEGORY_MAX_SCORES["Technical Skills"] - skills_score,
            "suggestion": skills_improvement,
        })

    # 4. Education (15 Marks)
    education_keywords = [
        "education",
        "b.tech",
        "bachelor",
        "degree",
        "university",
        "college",
        "master",
        "phd",
    ]

    matched_education_keyword = next(
        (kw for kw in education_keywords if kw in text_lower),
        None
    )
    education_score = 15 if matched_education_keyword else 0

    breakdown["Education"] = education_score
    score += education_score

    if education_score == 15:
        education_explanation = f"Detected academic credentials or education section ('{matched_education_keyword}'), earning full credit (+15/15)."
        education_improvement = None
        education_status = "full"
    else:
        education_explanation = "No education section or academic degree credentials detected (0/15)."
        education_improvement = "Include an Education section with your degree, university name, and graduation year."
        education_status = "missing"

    category_details["Education"] = {
        "score": education_score,
        "max": CATEGORY_MAX_SCORES["Education"],
        "explanation": education_explanation,
        "formula": CATEGORY_FORMULAS["Education"],
        "improvement": education_improvement,
        "status": education_status,
    }
    if education_improvement:
        improvement_areas.append({
            "category": "Education",
            "points_lost": CATEGORY_MAX_SCORES["Education"] - education_score,
            "suggestion": education_improvement,
        })

    # 5. Experience (15 Marks)
    experience_keywords = [
        "experience",
        "internship",
        "intern",
        "work history",
        "employment",
    ]

    matched_experience_keyword = next(
        (kw for kw in experience_keywords if kw in text_lower),
        None
    )
    experience_score = 15 if matched_experience_keyword else 0

    breakdown["Experience"] = experience_score
    score += experience_score

    if experience_score == 15:
        experience_explanation = f"Detected work experience or internship section ('{matched_experience_keyword}'), earning full credit (+15/15)."
        experience_improvement = None
        experience_status = "full"
    else:
        experience_explanation = "No work experience or internship history detected (0/15)."
        experience_improvement = "Add a Work Experience section detailing your previous professional roles, internships, and key contributions."
        experience_status = "missing"

    category_details["Experience"] = {
        "score": experience_score,
        "max": CATEGORY_MAX_SCORES["Experience"],
        "explanation": experience_explanation,
        "formula": CATEGORY_FORMULAS["Experience"],
        "improvement": experience_improvement,
        "status": experience_status,
    }
    if experience_improvement:
        improvement_areas.append({
            "category": "Experience",
            "points_lost": CATEGORY_MAX_SCORES["Experience"] - experience_score,
            "suggestion": experience_improvement,
        })

    # 6. Projects (20 Marks)
    project_keywords = [
        "projects",
        "project",
        "github repository",
        "portfolio",
    ]

    matched_project_keyword = next(
        (kw for kw in project_keywords if kw in text_lower),
        None
    )
    project_score = 20 if matched_project_keyword else 0

    breakdown["Projects"] = project_score
    score += project_score

    if project_score == 20:
        project_explanation = f"Detected technical projects or code repository references ('{matched_project_keyword}'), earning full credit (+20/20)."
        project_improvement = None
        project_status = "full"
    else:
        project_explanation = "No technical projects or project section detected (0/20)."
        project_improvement = "Add a Projects section showcasing 2-3 technical projects with tech stacks and links to GitHub or live demos."
        project_status = "missing"

    category_details["Projects"] = {
        "score": project_score,
        "max": CATEGORY_MAX_SCORES["Projects"],
        "explanation": project_explanation,
        "formula": CATEGORY_FORMULAS["Projects"],
        "improvement": project_improvement,
        "status": project_status,
    }
    if project_improvement:
        improvement_areas.append({
            "category": "Projects",
            "points_lost": CATEGORY_MAX_SCORES["Projects"] - project_score,
            "suggestion": project_improvement,
        })

    # 7. Readability & Formatting (10 Marks)
    readability_score = 0
    words = text.split()
    word_count = len(words)

    if word_count >= 100:
        readability_score += 5

    headings = [
        "education",
        "skills",
        "projects",
        "experience",
        "summary",
    ]

    heading_count = sum(1 for heading in headings if heading in text_lower)

    if heading_count >= 3:
        readability_score += 5

    breakdown["Readability"] = readability_score
    score += readability_score

    if readability_score == 10:
        readability_explanation = f"Well-structured resume: word count ({word_count} words, >= 100) and {heading_count} standard section headings (>= 3) earned full credit (+10/10)."
        readability_improvement = None
        readability_status = "full"
    elif word_count >= 100:
        readability_explanation = f"Resume length is sufficient ({word_count} words, +5/5), but fewer than 3 standard section headings were detected (found {heading_count}/3, 0/5)."
        readability_improvement = "Organize resume content under at least 3 standard section headings (e.g. Education, Skills, Experience, Projects)."
        readability_status = "partial"
    elif heading_count >= 3:
        readability_explanation = f"Section headings structure is clear ({heading_count} headings, +5/5), but word count is too brief ({word_count} words < 100 words, 0/5)."
        readability_improvement = "Expand your resume content to at least 100-400 words with descriptive bullet points."
        readability_status = "partial"
    else:
        readability_explanation = f"Resume is too brief ({word_count} words < 100) and lacks standard section headings (found {heading_count}/3 headings), earning 0/10."
        readability_improvement = "Add descriptive bullet points to reach at least 100 words and divide content under standard headings."
        readability_status = "missing"

    category_details["Readability"] = {
        "score": readability_score,
        "max": CATEGORY_MAX_SCORES["Readability"],
        "explanation": readability_explanation,
        "formula": CATEGORY_FORMULAS["Readability"],
        "improvement": readability_improvement,
        "status": readability_status,
    }
    if readability_improvement:
        improvement_areas.append({
            "category": "Readability",
            "points_lost": CATEGORY_MAX_SCORES["Readability"] - readability_score,
            "suggestion": readability_improvement,
        })

    # Overall explanation
    overall_explanation = (
        f"Overall resume score is {score}/100, calculated as the exact sum of 7 category scores: "
        f"Contact Information ({breakdown['Contact Information']}/10), "
        f"Professional Summary ({breakdown['Professional Summary']}/10), "
        f"Technical Skills ({breakdown['Technical Skills']}/20), "
        f"Education ({breakdown['Education']}/15), "
        f"Experience ({breakdown['Experience']}/15), "
        f"Projects ({breakdown['Projects']}/20), "
        f"and Readability ({breakdown['Readability']}/10)."
    )

    # Final Result
    return {
        "score": score,
        "breakdown": breakdown,
        "category_details": category_details,
        "overall_explanation": overall_explanation,
        "scoring_formula": SCORING_FORMULA_SUMMARY,
        "category_formulas": CATEGORY_FORMULAS,
        "improvement_areas": improvement_areas,
        "detected_skills": detected_skills,
        "word_count": word_count,
    }
