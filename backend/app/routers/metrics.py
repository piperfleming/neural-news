"""Endpoints for tracking and summarizing user engagement metrics."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_admin_user, get_current_user
from app.models.article import Article
from app.models.user import User
from app.models.user_metrics import ArticleClick, UserSession
from app.schemas.metrics import (
    AdminMetricsSummary,
    ArticleClickIn,
    DailyMetric,
    HeartbeatIn,
    HeartbeatResponse,
    MetricsSummary,
    SessionEndIn,
    TagMetric,
    TopArticle,
)

router = APIRouter()

# Heartbeat interval on the frontend is 30s; allow some jitter / brief pauses.
_MAX_ACTIVE_GAP_SECONDS = 120


def _utcnow() -> datetime:
    # Keep naive UTC timestamps to match existing models/tables in this project.
    return datetime.utcnow()


async def _touch_session(
    *,
    db: AsyncSession,
    user_id: int,
    session_id: str,
    now: datetime,
    user_agent: str | None = None,
) -> UserSession:
    result = await db.execute(
        select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.session_id == session_id,
        )
    )
    session = result.scalar_one_or_none()

    if session is None:
        session = UserSession(
            user_id=user_id,
            session_id=session_id,
            started_at=now,
            last_seen_at=now,
            active_seconds=0,
            user_agent=user_agent,
        )
        db.add(session)
        return session

    # If the client "ends" a session and later resumes with same session_id,
    # treat it as a fresh session.
    if session.ended_at is not None:
        session.started_at = now
        session.last_seen_at = now
        session.ended_at = None
        session.active_seconds = 0
        session.user_agent = session.user_agent or user_agent
        return session

    # Best-effort active time approximation: add delta between heartbeats
    # when the user was recently seen.
    if session.last_seen_at is not None:
        delta = (now - session.last_seen_at).total_seconds()
        if 0 < delta <= _MAX_ACTIVE_GAP_SECONDS:
            session.active_seconds += int(delta)

    session.last_seen_at = now
    session.user_agent = session.user_agent or user_agent
    return session


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(
    payload: HeartbeatIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = _utcnow()
    session = await _touch_session(
        db=db,
        user_id=current_user.id,
        session_id=payload.session_id,
        now=now,
        user_agent=payload.user_agent,
    )
    await db.flush()
    return HeartbeatResponse(session_id=session.session_id, active_seconds=session.active_seconds)


@router.post("/session-end", status_code=204)
async def session_end(
    payload: SessionEndIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = _utcnow()
    result = await db.execute(
        select(UserSession).where(
            UserSession.user_id == current_user.id,
            UserSession.session_id == payload.session_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    if session.ended_at is None and session.last_seen_at is not None:
        delta = (now - session.last_seen_at).total_seconds()
        if 0 < delta <= _MAX_ACTIVE_GAP_SECONDS:
            session.active_seconds += int(delta)
        session.last_seen_at = now
        session.ended_at = now

    await db.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/article-click", status_code=201)
async def article_click(
    payload: ArticleClickIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = _utcnow()
    await _touch_session(
        db=db,
        user_id=current_user.id,
        session_id=payload.session_id,
        now=now,
        user_agent=None,
    )

    click = ArticleClick(
        user_id=current_user.id,
        article_id=payload.article_id,
        session_id=payload.session_id,
        article_url=payload.article_url,
        page_path=payload.page_path,
        tags=payload.tags,
        clicked_at=now,
    )
    db.add(click)
    await db.flush()
    return {"ok": True}


@router.get("/me/summary", response_model=MetricsSummary)
async def my_summary(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = _utcnow()
    start = now - timedelta(days=days)

    # Totals
    total_sessions = (
        await db.execute(
            select(func.count(UserSession.id)).where(
                UserSession.user_id == current_user.id,
                UserSession.started_at >= start,
            )
        )
    ).scalar_one()

    total_active_seconds = (
        await db.execute(
            select(func.coalesce(func.sum(UserSession.active_seconds), 0)).where(
                UserSession.user_id == current_user.id,
                UserSession.started_at >= start,
            )
        )
    ).scalar_one()

    total_clicks = (
        await db.execute(
            select(func.count(ArticleClick.id)).where(
                ArticleClick.user_id == current_user.id,
                ArticleClick.clicked_at >= start,
            )
        )
    ).scalar_one()

    # Daily series (merge sessions + clicks into a single list)
    day_sessions = func.date(UserSession.started_at)
    sessions_daily_rows = (
        await db.execute(
            select(
                day_sessions.label("day"),
                func.count(UserSession.id).label("sessions"),
                func.coalesce(func.sum(UserSession.active_seconds), 0).label("active_seconds"),
            )
            .where(UserSession.user_id == current_user.id, UserSession.started_at >= start)
            .group_by(day_sessions)
            .order_by(day_sessions)
        )
    ).all()

    day_clicks = func.date(ArticleClick.clicked_at)
    clicks_daily_rows = (
        await db.execute(
            select(
                day_clicks.label("day"),
                func.count(ArticleClick.id).label("clicks"),
            )
            .where(ArticleClick.user_id == current_user.id, ArticleClick.clicked_at >= start)
            .group_by(day_clicks)
            .order_by(day_clicks)
        )
    ).all()

    daily_map: dict[str, DailyMetric] = {}
    for day, sessions, active_seconds in sessions_daily_rows:
        key = str(day)
        daily_map[key] = DailyMetric(
            date=key,
            sessions=int(sessions or 0),
            active_seconds=int(active_seconds or 0),
            clicks=0,
        )
    for day, clicks in clicks_daily_rows:
        key = str(day)
        if key not in daily_map:
            daily_map[key] = DailyMetric(date=key, sessions=0, active_seconds=0, clicks=int(clicks or 0))
        else:
            daily_map[key].clicks = int(clicks or 0)

    daily = [daily_map[k] for k in sorted(daily_map.keys())]

    # Clicks by tag (best-effort; tags are stored as an array snapshot on click)
    clicks_by_tag_rows = (
        await db.execute(
            text(
                """
                SELECT tag, COUNT(*)::int AS clicks
                FROM (
                    SELECT unnest(tags) AS tag
                    FROM article_clicks
                    WHERE user_id = :user_id
                      AND clicked_at >= :start
                ) t
                GROUP BY tag
                ORDER BY clicks DESC
                """
            ),
            {"user_id": current_user.id, "start": start},
        )
    ).all()
    clicks_by_tag = {row[0]: int(row[1]) for row in clicks_by_tag_rows if row[0]}

    # Top clicked articles
    top_article_rows = (
        await db.execute(
            select(
                ArticleClick.article_id,
                Article.title,
                func.count(ArticleClick.id).label("clicks"),
            )
            .join(Article, Article.id == ArticleClick.article_id, isouter=True)
            .where(ArticleClick.user_id == current_user.id, ArticleClick.clicked_at >= start)
            .group_by(ArticleClick.article_id, Article.title)
            .order_by(desc(func.count(ArticleClick.id)))
            .limit(10)
        )
    ).all()
    top_articles = [
        TopArticle(article_id=row[0], title=row[1], clicks=int(row[2] or 0))
        for row in top_article_rows
    ]

    return MetricsSummary(
        days=days,
        total_sessions=int(total_sessions or 0),
        total_active_seconds=int(total_active_seconds or 0),
        total_clicks=int(total_clicks or 0),
        daily=daily,
        clicks_by_tag=clicks_by_tag,
        top_articles=top_articles,
    )


@router.get("/admin/summary", response_model=AdminMetricsSummary)
async def admin_summary(
    days: int = Query(30, ge=1, le=365),
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    now = _utcnow()
    start = now - timedelta(days=days)
    last_24h = now - timedelta(hours=24)

    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    new_users = (
        await db.execute(select(func.count(User.id)).where(User.created_at >= start))
    ).scalar_one()
    active_users_24h = (
        await db.execute(
            select(func.count(func.distinct(UserSession.user_id))).where(
                UserSession.last_seen_at >= last_24h
            )
        )
    ).scalar_one()

    total_sessions = (
        await db.execute(
            select(func.count(UserSession.id)).where(UserSession.started_at >= start)
        )
    ).scalar_one()
    total_active_seconds = (
        await db.execute(
            select(func.coalesce(func.sum(UserSession.active_seconds), 0)).where(
                UserSession.started_at >= start
            )
        )
    ).scalar_one()
    total_clicks = (
        await db.execute(
            select(func.count(ArticleClick.id)).where(ArticleClick.clicked_at >= start)
        )
    ).scalar_one()

    top_tag_rows = (
        await db.execute(
            text(
                """
                SELECT tag, COUNT(*)::int AS clicks
                FROM (
                    SELECT unnest(tags) AS tag
                    FROM article_clicks
                    WHERE clicked_at >= :start
                ) t
                GROUP BY tag
                ORDER BY clicks DESC
                LIMIT 10
                """
            ),
            {"start": start},
        )
    ).all()
    top_tags = [TagMetric(tag=row[0], clicks=int(row[1])) for row in top_tag_rows if row[0]]

    top_article_rows = (
        await db.execute(
            select(
                ArticleClick.article_id,
                Article.title,
                func.count(ArticleClick.id).label("clicks"),
            )
            .join(Article, Article.id == ArticleClick.article_id, isouter=True)
            .where(ArticleClick.clicked_at >= start)
            .group_by(ArticleClick.article_id, Article.title)
            .order_by(desc(func.count(ArticleClick.id)))
            .limit(10)
        )
    ).all()
    top_articles = [
        TopArticle(article_id=row[0], title=row[1], clicks=int(row[2] or 0))
        for row in top_article_rows
    ]

    return AdminMetricsSummary(
        days=days,
        total_users=int(total_users or 0),
        new_users=int(new_users or 0),
        active_users_24h=int(active_users_24h or 0),
        total_sessions=int(total_sessions or 0),
        total_active_seconds=int(total_active_seconds or 0),
        total_clicks=int(total_clicks or 0),
        top_tags=top_tags,
        top_articles=top_articles,
    )

