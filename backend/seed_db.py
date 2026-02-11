"""Seed the database with sample articles from frontend.py."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import from app
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker, engine
from app.models.base import Base
from app.models.article import Article


# Sample articles from frontend.py
SAMPLE_ARTICLES = [
    {
        "title": "Jake Sullivan interview on AI chips and Nvidia",
        "url": "https://www.theverge.com/policy/856815/jake-sullivan-interview-ai-chips-nvidia-trump",
        "org": "The Verge",
        "org_initials": "TV",
        "logo_url": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQDwFmAm4KIoRt16UsLNsoQhRwJhvPnASFuXQ&s",
        "summary": "✨ The interview explores AI chip export policy, Nvidia's role, and how U.S. strategy could shift under new political pressures.",
        "date": "2026-01-29",
        "author": "The Verge Staff",
        "tags": ["Policy", "Editors Choice"],
        "content": "National Security Advisor Jake Sullivan discusses the complex landscape of AI chip exports and Nvidia's strategic position in the global AI race.",
    },
    {
        "title": "UCLA AI policies should add more faculty regulations",
        "url": "https://dailybruin.com/2026/02/01/opinion-uclas-ai-policies-must-be-consistent-include-more-regulations-on-faculty-use",
        "org": "Daily Bruin",
        "org_initials": "DB",
        "logo_url": "https://wp.dailybruin.com/images/2017/03/db-logo.png",
        "summary": "✨ The piece argues for clearer, consistent faculty rules and more guardrails around academic AI use.",
        "date": "2026-02-01",
        "author": "Daily Bruin Opinion",
        "tags": ["Policy"],
        "content": "An opinion piece calling for UCLA to establish more comprehensive and consistent AI policies for faculty members.",
    },
    {
        "title": "Meta AI team delivers key internal models",
        "url": "https://www.reuters.com/technology/metas-new-ai-team-has-delivered-first-key-models-internally-this-month-cto-says-2026-01-21/",
        "org": "Reuters",
        "org_initials": "R",
        "logo_url": "https://static.wikia.nocookie.net/logopedia/images/d/db/Reuters_2024_vertical.svg/revision/latest/scale-to-width-down/250?cb=20240525042050",
        "summary": "✨ Meta's new AI team reportedly delivered internal models this month, showing early traction in its core model roadmap.",
        "date": "2026-01-21",
        "author": "Reuters Staff",
        "tags": ["Models"],
        "content": "Meta's newly formed AI team has successfully delivered its first key models internally, marking significant progress in the company's AI development roadmap.",
    },
    {
        "title": "Open models and data tools accelerate AI",
        "url": "https://blogs.nvidia.com/blog/open-models-data-tools-accelerate-ai/",
        "org": "NVIDIA Blog",
        "org_initials": "NV",
        "logo_url": "https://www.nvidia.com/content/dam/en-zz/Solutions/about-nvidia/logo-and-brand/02-nvidia-logo-color-grn-500x200-4c25-p@2x.png",
        "summary": "✨ NVIDIA highlights open models and data tooling as catalysts for faster AI experimentation and deployment.",
        "date": "2026-01-28",
        "author": "NVIDIA Blog",
        "tags": ["Models"],
        "content": "NVIDIA explores how open-source models and data tools are accelerating AI development and enabling faster experimentation across the industry.",
    },
    {
        "title": "OpenAI retires GPT-4o for users",
        "url": "https://mashable.com/article/openai-retiring-chatgpt-gpt-4o-users-heartbroken",
        "org": "Mashable",
        "org_initials": "M",
        "logo_url": "https://icon-icons.com/download-file?file=https%3A%2F%2Fimages.icon-icons.com%2F2699%2FPNG%2F512%2Fmashable_logo_icon_168991.png&id=168991&pack_or_individual=pack",
        "summary": "✨ OpenAI is retiring GPT-4o, and users are reacting to what comes next for ChatGPT capabilities.",
        "date": "2026-01-30",
        "author": "Mashable Staff",
        "tags": ["Models"],
        "content": "OpenAI announces the retirement of GPT-4o, leaving users to speculate about the future direction of ChatGPT's capabilities.",
    },
    {
        "title": "Google's Sage agentic AI research and SEO impact",
        "url": "https://www.searchenginejournal.com/googles-sage-agentic-ai-research-what-it-means-for-seo/566215/",
        "org": "Search Engine Journal",
        "org_initials": "SEJ",
        "logo_url": "https://media.licdn.com/dms/image/v2/C560BAQHWovXmoQJ13w/company-logo_200_200/company-logo_200_200/0/1630601143517/search_engine_journal_logo?e=2147483647&v=beta&t=k2IvrbFy2aGM9WnsnOxJygSckiGDdisTahpgIwy8lYE",
        "summary": "✨ Google's Sage research points to agentic AI workflows that could reshape SEO strategies and search behavior.",
        "date": "2026-01-31",
        "author": "SEJ Staff",
        "tags": ["Research"],
        "content": "Google's research into agentic AI systems has significant implications for the future of search engine optimization and user search behavior.",
    },
    {
        "title": "OpenAI investment was never a commitment, Huang says",
        "url": "https://www.bloomberg.com/news/articles/2026-02-01/openai-investment-was-never-a-commitment-nvidia-s-huang-says",
        "org": "Bloomberg",
        "org_initials": "B",
        "logo_url": "https://e7.pngegg.com/pngimages/727/671/png-clipart-bloomberg-round-logo-icons-logos-emojis-iconic-brands-thumbnail.png",
        "summary": "✨ Nvidia's CEO says OpenAI investment talk was never a firm commitment, reframing expectations in the market.",
        "date": "2026-02-01",
        "author": "Bloomberg Staff",
        "tags": ["Companies", "Reader Favorite"],
        "content": "Nvidia CEO Jensen Huang clarifies that discussions about OpenAI investment were never a firm commitment, addressing market speculation.",
    },
    {
        "title": "Peloton layoffs and cost cutting in 2026",
        "url": "https://www.theverge.com/gadgets/871422/peloton-layoffs-cost-cutting-2026",
        "org": "The Verge",
        "org_initials": "TV",
        "logo_url": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQDwFmAm4KIoRt16UsLNsoQhRwJhvPnASFuXQ&s",
        "summary": "✨ Peloton's latest layoffs and cost cuts highlight pressure to streamline hardware operations in 2026.",
        "date": "2026-01-31",
        "author": "The Verge Staff",
        "tags": ["Hardware", "Infrastructure"],
        "content": "Peloton announces significant layoffs and cost-cutting measures as the company faces pressure to streamline its hardware operations.",
    },
    {
        "title": "Smart glasses seen as first major AI hardware",
        "url": "https://finance.yahoo.com/news/big-tech-thinks-smart-glasses-will-be-the-first-major-piece-of-ai-hardware-105218224.html",
        "org": "Yahoo Finance",
        "org_initials": "YF",
        "logo_url": "https://images-cdn3.welcomesoftware.com/assets/yahoo+finance.jpg/Zz0yNWFjNTk0NjlkMmQxMWVmYjhlNjFlYTY2MTI5N2IyNg==?width=1200",
        "summary": "✨ Major tech firms see smart glasses as the first widely adopted AI hardware category.",
        "date": "2026-01-31",
        "author": "Yahoo Finance",
        "tags": ["Hardware", "Infrastructure"],
        "content": "Big tech companies are betting that smart glasses will be the first major consumer AI hardware product to achieve widespread adoption.",
    },
    {
        "title": "Moltbot highlights cybersecurity risks for AI agents",
        "url": "https://www.axios.com/2026/01/29/moltbot-cybersecurity-ai-agent-risks",
        "org": "Axios",
        "org_initials": "AX",
        "logo_url": "https://tannerfriedman.com/wp-content/uploads/2022/08/91-913031_axios-axios-logo-hd-png-download.png",
        "summary": "✨ Moltbot spotlights how AI agents can be misused, raising new concerns for cybersecurity teams.",
        "date": "2026-01-29",
        "author": "Axios Staff",
        "tags": ["Security", "Misuse"],
        "content": "New research on Moltbot reveals significant cybersecurity risks posed by AI agents and their potential for misuse.",
    },
]


async def seed_articles(session: AsyncSession) -> None:
    """Insert sample articles into the database."""
    print("🌱 Seeding database with sample articles...")

    articles = [Article(**data) for data in SAMPLE_ARTICLES]
    session.add_all(articles)
    await session.commit()

    print(f"✅ Successfully seeded {len(SAMPLE_ARTICLES)} articles!\n")
    for i, a in enumerate(articles, 1):
        print(f"  {i}. {a.title} ({', '.join(a.tags)})")


async def main(force: bool = False):
    """Main seeding function.

    Args:
        force: If True, skip the confirmation prompt (useful for CI / Docker).
    """
    print("=" * 60)
    print("Neural News (N²) Database Seeder")
    print("=" * 60)

    from app.config import settings

    db_url = settings.database_url
    is_cloud = "localhost" not in db_url and "127.0.0.1" not in db_url

    if is_cloud:
        print("\n⚠️  WARNING: You are connected to a CLOUD database!")
        print(f"   URL: {db_url[:40]}...")
        print("   This will DROP ALL TABLES and delete all data.\n")
    else:
        print(f"\n📍 Target database: local ({db_url[:60]}...)")

    if not force:
        confirm = input("Type 'yes' to proceed, anything else to abort: ").strip().lower()
        if confirm != "yes":
            print("\n🚫 Aborted. No changes were made.")
            sys.exit(0)

    try:
        # Drop and recreate the articles table so schema matches the model
        print("\n📊 Dropping old tables and recreating from model...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Database tables recreated with current schema")
        
        # Seed data
        async with async_session_maker() as session:
            await seed_articles(session)
        
        print("\n" + "=" * 60)
        print("🎉 Seeding complete!")
        print("=" * 60)
        print("\nYou can now start the server with:")
        print("  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        print("\nThen visit http://localhost:8000 to see your articles!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    force_flag = "--force" in sys.argv or "-f" in sys.argv
    asyncio.run(main(force=force_flag))
