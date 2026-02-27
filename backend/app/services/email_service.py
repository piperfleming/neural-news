"""SendGrid email service for daily briefing emails."""
import logging
import re

from app.config import settings

logger = logging.getLogger(__name__)


_STOP = {
    "the", "and", "for", "with", "that", "this", "are", "from", "have",
    "about", "into", "will", "been", "they", "them", "some", "what",
    "its", "our", "you", "how", "was", "has", "had", "but", "not", "all",
    "can", "new", "says", "said", "more", "also", "just", "over", "after",
}


def _keywords(text: str) -> set[str]:
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    return {w for w in words if w not in _STOP}


def _best_article(heading: str, used: set[int], articles: list[dict]) -> dict | None:
    """Return the unused article with the most keyword overlap with the heading."""
    heading_kw = _keywords(heading)
    best, best_score = None, 0
    for i, a in enumerate(articles):
        if i in used or not a.get("url"):
            continue
        score = len(heading_kw & _keywords(a.get("title", "") + " " + a.get("summary", "")))
        if score > best_score:
            best, best_score = (i, a), score
    return best if best_score > 0 else None


def _render_lines(lines: list[str]) -> str:
    html_lines = []
    in_list = False
    for line in lines:
        if line.startswith("- "):
            if not in_list:
                html_lines.append('<ul style="margin:0 0 12px 0;padding-left:20px;">')
                in_list = True
            content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line[2:].strip())
            html_lines.append(f'<li style="margin-bottom:4px;color:#0f1f14;">{content}</li>')
        elif line.strip() == "":
            if in_list:
                html_lines.append("</ul>")
                in_list = False
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
            html_lines.append(f'<p style="margin:0 0 12px 0;color:#0f1f14;line-height:1.6;">{content}</p>')
    if in_list:
        html_lines.append("</ul>")
    return "\n".join(html_lines)


def _briefing_to_html(briefing_text: str, articles: list[dict] | None = None) -> str:
    """Convert markdown briefing to styled HTML email body."""
    # Split into sections on ### headings
    raw_sections = re.split(r'^(### .+)$', briefing_text, flags=re.MULTILINE)

    # raw_sections alternates: [preamble, heading, body, heading, body, ...]
    sections_html = []
    used_articles: set[int] = set()
    pool = articles or []

    # Any preamble before the first heading
    if raw_sections[0].strip():
        sections_html.append(_render_lines(raw_sections[0].strip().splitlines()))

    it = iter(raw_sections[1:])
    for heading_line, body in zip(it, it):
        heading_text = heading_line[4:].strip()
        heading_html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", heading_text)
        body_html = _render_lines(body.strip().splitlines())

        # Find best matching article for this topic
        read_more = ""
        result = _best_article(heading_text, used_articles, pool)
        if result is not None:
            idx, art = result
            used_articles.add(idx)
            read_more = (
                f'<p style="margin:4px 0 16px 0;">'
                f'<a href="{art["url"]}" style="color:#1f9d55;font-size:0.85rem;text-decoration:none;font-weight:600;">'
                f'Read more →</a></p>'
            )

        sections_html.append(
            f'<h3 style="color:#1f9d55;margin:24px 0 8px 0;font-size:1rem;">{heading_html}</h3>'
            f'{body_html}'
            f'{read_more}'
        )

    briefing_html = "\n".join(sections_html)

    return f"""
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:600px;margin:0 auto;padding:32px 24px;background:#ffffff;">
  <div style="text-align:center;margin-bottom:28px;padding-bottom:20px;border-bottom:2px solid #e1f3e6;">
    <div style="font-size:1.6rem;font-weight:800;color:#1f9d55;letter-spacing:-0.5px;">Neural News</div>
    <div style="font-size:0.85rem;color:#6b7280;margin-top:4px;">Your Daily AI Briefing</div>
  </div>
  <div style="padding-top:8px;">
    {briefing_html}
  </div>
  <div style="border-top:1px solid #e1f3e6;margin-top:32px;padding-top:16px;text-align:center;color:#6b7280;font-size:0.8rem;">
    You're receiving this because you enabled daily briefing emails.
    Update your preferences at any time in your account settings.
  </div>
</div>
""".strip()


async def send_daily_briefing_email(
    user_email: str, user_name: str, briefing: dict
) -> None:
    """Send the daily briefing email via SendGrid.

    No-ops gracefully if SENDGRID_API_KEY is not configured.
    """
    if not settings.sendgrid_api_key:
        logger.warning("SENDGRID_API_KEY not set — skipping email to %s", user_email)
        return

    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail, To
    except ImportError:
        logger.error("sendgrid package not installed — cannot send email to %s", user_email)
        return

    briefing_text = briefing.get("briefing_text", "")
    articles = briefing.get("articles", [])
    first_name = user_name.split()[0] if user_name else "there"

    html_body = _briefing_to_html(briefing_text, articles)

    message = Mail(
        from_email=settings.from_email,
        to_emails=To(user_email),
        subject=f"Your AI briefing for today, {first_name}",
        html_content=html_body,
    )

    sg = sendgrid.SendGridAPIClient(api_key=settings.sendgrid_api_key)
    response = sg.send(message)
    logger.info(
        "Briefing email sent to %s — status %s", user_email, response.status_code
    )
