"""Prompt templates for LLM-powered features in Beacon Phase 3."""

REQUIREMENTS_EXTRACTION_PROMPT = """\
Analyze the following job description and extract structured requirements.

Return a JSON object with these fields:
- required_skills: list of required technical skills
- preferred_skills: list of preferred/nice-to-have skills
- seniority: the seniority level (junior, mid, senior, staff, lead, principal)
- keywords: list of important keywords and technologies mentioned
- responsibilities: list of key responsibilities
- culture_signals: list of any AI/ML culture signals mentioned

Job Description:
{job_description}
"""

RESUME_SYSTEM_PROMPT = """\
You are an expert resume writer specializing in technical roles. You create \
concise, impactful resumes that highlight relevant experience and quantified \
achievements. You tailor content to match specific job requirements while \
maintaining honesty. Use strong action verbs and quantify results where possible.\
"""

RESUME_TAILOR_PROMPT = """\
Create a tailored resume based on the following profile data and job requirements.

Target Job Requirements:
{requirements}

Candidate Profile:
{profile}

Instructions:
- Emphasize experiences and skills that match the job requirements
- Include quantified achievements where available
- Keep to {page_limit} page(s) — be concise
- Use clear section headers: Summary, Experience, Projects, Skills, Education
- For each experience, highlight 2-3 most relevant achievements
- Order skills by relevance to the job

Return the resume in markdown format.
"""

COVER_LETTER_SYSTEM_PROMPT = """\
You are an expert cover letter writer. You write compelling, authentic cover \
letters that connect a candidate's experience to a company's needs. You \
avoid generic language and instead demonstrate specific knowledge of the \
company and role. You write in a {tone} tone.\
"""

COVER_LETTER_PROMPT = """\
Write a cover letter for the following job, incorporating the candidate's \
profile and research about the company.

Job Title: {job_title}
Company: {company_name}

Company Research:
{company_context}

Candidate Profile Summary:
{profile_summary}

Job Requirements:
{requirements}

Instructions:
- Open with a compelling hook that shows knowledge of the company
- Connect the candidate's specific experience to the role requirements
- Reference the company's AI-first culture and tools where relevant
- Include 1-2 specific achievements that demonstrate relevant impact
- Close with enthusiasm and a clear call to action
- Keep to 3-4 paragraphs
- Write in a {tone} tone
"""

WHY_STATEMENT_PROMPT = """\
Write a compelling "Why {company_name}?" statement based on the following \
company research and candidate profile.

Company Research:
{company_context}

Candidate Profile Summary:
{profile_summary}

Instructions:
- Be specific about what attracts the candidate to this company
- Reference AI-first signals, leadership, and tools where relevant
- Connect the company's mission to the candidate's interests
- Keep to 2-3 sentences, punchy and authentic
"""

PORTFOLIO_SUMMARY_PROMPT = """\
Create a brief portfolio summary highlighting the candidate's most relevant \
projects for this role.

Job Requirements:
{requirements}

Candidate Projects:
{projects}

Instructions:
- Select the 3-5 most relevant projects
- For each, write 1-2 sentences connecting it to the job requirements
- Emphasize technologies and outcomes that match the role
- Format as a bulleted list
"""
