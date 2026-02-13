from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json


ARTICLES = [
    {
        "id": 1,
        "title": "Jake Sullivan interview on AI chips and Nvidia",
        "url": "https://www.theverge.com/policy/856815/jake-sullivan-interview-ai-chips-nvidia-trump",
        "org": "The Verge",
        "org_initials": "TV",
        "logo_url": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQDwFmAm4KIoRt16UsLNsoQhRwJhvPnASFuXQ&s",
        "summary": "✨ The interview explores AI chip export policy, Nvidia's role, and how U.S. strategy could shift under new political pressures.",
        "date": "2026-01-29",
        "author": "The Verge Staff",
        "tags": ["Policy", "Editors Choice"],
    },
    {
        "id": 2,
        "title": "UCLA AI policies should add more faculty regulations",
        "url": "https://dailybruin.com/2026/02/01/opinion-uclas-ai-policies-must-be-consistent-include-more-regulations-on-faculty-use",
        "org": "Daily Bruin",
        "org_initials": "DB",
        "logo_url": "https://wp.dailybruin.com/images/2017/03/db-logo.png",
        "summary": "✨ The piece argues for clearer, consistent faculty rules and more guardrails around academic AI use.",
        "date": "2026-02-01",
        "author": "Daily Bruin Opinion",
        "tags": ["Policy"],
    },
    {
        "id": 3,
        "title": "Meta AI team delivers key internal models",
        "url": "https://www.reuters.com/technology/metas-new-ai-team-has-delivered-first-key-models-internally-this-month-cto-says-2026-01-21/",
        "org": "Reuters",
        "org_initials": "R",
        "logo_url": "https://static.wikia.nocookie.net/logopedia/images/d/db/Reuters_2024_vertical.svg/revision/latest/scale-to-width-down/250?cb=20240525042050",
        "summary": "✨ Meta's new AI team reportedly delivered internal models this month, showing early traction in its core model roadmap.",
        "date": "2026-01-21",
        "author": "Reuters Staff",
        "tags": ["Models"],
    },
    {
        "id": 4,
        "title": "Open models and data tools accelerate AI",
        "url": "https://blogs.nvidia.com/blog/open-models-data-tools-accelerate-ai/",
        "org": "NVIDIA Blog",
        "org_initials": "NV",
        "logo_url": "https://www.nvidia.com/content/dam/en-zz/Solutions/about-nvidia/logo-and-brand/02-nvidia-logo-color-grn-500x200-4c25-p@2x.png",
        "summary": "✨ NVIDIA highlights open models and data tooling as catalysts for faster AI experimentation and deployment.",
        "date": "2026-01-28",
        "author": "NVIDIA Blog",
        "tags": ["Models"],
    },
    {
        "id": 5,
        "title": "OpenAI retires GPT-4o for users",
        "url": "https://mashable.com/article/openai-retiring-chatgpt-gpt-4o-users-heartbroken",
        "org": "Mashable",
        "org_initials": "M",
        "logo_url": "https://icon-icons.com/download-file?file=https%3A%2F%2Fimages.icon-icons.com%2F2699%2FPNG%2F512%2Fmashable_logo_icon_168991.png&id=168991&pack_or_individual=pack",
        "summary": "✨ OpenAI is retiring GPT-4o, and users are reacting to what comes next for ChatGPT capabilities.",
        "date": "2026-01-30",
        "author": "Mashable Staff",
        "tags": ["Models"],
    },
    {
        "id": 6,
        "title": "Google's Sage agentic AI research and SEO impact",
        "url": "https://www.searchenginejournal.com/googles-sage-agentic-ai-research-what-it-means-for-seo/566215/",
        "org": "Search Engine Journal",
        "org_initials": "SEJ",
        "logo_url": "https://media.licdn.com/dms/image/v2/C560BAQHWovXmoQJ13w/company-logo_200_200/company-logo_200_200/0/1630601143517/search_engine_journal_logo?e=2147483647&v=beta&t=k2IvrbFy2aGM9WnsnOxJygSckiGDdisTahpgIwy8lYE",
        "summary": "✨ Google's Sage research points to agentic AI workflows that could reshape SEO strategies and search behavior.",
        "date": "2026-01-31",
        "author": "SEJ Staff",
        "tags": ["Research"],
    },
    {
        "id": 7,
        "title": "OpenAI investment was never a commitment, Huang says",
        "url": "https://www.bloomberg.com/news/articles/2026-02-01/openai-investment-was-never-a-commitment-nvidia-s-huang-says",
        "org": "Bloomberg",
        "org_initials": "B",
        "logo_url": "https://e7.pngegg.com/pngimages/727/671/png-clipart-bloomberg-round-logo-icons-logos-emojis-iconic-brands-thumbnail.png",
        "summary": "✨ Nvidia's CEO says OpenAI investment talk was never a firm commitment, reframing expectations in the market.",
        "date": "2026-02-01",
        "author": "Bloomberg Staff",
        "tags": ["Companies", "Reader Favorite"],
    },
    {
        "id": 8,
        "title": "Peloton layoffs and cost cutting in 2026",
        "url": "https://www.theverge.com/gadgets/871422/peloton-layoffs-cost-cutting-2026",
        "org": "The Verge",
        "org_initials": "TV",
        "logo_url": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQDwFmAm4KIoRt16UsLNsoQhRwJhvPnASFuXQ&s",
        "summary": "✨ Peloton's latest layoffs and cost cuts highlight pressure to streamline hardware operations in 2026.",
        "date": "2026-01-31",
        "author": "The Verge Staff",
        "tags": ["Hardware", "Infrastructure"],
    },
    {
        "id": 9,
        "title": "Smart glasses seen as first major AI hardware",
        "url": "https://finance.yahoo.com/news/big-tech-thinks-smart-glasses-will-be-the-first-major-piece-of-ai-hardware-105218224.html",
        "org": "Yahoo Finance",
        "org_initials": "YF",
        "logo_url": "https://images-cdn3.welcomesoftware.com/assets/yahoo+finance.jpg/Zz0yNWFjNTk0NjlkMmQxMWVmYjhlNjFlYTY2MTI5N2IyNg==?width=1200",
        "summary": "✨ Major tech firms see smart glasses as the first widely adopted AI hardware category.",
        "date": "2026-01-31",
        "author": "Yahoo Finance",
        "tags": ["Hardware", "Infrastructure"],
    },
    {
        "id": 10,
        "title": "Moltbot highlights cybersecurity risks for AI agents",
        "url": "https://www.axios.com/2026/01/29/moltbot-cybersecurity-ai-agent-risks",
        "org": "Axios",
        "org_initials": "AX",
        "logo_url": "https://tannerfriedman.com/wp-content/uploads/2022/08/91-913031_axios-axios-logo-hd-png-download.png",
        "summary": "✨ Moltbot spotlights how AI agents can be misused, raising new concerns for cybersecurity teams.",
        "date": "2026-01-29",
        "author": "Axios Staff",
        "tags": ["Security", "Misuse"],
    },
]


class NewsHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/articles":
            query = parse_qs(parsed.query)
            tags_param = query.get("tags", [""])[0]
            tags = [tag.strip() for tag in tags_param.split(",") if tag.strip()]
            filtered = self._filter_articles(tags)
            payload = {"count": len(filtered), "articles": filtered}

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        if parsed.path == "/":
            self.path = "/index.html"
        elif parsed.path == "/account":
            self.path = "/auth.html"
        return super().do_GET()

    def _filter_articles(self, tags):
        if not tags:
            return ARTICLES
        lower_tags = {tag.lower() for tag in tags}
        return [
            article
            for article in ARTICLES
            if lower_tags.intersection({tag.lower() for tag in article["tags"]})
        ]


def run_server(host="localhost", port=8000):
    server = HTTPServer((host, port), NewsHandler)
    print(f"Serving AI news on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()