# Personal Website — Framework Recommendation

## TL;DR: Use Astro + Vercel (free tier)

After researching what developers and data scientists are using in 2025/2026, here's the recommendation:

### Why Astro

- **Content-first architecture** — Built for blogs, portfolios, and docs. Your site is primarily content (projects, blog posts, resume), not an interactive app.
- **Zero JavaScript by default** — Pages ship as pure HTML unless you explicitly add interactivity. Perfect Lighthouse scores out of the box.
- **Markdown-native** — Write blog posts in Markdown, Astro renders them. No CMS needed.
- **Island architecture** — When you *do* want interactivity (e.g., an interactive project demo), you can add React/Svelte components that only load where needed.
- **Fast builds** — Not as fast as Hugo, but fast enough for a personal site. Much more flexible than Hugo.
- **Modern DX** — TypeScript, Tailwind, hot reload, component-based. Feels like writing a modern app, not fighting a template engine.

### Why Not Hugo

Hugo is faster but its Go templating language is clunky and unfamiliar. For someone who works primarily in Python and is learning modern JS tooling, Astro's JSX-like syntax is more transferable. Hugo is better if you have 10,000+ pages; you don't.

### Why Not Next.js

Overkill for a portfolio site. Next.js is a full React framework designed for dynamic web apps. Your site is 95% static content. Next.js adds unnecessary complexity and ships ~40-50KB of runtime JavaScript even for a static page.

### Hosting: Vercel Free Tier

You already have a Vercel hobby account. Astro deploys to Vercel with zero configuration. Free tier includes:
- Custom domain support
- Automatic HTTPS
- Git-based deploys (push to main → site updates)
- Analytics (basic)

### Domain

Recommend: **michaelpawlus.dev** (~$12/year on Cloudflare or Google Domains)
- `.dev` signals developer/technical focus
- Clean, memorable, professional
- `.com` is fine too but `.dev` is more aligned with target audience (AI-first tech companies)

You could also start with `michaelpawlus.vercel.app` (free) and add a custom domain later.

### Site Structure (V1 — Minimal)

```
/                     → Home (brief bio + what you do now + featured projects)
/about                → Full story (the non-traditional path narrative)
/projects             → Project cards (Beacon, work projects sanitized, etc.)
/blog                 → Blog posts (Markdown files)
/resume               → Always-current resume (generated from data)
```

### What Makes This a Portfolio Piece

Building the site with Astro demonstrates:
- Modern frontend tooling knowledge
- Component-based architecture
- Static site optimization
- CI/CD (automatic deployment from GitHub)
- Content management (Markdown-driven)

And the site itself is the display case for everything else you build.

### Existing GitHub Pages Blog

Archive the old Jekyll blog:
1. Keep the repo but rename it (e.g., `michaelpawlus/old-blog-archive`)
2. Remove the GitHub Pages deployment
3. The new Astro site can live at `michaelpawlus/michaelpawlus.dev` and deploy to Vercel
4. If you ever want to reference old posts, they're still in the archive repo

### Getting Started

```bash
# Create new Astro site
npm create astro@latest michaelpawlus.dev

# During setup:
#   Template: Blog
#   TypeScript: Yes (strict)
#   Install dependencies: Yes

# Add Tailwind
npx astro add tailwind

# Add Vercel adapter
npx astro add vercel

# Start developing
cd michaelpawlus.dev
npm run dev
```

Then connect the GitHub repo to Vercel for automatic deployments.
