"""Unit tests for explainable resume scoring (Issue #31).

Tests that:
- Every score has an explanation.
- Category scores follow a documented formula.
- Overall scoring is consistent.
- Users can identify areas requiring improvement.
"""

import unittest
from analyzer.resume_scorer import (
    calculate_resume_score,
    CATEGORY_MAX_SCORES,
    CATEGORY_FORMULAS,
    SCORING_FORMULA_SUMMARY,
)


class TestExplainableScoring(unittest.TestCase):

    def setUp(self):
        self.perfect_resume = (
            "Alex Smith\n"
            "alex.smith@example.com | +1 555-123-4567\n"
            "PROFESSIONAL SUMMARY\n"
            "Experienced software engineer specializing in scalable cloud applications.\n"
            "EDUCATION\n"
            "Bachelor of Science in Computer Science, Example University\n"
            "WORK EXPERIENCE\n"
            "Senior Backend Engineer at TechCorp. Developed microservices with Python, Flask, and Docker.\n"
            "PROJECTS\n"
            "AI Resume Analyzer - Python, Flask, React, SQL, MongoDB, PostgreSQL, Git, GitHub, Machine Learning, Deep Learning\n"
            "SKILLS\n"
            "Python, Java, C++, JavaScript, HTML, CSS, SQL, Flask, Django, React, MongoDB, Git, GitHub\n"
            "Additional details describing architectural patterns, unit testing, continuous integration, "
            "deployment pipelines, team leadership, mentoring junior developers, and code quality initiatives. "
            "Successfully delivered multiple end-to-end commercial web applications with high availability and performance."
        )

        self.minimal_resume = (
            "Jane Doe\n"
            "jane@example.com\n"
            "Education: Example College\n"
        )

    def test_category_scores_follow_documented_formula(self):
        """Acceptance Criteria 2: Category scores follow a documented formula."""
        # Max scores must sum to exactly 100
        self.assertEqual(sum(CATEGORY_MAX_SCORES.values()), 100)

        # All 7 categories must have documented formulas
        for category, max_points in CATEGORY_MAX_SCORES.items():
            self.assertIn(category, CATEGORY_FORMULAS)
            self.assertIsInstance(CATEGORY_FORMULAS[category], str)
            self.assertGreater(len(CATEGORY_FORMULAS[category]), 10)

        # Overall formula summary exists and mentions 100
        self.assertIn("100", SCORING_FORMULA_SUMMARY)

    def test_every_score_has_an_explanation(self):
        """Acceptance Criteria 1: Every score has an explanation."""
        result = calculate_resume_score(self.minimal_resume)

        self.assertIn("overall_explanation", result)
        self.assertIsInstance(result["overall_explanation"], str)
        self.assertIn(str(result["score"]), result["overall_explanation"])

        self.assertIn("category_details", result)
        for category in CATEGORY_MAX_SCORES:
            self.assertIn(category, result["category_details"])
            detail = result["category_details"][category]
            self.assertIn("score", detail)
            self.assertIn("max", detail)
            self.assertIn("explanation", detail)
            self.assertIn("formula", detail)
            self.assertIsInstance(detail["explanation"], str)
            self.assertGreater(len(detail["explanation"]), 5)

    def test_contact_information_scoring_rules(self):
        """Contact info formula: Email (5) + Phone (5) = 10 max."""
        # Both email and phone
        res_both = calculate_resume_score("user@example.com +1 234 567 8901")
        self.assertEqual(res_both["breakdown"]["Contact Information"], 10)
        self.assertIn("full credit", res_both["category_details"]["Contact Information"]["explanation"].lower())

        # Email only
        res_email = calculate_resume_score("user@example.com")
        self.assertEqual(res_email["breakdown"]["Contact Information"], 5)
        self.assertIn("phone number was detected", res_email["category_details"]["Contact Information"]["explanation"])

        # Phone only
        res_phone = calculate_resume_score("+1 234 567 8901")
        self.assertEqual(res_phone["breakdown"]["Contact Information"], 5)
        self.assertIn("email address was detected", res_phone["category_details"]["Contact Information"]["explanation"])

        # Neither
        res_none = calculate_resume_score("Just plain text with no contact")
        self.assertEqual(res_none["breakdown"]["Contact Information"], 0)
        self.assertIn("0/10", res_none["category_details"]["Contact Information"]["explanation"])

    def test_technical_skills_scoring_rules(self):
        """Technical skills formula: 2 pts per detected skill, capped at 20."""
        # 3 skills -> 6 points
        res_3 = calculate_resume_score("Skills: Python, SQL, Git")
        self.assertEqual(res_3["breakdown"]["Technical Skills"], 6)
        self.assertIn("6/20", res_3["category_details"]["Technical Skills"]["explanation"])

        # 11 skills -> 20 points (capped)
        eleven_skills = "Python, Java, C++, JavaScript, HTML, CSS, SQL, Flask, Django, React, Git"
        res_11 = calculate_resume_score(eleven_skills)
        self.assertEqual(res_11["breakdown"]["Technical Skills"], 20)
        self.assertIn("full credit", res_11["category_details"]["Technical Skills"]["explanation"].lower())

        # C++ must not double-count as both C++ and C
        res_cpp = calculate_resume_score("Proficient in C++")
        self.assertEqual(res_cpp["detected_skills"], ["C++"])
        self.assertEqual(res_cpp["breakdown"]["Technical Skills"], 2)

        # Modern stack skills in dictionary (Go, TypeScript, Docker, Kubernetes, AWS, etc.)
        modern_stack = "Go, TypeScript, React, Node.js, Docker, Kubernetes, AWS, Terraform, PostgreSQL, GraphQL"
        res_modern = calculate_resume_score(modern_stack)
        self.assertEqual(res_modern["breakdown"]["Technical Skills"], 20)

        # Soft skills must not count as Technical Skills
        res_soft = calculate_resume_score("Communication, Leadership, Teamwork, Problem Solving")
        self.assertEqual(res_soft["detected_skills"], [])
        self.assertEqual(res_soft["breakdown"]["Technical Skills"], 0)

    def test_readability_formatting_scoring_rules(self):
        """Readability formula: >= 100 words (5 pts) + >= 3 headings (5 pts)."""
        headings = "Education\nSkills\nProjects\nExperience\n"

        # Word count >= 100 and >= 3 headings -> 10 pts
        long_text = headings + ("word " * 110)
        res_full = calculate_resume_score(long_text)
        self.assertEqual(res_full["breakdown"]["Readability"], 10)

        # Word count >= 100 but no headings -> 5 pts
        res_words_only = calculate_resume_score("word " * 110)
        self.assertEqual(res_words_only["breakdown"]["Readability"], 5)
        self.assertIn("fewer than 3", res_words_only["category_details"]["Readability"]["explanation"])

        # Headings only (< 100 words) -> 5 pts
        res_headings_only = calculate_resume_score(headings + "brief text")
        self.assertEqual(res_headings_only["breakdown"]["Readability"], 5)
        self.assertIn("too brief", res_headings_only["category_details"]["Readability"]["explanation"])

    def test_overall_scoring_is_consistent(self):
        """Acceptance Criteria 3: Overall scoring is consistent."""
        test_samples = [
            self.perfect_resume,
            self.minimal_resume,
            "",
            "Random words with no sections or skills",
            "john@example.com B.Tech in CS Python Flask",
        ]

        for sample in test_samples:
            with self.subTest(sample=sample[:30]):
                res1 = calculate_resume_score(sample)
                res2 = calculate_resume_score(sample)

                # Consistent & deterministic
                self.assertEqual(res1["score"], res2["score"])
                self.assertEqual(res1["breakdown"], res2["breakdown"])

                # Exact sum of category breakdown
                expected_sum = sum(res1["breakdown"].values())
                self.assertEqual(res1["score"], expected_sum)

                # Bounded between 0 and 100
                self.assertGreaterEqual(res1["score"], 0)
                self.assertLessEqual(res1["score"], 100)

    def test_users_can_identify_areas_requiring_improvement(self):
        """Acceptance Criteria 4: Users can identify areas requiring improvement."""
        # Minimal resume misses summary, experience, projects, skills, etc.
        result = calculate_resume_score(self.minimal_resume)

        improvement_areas = result.get("improvement_areas", [])
        self.assertIsInstance(improvement_areas, list)
        self.assertGreater(len(improvement_areas), 0)

        # Each improvement area has category, points lost, and specific actionable suggestion
        for area in improvement_areas:
            self.assertIn("category", area)
            self.assertIn("points_lost", area)
            self.assertIn("suggestion", area)
            self.assertGreater(area["points_lost"], 0)
            self.assertIsInstance(area["suggestion"], str)
            self.assertGreater(len(area["suggestion"]), 10)

        # Perfect resume has 0 improvement areas
        perfect_result = calculate_resume_score(self.perfect_resume)
        self.assertEqual(perfect_result["score"], 100)
        self.assertEqual(len(perfect_result["improvement_areas"]), 0)


if __name__ == "__main__":
    unittest.main()
