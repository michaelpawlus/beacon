"""Tests for job highlights extraction."""

from beacon.research.job_highlights import extract_highlights


class TestSalaryExtraction:
    def test_range_with_commas(self):
        desc = "The base salary range for this role is $149,000 - $250,000 annually."
        hl = extract_highlights(desc)
        assert hl["salary_min"] == 149000
        assert hl["salary_max"] == 250000
        assert "$149,000" in hl["salary_raw"]

    def test_range_with_dash(self):
        desc = "Pay range: $120,000-$180,000 per year."
        hl = extract_highlights(desc)
        assert hl["salary_min"] == 120000
        assert hl["salary_max"] == 180000

    def test_range_with_en_dash(self):
        desc = "Compensation: $100,000\u2013$200,000"
        hl = extract_highlights(desc)
        assert hl["salary_min"] == 100000
        assert hl["salary_max"] == 200000

    def test_no_salary(self):
        desc = "We offer competitive compensation and great benefits."
        hl = extract_highlights(desc)
        assert hl["salary_min"] is None
        assert hl["salary_max"] is None
        assert hl["salary_raw"] is None

    def test_small_numbers_ignored(self):
        desc = "We offer $50 gift cards and a salary of $150,000 - $200,000."
        hl = extract_highlights(desc)
        assert hl["salary_min"] == 150000
        assert hl["salary_max"] == 200000

    def test_salary_in_html(self):
        desc = '<span>$235,000</span><span class="divider">&mdash;</span><span>$376,000 USD</span>'
        hl = extract_highlights(desc)
        assert hl["salary_min"] == 235000
        assert hl["salary_max"] == 376000

    def test_salary_with_html_entities(self):
        desc = "Salary: $100,000&ndash;$150,000 annually."
        hl = extract_highlights(desc)
        assert hl["salary_min"] == 100000
        assert hl["salary_max"] == 150000


class TestAIToolsExtraction:
    def test_finds_llm_mentions(self):
        desc = "Experience with LLMs and RAG systems required. Familiarity with Claude API preferred."
        hl = extract_highlights(desc)
        assert "LLMs" in hl["ai_tools"]
        assert "RAG" in hl["ai_tools"]
        assert "Claude" in hl["ai_tools"]

    def test_finds_ml_frameworks(self):
        desc = "We use PyTorch and TensorFlow for model training, with MLflow for tracking."
        hl = extract_highlights(desc)
        assert "PyTorch" in hl["ai_tools"]
        assert "TensorFlow" in hl["ai_tools"]
        assert "MLflow" in hl["ai_tools"]

    def test_finds_copilot(self):
        desc = "All engineers use GitHub Copilot and Cursor for development."
        hl = extract_highlights(desc)
        assert "GitHub Copilot" in hl["ai_tools"]
        assert "Cursor" in hl["ai_tools"]

    def test_no_ai_tools(self):
        desc = "Looking for an office manager with strong organizational skills."
        hl = extract_highlights(desc)
        assert hl["ai_tools"] == []

    def test_deduplicates_llm_variants(self):
        desc = "Work with LLMs and large language models daily."
        hl = extract_highlights(desc)
        llm_count = sum(1 for t in hl["ai_tools"] if t == "LLMs")
        assert llm_count == 1


class TestExperienceExtraction:
    def test_years_of_experience(self):
        desc = "5+ years of experience in data engineering."
        hl = extract_highlights(desc)
        assert hl["experience_years"] == "5+"

    def test_multiple_experience_mentions(self):
        desc = "3+ years of Python experience. 5+ years of data engineering experience."
        hl = extract_highlights(desc)
        assert hl["experience_years"] == "5+"

    def test_no_experience_mentioned(self):
        desc = "Join our team of passionate engineers."
        hl = extract_highlights(desc)
        assert hl["experience_years"] is None


class TestKeyRequirements:
    def test_finds_tech_stack(self):
        desc = "Must have experience with Python, SQL, Spark, and Snowflake."
        hl = extract_highlights(desc)
        assert "Python" in hl["key_requirements"]
        assert "SQL" in hl["key_requirements"]
        assert "Spark" in hl["key_requirements"]
        assert "Snowflake" in hl["key_requirements"]

    def test_finds_cloud_platforms(self):
        desc = "Experience with AWS and Kubernetes required. GCP a plus."
        hl = extract_highlights(desc)
        assert "AWS" in hl["key_requirements"]
        assert "Kubernetes" in hl["key_requirements"]
        assert "GCP" in hl["key_requirements"]


class TestEmptyInput:
    def test_empty_string(self):
        hl = extract_highlights("")
        assert hl["salary_min"] is None
        assert hl["salary_max"] is None
        assert hl["salary_raw"] is None
        assert hl["ai_tools"] == []
        assert hl["experience_years"] is None
        assert hl["key_requirements"] == []

    def test_none_like(self):
        hl = extract_highlights("")
        assert isinstance(hl, dict)
        assert len(hl) == 6
