"""LLM-powered persona classification and theme generation."""
import json
import logging

from openai import AsyncOpenAI

from app.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)
client = AsyncOpenAI(api_key=settings.openai_api_key)

# ---------------------------------------------------------------------------
# Palette definitions — all CSS values, applied client-side via JS overrides
# ---------------------------------------------------------------------------

THEME_PALETTES: dict[str, dict] = {
    "researcher": {
        "primary":      "#6366f1",
        "primaryDark":  "#4338ca",
        "bg":           "#f5f3ff",
        "filterBg":     "#ede9fe",
        "filterText":   "#4338ca",
        "textMuted":    "#6366f1",
        "buzzFrom":     "#312e81",
        "buzzTo":       "#1e1b4b",
        "cardHighlight":"#f9f8ff",
        "cardBorder":   "rgba(99,102,241,0.12)",
        "tagHover":     "#6366f1",
    },
    "engineer": {
        "primary":      "#0891b2",
        "primaryDark":  "#0e7490",
        "bg":           "#ecfeff",
        "filterBg":     "#cffafe",
        "filterText":   "#0e7490",
        "textMuted":    "#0891b2",
        "buzzFrom":     "#164e63",
        "buzzTo":       "#0a2e38",
        "cardHighlight":"#f0feff",
        "cardBorder":   "rgba(8,145,178,0.12)",
        "tagHover":     "#0891b2",
    },
    "policy": {
        "primary":      "#1d4ed8",
        "primaryDark":  "#1e40af",
        "bg":           "#eff6ff",
        "filterBg":     "#dbeafe",
        "filterText":   "#1e40af",
        "textMuted":    "#3b82f6",
        "buzzFrom":     "#1e3a8a",
        "buzzTo":       "#0f2158",
        "cardHighlight":"#f8faff",
        "cardBorder":   "rgba(29,78,216,0.12)",
        "tagHover":     "#1d4ed8",
    },
    "investor": {
        "primary":      "#d97706",
        "primaryDark":  "#b45309",
        "bg":           "#fffbeb",
        "filterBg":     "#fef3c7",
        "filterText":   "#b45309",
        "textMuted":    "#d97706",
        "buzzFrom":     "#78350f",
        "buzzTo":       "#431a03",
        "cardHighlight":"#fffdf5",
        "cardBorder":   "rgba(217,119,6,0.12)",
        "tagHover":     "#d97706",
    },
    "futurist": {
        "primary":      "#7c3aed",
        "primaryDark":  "#6d28d9",
        "bg":           "#faf5ff",
        "filterBg":     "#ede9fe",
        "filterText":   "#6d28d9",
        "textMuted":    "#7c3aed",
        "buzzFrom":     "#4c1d95",
        "buzzTo":       "#2d1259",
        "cardHighlight":"#fdf9ff",
        "cardBorder":   "rgba(124,58,237,0.12)",
        "tagHover":     "#7c3aed",
    },
    "journalist": {
        "primary":      "#c2410c",
        "primaryDark":  "#9a3412",
        "bg":           "#fff7ed",
        "filterBg":     "#fed7aa",
        "filterText":   "#9a3412",
        "textMuted":    "#c2410c",
        "buzzFrom":     "#7c2d12",
        "buzzTo":       "#431407",
        "cardHighlight":"#fffaf5",
        "cardBorder":   "rgba(194,65,12,0.12)",
        "tagHover":     "#c2410c",
    },
    "default": {
        "primary":      "#1f9d55",
        "primaryDark":  "#1a6a3a",
        "bg":           "#eef6ef",
        "filterBg":     "#e1f3e6",
        "filterText":   "#1a6a3a",
        "textMuted":    "#4b6b57",
        "buzzFrom":     "#1a5c35",
        "buzzTo":       "#0d3d22",
        "cardHighlight":"#f7fbf7",
        "cardBorder":   "rgba(14,36,22,0.08)",
        "tagHover":     "#1f9d55",
    },
}

_CLASSIFY_SYSTEM = (
    "You are a UX persona classifier for an AI news platform. "
    "Given a user's interests, role, and preferred topics, classify them into "
    "exactly one of these personas and generate personalised display text.\n\n"
    "Personas:\n"
    "- researcher  : AI safety, alignment, academic research, interpretability\n"
    "- engineer    : ML engineering, coding, models, hardware, infrastructure, building things\n"
    "- policy      : AI policy, regulation, governance, law, government\n"
    "- investor    : startups, VC, funding, companies, market, business\n"
    "- futurist    : AGI, long-term futures, speculation, philosophy of mind, transhumanism\n"
    "- journalist  : writing, reporting, media, storytelling, communications\n"
    "- default     : general interest, none of the above clearly applies\n\n"
    "Return ONLY valid JSON, no markdown:\n"
    '{"theme":"<one of the 7 keys>","persona_name":"<2-4 word title>","persona_icon":"<single emoji>",'
    '"tagline":"<punchy 5-8 word phrase that captures their POV>","greeting":"<personalised question to ask them, max 12 words, use {name} as placeholder>"}'
)


async def generate_user_theme(user: User) -> dict:
    """Classify user into a persona and return full theme config (palette + display text)."""
    tag_desc = ", ".join(user.preferred_tags) if user.preferred_tags else "none selected"
    role_desc = user.role or "not specified"
    interests_desc = user.custom_interests or "not provided"

    user_context = (
        f"Preferred topics: {tag_desc}\n"
        f"Role/occupation: {role_desc}\n"
        f"Custom interests (their own words): {interests_desc}"
    )

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _CLASSIFY_SYSTEM},
                {"role": "user", "content": user_context},
            ],
            response_format={"type": "json_object"},
            temperature=0.5,
        )
        raw = json.loads(response.choices[0].message.content)
    except Exception as exc:
        logger.warning("Theme generation failed, using default: %s", exc)
        raw = {
            "theme": "default",
            "persona_name": "AI Enthusiast",
            "persona_icon": "🧠",
            "tagline": "Staying ahead of the curve.",
            "greeting": "What AI news are you looking for today, {name}?",
        }

    theme_key = raw.get("theme", "default")
    if theme_key not in THEME_PALETTES:
        theme_key = "default"

    return {
        "theme": theme_key,
        "persona_name": raw.get("persona_name", "AI Enthusiast"),
        "persona_icon": raw.get("persona_icon", "🧠"),
        "tagline": raw.get("tagline", "Staying ahead of the curve."),
        "greeting": raw.get("greeting", "What AI news are you looking for today, {name}?"),
        "palette": THEME_PALETTES[theme_key],
    }
