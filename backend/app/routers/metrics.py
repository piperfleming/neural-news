"""Endpoints for tracking and summarizing user engagement metrics."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_admin_user, get_current_user
from app.models.article import Article
from app.models.user import User
from app.models.user_metrics import ArticleClick, ArticleLike, UserSession
from app.schemas.metrics import (
    AdminUserDetail,
    AdminUserListItem,
    AdminUsersResponse,
    AdminMetricsSummary,
    ArticleClickIn,
    ArticleLikeIn,
    DailyMetric,
    HeartbeatIn,
    HeartbeatResponse,
    MetricsSummary,
    SessionEndIn,
    SessionMetric,
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


@router.get("/me/article-likes/ids")
async def my_article_like_ids(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(ArticleLike.article_id).where(
                ArticleLike.user_id == current_user.id,
                ArticleLike.article_id.is_not(None),
            )
        )
    ).all()
    return {"article_ids": [row[0] for row in rows]}


@router.get("/me/article-likes/urls")
async def my_article_like_urls(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(ArticleLike.article_url).where(
                ArticleLike.user_id == current_user.id,
                ArticleLike.article_url.is_not(None),
            )
        )
    ).all()
    return {"article_urls": [row[0] for row in rows if row[0]]}


@router.post("/article-like", status_code=201)
async def article_like(
    payload: ArticleLikeIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.article_id is None and not payload.article_url:
        raise HTTPException(status_code=422, detail="article_id or article_url is required")

    if payload.article_id is not None:
        existing_query = select(ArticleLike).where(
            ArticleLike.user_id == current_user.id,
            ArticleLike.article_id == payload.article_id,
        )
    else:
        existing_query = select(ArticleLike).where(
            ArticleLike.user_id == current_user.id,
            ArticleLike.article_url == payload.article_url,
        )

    existing = (await db.execute(existing_query)).scalar_one_or_none()
    if existing is not None:
        return {"ok": True, "liked": True}

    like = ArticleLike(
        user_id=current_user.id,
        article_id=payload.article_id,
        article_url=payload.article_url,
        tags=payload.tags,
        liked_at=_utcnow(),
    )
    db.add(like)
    await db.flush()
    return {"ok": True, "liked": True}


@router.delete("/article-like/{article_id}", status_code=204)
async def article_unlike(
    article_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = (
        await db.execute(
            select(ArticleLike).where(
                ArticleLike.user_id == current_user.id,
                ArticleLike.article_id == article_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        await db.delete(existing)
        await db.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/article-like-by-url", status_code=204)
async def article_unlike_by_url(
    article_url: str = Query(..., min_length=5),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = (
        await db.execute(
            select(ArticleLike).where(
                ArticleLike.user_id == current_user.id,
                ArticleLike.article_url == article_url,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        await db.delete(existing)
        await db.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    total_likes = (
        await db.execute(
            select(func.count(ArticleLike.id)).where(
                ArticleLike.user_id == current_user.id,
                ArticleLike.liked_at >= start,
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
    day_likes = func.date(ArticleLike.liked_at)
    likes_daily_rows = (
        await db.execute(
            select(
                day_likes.label("day"),
                func.count(ArticleLike.id).label("likes"),
            )
            .where(ArticleLike.user_id == current_user.id, ArticleLike.liked_at >= start)
            .group_by(day_likes)
            .order_by(day_likes)
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
            likes=0,
        )
    for day, clicks in clicks_daily_rows:
        key = str(day)
        if key not in daily_map:
            daily_map[key] = DailyMetric(date=key, sessions=0, active_seconds=0, clicks=int(clicks or 0))
        else:
            daily_map[key].clicks = int(clicks or 0)
    for day, likes in likes_daily_rows:
        key = str(day)
        if key not in daily_map:
            daily_map[key] = DailyMetric(date=key, sessions=0, active_seconds=0, clicks=0, likes=int(likes or 0))
        else:
            daily_map[key].likes = int(likes or 0)

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

    likes_agg = (
        select(
            ArticleLike.article_id.label("article_id"),
            func.count(ArticleLike.id).label("likes"),
        )
        .where(ArticleLike.user_id == current_user.id, ArticleLike.liked_at >= start)
        .group_by(ArticleLike.article_id)
        .subquery()
    )

    # Top engaged articles
    top_article_rows = (
        await db.execute(
            select(
                ArticleClick.article_id,
                Article.title,
                func.count(ArticleClick.id).label("clicks"),
                func.coalesce(likes_agg.c.likes, 0).label("likes"),
            )
            .join(Article, Article.id == ArticleClick.article_id, isouter=True)
            .join(likes_agg, likes_agg.c.article_id == ArticleClick.article_id, isouter=True)
            .where(ArticleClick.user_id == current_user.id, ArticleClick.clicked_at >= start)
            .group_by(ArticleClick.article_id, Article.title, likes_agg.c.likes)
            .order_by(desc(func.coalesce(likes_agg.c.likes, 0)), desc(func.count(ArticleClick.id)))
            .limit(10)
        )
    ).all()
    top_articles = [
        TopArticle(article_id=row[0], title=row[1], clicks=int(row[2] or 0), likes=int(row[3] or 0))
        for row in top_article_rows
    ]

    return MetricsSummary(
        days=days,
        total_sessions=int(total_sessions or 0),
        total_active_seconds=int(total_active_seconds or 0),
        total_clicks=int(total_clicks or 0),
        total_likes=int(total_likes or 0),
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
    total_likes = (
        await db.execute(
            select(func.count(ArticleLike.id)).where(ArticleLike.liked_at >= start)
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

    likes_agg = (
        select(
            ArticleLike.article_id.label("article_id"),
            func.count(ArticleLike.id).label("likes"),
        )
        .where(ArticleLike.liked_at >= start)
        .group_by(ArticleLike.article_id)
        .subquery()
    )

    top_article_rows = (
        await db.execute(
            select(
                ArticleClick.article_id,
                Article.title,
                func.count(ArticleClick.id).label("clicks"),
                func.coalesce(likes_agg.c.likes, 0).label("likes"),
            )
            .join(Article, Article.id == ArticleClick.article_id, isouter=True)
            .join(likes_agg, likes_agg.c.article_id == ArticleClick.article_id, isouter=True)
            .where(ArticleClick.clicked_at >= start)
            .group_by(ArticleClick.article_id, Article.title, likes_agg.c.likes)
            .order_by(desc(func.coalesce(likes_agg.c.likes, 0)), desc(func.count(ArticleClick.id)))
            .limit(10)
        )
    ).all()
    top_articles = [
        TopArticle(article_id=row[0], title=row[1], clicks=int(row[2] or 0), likes=int(row[3] or 0))
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
        total_likes=int(total_likes or 0),
        top_tags=top_tags,
        top_articles=top_articles,
    )


@router.get("/admin/users", response_model=AdminUsersResponse)
async def admin_users(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=500),
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    now = _utcnow()
    start = now - timedelta(days=days)

    sessions_agg = (
        select(
            UserSession.user_id.label("user_id"),
            func.count(UserSession.id).label("total_sessions"),
            func.coalesce(func.sum(UserSession.active_seconds), 0).label("total_active_seconds"),
            func.max(UserSession.last_seen_at).label("last_seen_at"),
        )
        .where(UserSession.started_at >= start)
        .group_by(UserSession.user_id)
        .subquery()
    )
    clicks_agg = (
        select(
            ArticleClick.user_id.label("user_id"),
            func.count(ArticleClick.id).label("total_clicks"),
        )
        .where(ArticleClick.clicked_at >= start)
        .group_by(ArticleClick.user_id)
        .subquery()
    )
    likes_agg = (
        select(
            ArticleLike.user_id.label("user_id"),
            func.count(ArticleLike.id).label("total_likes"),
        )
        .where(ArticleLike.liked_at >= start)
        .group_by(ArticleLike.user_id)
        .subquery()
    )

    rows = (
        await db.execute(
            select(
                User.id,
                User.name,
                User.email,
                User.role,
                User.created_at,
                sessions_agg.c.last_seen_at,
                func.coalesce(sessions_agg.c.total_sessions, 0).label("total_sessions"),
                func.coalesce(sessions_agg.c.total_active_seconds, 0).label("total_active_seconds"),
                func.coalesce(clicks_agg.c.total_clicks, 0).label("total_clicks"),
                func.coalesce(likes_agg.c.total_likes, 0).label("total_likes"),
            )
            .join(sessions_agg, sessions_agg.c.user_id == User.id, isouter=True)
            .join(clicks_agg, clicks_agg.c.user_id == User.id, isouter=True)
            .join(likes_agg, likes_agg.c.user_id == User.id, isouter=True)
            .order_by(
                desc(func.coalesce(sessions_agg.c.total_active_seconds, 0)),
                desc(func.coalesce(likes_agg.c.total_likes, 0)),
                desc(func.coalesce(clicks_agg.c.total_clicks, 0)),
                User.created_at.desc(),
            )
            .limit(limit)
        )
    ).all()

    users = [
        AdminUserListItem(
            user_id=row[0],
            name=row[1],
            email=row[2],
            role=row[3],
            created_at=row[4],
            last_seen_at=row[5],
            total_sessions=int(row[6] or 0),
            total_active_seconds=int(row[7] or 0),
            total_clicks=int(row[8] or 0),
            total_likes=int(row[9] or 0),
        )
        for row in rows
    ]
    return AdminUsersResponse(days=days, users=users)


@router.get("/admin/users/{user_id}", response_model=AdminUserDetail)
async def admin_user_detail(
    user_id: int,
    days: int = Query(30, ge=1, le=365),
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    now = _utcnow()
    start = now - timedelta(days=days)

    user = (
        await db.execute(
            select(User).where(User.id == user_id)
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    total_sessions = (
        await db.execute(
            select(func.count(UserSession.id)).where(
                UserSession.user_id == user_id,
                UserSession.started_at >= start,
            )
        )
    ).scalar_one()
    total_active_seconds = (
        await db.execute(
            select(func.coalesce(func.sum(UserSession.active_seconds), 0)).where(
                UserSession.user_id == user_id,
                UserSession.started_at >= start,
            )
        )
    ).scalar_one()
    total_clicks = (
        await db.execute(
            select(func.count(ArticleClick.id)).where(
                ArticleClick.user_id == user_id,
                ArticleClick.clicked_at >= start,
            )
        )
    ).scalar_one()
    total_likes = (
        await db.execute(
            select(func.count(ArticleLike.id)).where(
                ArticleLike.user_id == user_id,
                ArticleLike.liked_at >= start,
            )
        )
    ).scalar_one()

    last_seen_at = (
        await db.execute(
            select(func.max(UserSession.last_seen_at)).where(UserSession.user_id == user_id)
        )
    ).scalar_one()

    day_sessions = func.date(UserSession.started_at)
    sessions_daily_rows = (
        await db.execute(
            select(
                day_sessions.label("day"),
                func.count(UserSession.id).label("sessions"),
                func.coalesce(func.sum(UserSession.active_seconds), 0).label("active_seconds"),
            )
            .where(UserSession.user_id == user_id, UserSession.started_at >= start)
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
            .where(ArticleClick.user_id == user_id, ArticleClick.clicked_at >= start)
            .group_by(day_clicks)
            .order_by(day_clicks)
        )
    ).all()
    day_likes = func.date(ArticleLike.liked_at)
    likes_daily_rows = (
        await db.execute(
            select(
                day_likes.label("day"),
                func.count(ArticleLike.id).label("likes"),
            )
            .where(ArticleLike.user_id == user_id, ArticleLike.liked_at >= start)
            .group_by(day_likes)
            .order_by(day_likes)
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
            likes=0,
        )
    for day, clicks in clicks_daily_rows:
        key = str(day)
        if key not in daily_map:
            daily_map[key] = DailyMetric(date=key, sessions=0, active_seconds=0, clicks=int(clicks or 0))
        else:
            daily_map[key].clicks = int(clicks or 0)
    for day, likes in likes_daily_rows:
        key = str(day)
        if key not in daily_map:
            daily_map[key] = DailyMetric(date=key, sessions=0, active_seconds=0, clicks=0, likes=int(likes or 0))
        else:
            daily_map[key].likes = int(likes or 0)
    daily = [daily_map[k] for k in sorted(daily_map.keys())]

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
            {"user_id": user_id, "start": start},
        )
    ).all()
    clicks_by_tag = {row[0]: int(row[1]) for row in clicks_by_tag_rows if row[0]}

    likes_agg = (
        select(
            ArticleLike.article_id.label("article_id"),
            func.count(ArticleLike.id).label("likes"),
        )
        .where(ArticleLike.user_id == user_id, ArticleLike.liked_at >= start)
        .group_by(ArticleLike.article_id)
        .subquery()
    )

    top_article_rows = (
        await db.execute(
            select(
                ArticleClick.article_id,
                Article.title,
                func.count(ArticleClick.id).label("clicks"),
                func.coalesce(likes_agg.c.likes, 0).label("likes"),
            )
            .join(Article, Article.id == ArticleClick.article_id, isouter=True)
            .join(likes_agg, likes_agg.c.article_id == ArticleClick.article_id, isouter=True)
            .where(ArticleClick.user_id == user_id, ArticleClick.clicked_at >= start)
            .group_by(ArticleClick.article_id, Article.title, likes_agg.c.likes)
            .order_by(desc(func.coalesce(likes_agg.c.likes, 0)), desc(func.count(ArticleClick.id)))
            .limit(10)
        )
    ).all()
    top_articles = [
        TopArticle(article_id=row[0], title=row[1], clicks=int(row[2] or 0), likes=int(row[3] or 0))
        for row in top_article_rows
    ]

    recent_session_rows = (
        await db.execute(
            select(UserSession)
            .where(UserSession.user_id == user_id, UserSession.started_at >= start)
            .order_by(UserSession.started_at.desc())
            .limit(20)
        )
    ).scalars().all()
    recent_sessions = [
        SessionMetric(
            session_id=session.session_id,
            started_at=session.started_at,
            last_seen_at=session.last_seen_at,
            ended_at=session.ended_at,
            active_seconds=int(session.active_seconds or 0),
        )
        for session in recent_session_rows
    ]

    return AdminUserDetail(
        days=days,
        user_id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
        last_seen_at=last_seen_at,
        total_sessions=int(total_sessions or 0),
        total_active_seconds=int(total_active_seconds or 0),
        total_clicks=int(total_clicks or 0),
        total_likes=int(total_likes or 0),
        daily=daily,
        clicks_by_tag=clicks_by_tag,
        top_articles=top_articles,
        recent_sessions=recent_sessions,
    )

