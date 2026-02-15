# Enrichment Interview Guide

A standalone guide for conducting structured professional accomplishment interviews. Any Claude session can use this document to interview a professional and capture accomplishments in rich detail — no Beacon code required.

## Purpose

This guide helps you:
1. Capture professional accomplishments using the STAR framework
2. Extract quantifiable metrics and specific details
3. Identify content angles for LinkedIn, blog posts, and profile updates
4. Produce structured output matching the Beacon `accomplishments` table format

## Interview Framework: STAR+

The core framework is STAR (Situation, Task, Action, Result), extended with additional dimensions for content generation:

### Phase 1: Opening

Start with an open-ended question:
> "Tell me about a professional accomplishment you're proud of — something where you made a meaningful impact."

Or, if enriching a specific role:
> "At [Company], what's something you accomplished that you'd want a hiring manager to know about?"

### Phase 2: STAR Deep-Dive

For each accomplishment, ask these follow-up questions:

**Situation / Context**
- What was the situation before you got involved?
- What problem or opportunity prompted this work?
- What was the scope? (team size, user count, budget, timeline)
- Was this assigned to you, or did you identify the opportunity?

**Task / Role**
- What was your specific role?
- Were you the sole owner, or part of a team?
- Who else was involved? (direct reports, stakeholders, leadership)
- What was expected of you vs. what you actually delivered?

**Action / What You Did**
- Walk me through the steps you took.
- What technologies, tools, or frameworks did you use?
- What decisions did you make, and why?
- What alternatives did you consider but reject?
- What was the hardest part?

**Result / Impact**
- What was the measurable outcome?
- Can you quantify it? (revenue, time saved, users impacted, efficiency gains)
- What feedback did you receive? (from leadership, users, stakeholders)
- Is this work still in use today?
- What would have happened if you hadn't done this?

### Phase 3: Extended Questions

These add depth for content generation:

**Timeline**
- How long did this take from start to finish?
- Were there distinct phases?

**Challenges**
- What obstacles did you face?
- What surprised you?
- What would you do differently next time?

**Learning**
- What did you learn from this experience?
- How did it change your approach going forward?
- What advice would you give someone facing a similar challenge?

**Content Angles**
- If you wrote a blog post about this, what would the title be?
- What's the one-sentence takeaway someone else could learn from?
- Is there a "before and after" story here?

## Follow-Up Trees by Accomplishment Type

### Technical Implementation
```
"I built/implemented [system]"
├── What problem did it solve?
├── What was the architecture?
├── What technologies did you evaluate?
├── How many users/systems does it serve?
├── What was the performance improvement?
└── How do you maintain/monitor it?
```

### Process Improvement
```
"I improved/optimized [process]"
├── What did the process look like before?
├── What metrics were you tracking?
├── What changes did you make?
├── What was the before/after comparison?
├── How did you get buy-in?
└── How did you measure success?
```

### Leadership / Management
```
"I led/managed [team/project]"
├── How large was the team?
├── What was the team's charter?
├── How did you handle conflicts/challenges?
├── What was your management philosophy?
├── What did you learn about leadership?
└── What results did the team achieve?
```

### AI / ML Implementation
```
"I deployed/built [AI system]"
├── What was the use case?
├── What model/approach did you use?
├── How did you evaluate performance?
├── How did you handle edge cases?
├── What was the adoption rate?
├── How did you address concerns about AI?
└── What governance/policies did you create?
```

### Organizational Change
```
"I rolled out/adopted [tool/process]"
├── What was the status quo?
├── How did you make the case for change?
├── Who were the champions and resisters?
├── What training/support did you provide?
├── What was the adoption curve?
├── What metrics improved?
└── What would you do differently?
```

## Output Format

After the interview, produce structured JSON matching the `accomplishments` table:

```json
{
  "raw_statement": "Led Copilot Premium rollout to 50,000 users",
  "work_experience_id": null,
  "context": "Ohio State needed to adopt AI tools across a 50,000+ person institution with varying technical literacy and departmental needs",
  "action": "Built governance framework, created training materials, piloted with early adopters, designed feedback loops, iterated on policies based on usage data",
  "result": "Enterprise-wide adoption with measurable productivity improvements across departments",
  "metrics": "50,000 users, 12 departments, 3-month rollout timeline",
  "technologies": "Microsoft 365 Copilot, Microsoft Copilot Studio, Workfront",
  "stakeholders": "CIO office, department heads, IT security, end users",
  "timeline": "3 months planning + 3 months rollout",
  "challenges": "Resistance from non-technical staff, security concerns, inconsistent access across departments",
  "learning": "Change management is harder than technical implementation. Early champions in each department were the key to adoption.",
  "content_angles": "Blog: 'What I Learned Rolling Out AI to 50,000 Users'. LinkedIn: Post about governance frameworks. Profile: 'Led enterprise Copilot adoption for 50K-person institution'."
}
```

## Missing Info Checklist

After interviews, check the profile for these common gaps:

- [ ] Education entries (degrees, institutions, dates)
- [ ] Quantified metrics for each work experience (numbers, percentages)
- [ ] Technologies listed for each role
- [ ] At least 3 key achievements per role
- [ ] Description for each work experience
- [ ] At least one public project with repo URL
- [ ] Publications, talks, or conference presentations
- [ ] Skills across all categories (language, framework, tool, domain)

## Content Generation from Enriched Accomplishments

Each enriched accomplishment can produce:

1. **LinkedIn Post** — Use the hook (surprising result or counterintuitive insight) + 3-4 paragraphs of the story + takeaway
2. **Blog Post Outline** — Use the full STAR narrative as the structure, expand with context and lessons learned
3. **Profile Bullet Point** — Concise, metrics-driven: "Led [action] resulting in [quantified result] using [technologies]"
4. **Resume Achievement** — Same as profile bullet but tailored to specific job requirements

## TODO Template for Artifacts

After an interview session, create a TODO list of supporting materials to gather:

- [ ] Screenshots or demos of the work (sanitized if needed)
- [ ] Links to public-facing results (blog posts, repos, presentations)
- [ ] Testimonials or feedback quotes (with permission)
- [ ] Before/after metrics or visualizations
- [ ] Architecture diagrams or technical documentation
- [ ] Presentation slides from talks about this work

## Using This Guide

### With Beacon CLI
```bash
# Start an enrichment interview
beacon presence enrich

# Enrich a specific work experience
beacon presence enrich --work-id 1

# List what's missing from the profile
beacon presence enrich --list-gaps

# Generate content after enrichment
beacon presence enrich --generate-content
```

### Without Beacon (Standalone Claude Session)
1. Share this document with Claude
2. Say: "I want to do an enrichment interview about my work"
3. Claude will use the framework above to conduct the interview
4. Copy the output JSON and save it, or paste it into `beacon presence enrich` later
