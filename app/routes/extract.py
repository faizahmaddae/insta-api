"""
Universal Instagram URL extractor.
Single endpoint that handles any Instagram URL type.
"""

import re
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.logging import logger
from app.core.cache import get_cache, CacheTTL
from app.services.instaloader_service import get_instaloader_service

router = APIRouter(tags=["Extract"])


class MediaItem(BaseModel):
    url: str
    thumbnail: Optional[str] = None
    is_video: bool = False


class ExtractResponse(BaseModel):
    status: str
    message: str
    error: Optional[str] = None
    data: list[MediaItem] = []


def parse_instagram_url(url: str) -> dict:
    """
    Parse Instagram URL and extract type and identifier.
    
    Supports:
    - Posts: /p/SHORTCODE/ or /reel/SHORTCODE/
    - Profiles: /USERNAME/ or /USERNAME
    - Stories: /stories/USERNAME/ or /stories/USERNAME/STORY_ID/
    - Highlights: /stories/highlights/HIGHLIGHT_ID/
    """
    url = url.strip()
    
    # Remove query params and trailing slash for parsing
    clean_url = url.split('?')[0].rstrip('/')
    
    # Post/Reel: instagram.com/p/SHORTCODE or instagram.com/reel/SHORTCODE
    post_match = re.search(r'instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)', clean_url)
    if post_match:
        return {"type": "post", "shortcode": post_match.group(1)}
    
    # Highlight: instagram.com/stories/highlights/HIGHLIGHT_ID (check before stories)
    highlight_match = re.search(r'instagram\.com/stories/highlights/(\d+)', clean_url)
    if highlight_match:
        return {"type": "highlight", "highlight_id": highlight_match.group(1)}
    
    # Story with ID: instagram.com/stories/USERNAME/STORY_ID
    story_match = re.search(r'instagram\.com/stories/([^/]+)/(\d+)', clean_url)
    if story_match:
        return {"type": "story", "username": story_match.group(1), "story_id": story_match.group(2)}
    
    # All stories: instagram.com/stories/USERNAME (no specific story ID)
    all_stories_match = re.search(r'instagram\.com/stories/([A-Za-z0-9_.]+)/?$', clean_url)
    if all_stories_match:
        return {"type": "stories_all", "username": all_stories_match.group(1)}
    
    # Profile: instagram.com/USERNAME
    profile_match = re.search(r'instagram\.com/([A-Za-z0-9_.]+)/?$', clean_url)
    if profile_match:
        username = profile_match.group(1)
        # Filter out Instagram reserved paths
        reserved = ['p', 'reel', 'tv', 'stories', 'explore', 'direct', 'accounts', 'about', 'legal']
        if username.lower() not in reserved:
            return {"type": "profile", "username": username}
    
    return {"type": "unknown", "url": url}


@router.get(
    "",
    response_model=ExtractResponse,
    summary="Extract Media from Instagram URL",
    description="Universal endpoint - handles posts, reels, profiles, and stories."
)
async def extract_media(
    url: str = Query(..., description="Instagram URL (post, reel, profile, or story)")
) -> ExtractResponse:
    """
    Extract media from any Instagram URL.
    
    Supported URLs:
    - Posts: https://instagram.com/p/SHORTCODE
    - Reels: https://instagram.com/reel/SHORTCODE
    - Profiles: https://instagram.com/USERNAME (returns recent posts)
    - Stories: https://instagram.com/stories/USERNAME/STORY_ID
    """
    
    # Validate URL
    if not url or 'instagram.com' not in url:
        return ExtractResponse(
            status="error",
            message="Invalid URL",
            error="Please provide a valid Instagram URL"
        )
    
    # Parse URL type
    parsed = parse_instagram_url(url)
    logger.info(f"Extracting from URL: {url} -> {parsed}")
    
    # Check cache - include type in cache key to avoid collisions
    cache = get_cache()
    url_type = parsed.get("type", "unknown")
    identifier = parsed.get('shortcode') or parsed.get('username') or parsed.get('story_id') or url
    cache_key = f"extract:{url_type}:{identifier}"
    cached = await cache.get(cache_key)
    if cached:
        logger.debug(f"Cache hit for {cache_key}")
        return ExtractResponse(**cached)
    
    try:
        if parsed["type"] == "post":
            result = await extract_post(parsed["shortcode"])
        elif parsed["type"] == "profile":
            result = await extract_profile(parsed["username"])
        elif parsed["type"] == "story":
            result = await extract_story(parsed["username"], parsed["story_id"])
        elif parsed["type"] == "stories_all":
            result = await extract_all_stories(parsed["username"])
        elif parsed["type"] == "highlight":
            result = await extract_highlight(parsed["highlight_id"])
        else:
            return ExtractResponse(
                status="error",
                message="Unsupported URL",
                error=f"Could not parse Instagram URL: {url}"
            )
        
        # Cache successful result with appropriate TTL per type
        if result.status == "success":
            ttl_map = {
                "post": CacheTTL.POSTS,           # 1 hour
                "profile": CacheTTL.PROFILE,      # 1 hour
                "story": CacheTTL.STORIES,        # 5 minutes (stories expire)
                "stories_all": CacheTTL.STORIES,  # 5 minutes
                "highlight": CacheTTL.POSTS,      # 1 hour (highlights persist)
            }
            ttl = ttl_map.get(url_type, CacheTTL.POSTS)
            await cache.set(cache_key, result.model_dump(), ttl=ttl)
        
        return result
        
    except Exception as e:
        logger.error(f"Extraction error: {e}")
        return ExtractResponse(
            status="error",
            message="Extraction failed",
            error=str(e)
        )


async def extract_post(shortcode: str) -> ExtractResponse:
    """Extract media from a post/reel."""
    service = get_instaloader_service()
    
    try:
        post = await service.get_post(shortcode)
        
        media_items = []
        
        # Check if it's a carousel (multiple media)
        if post.typename == 'GraphSidecar':
            # Carousel post - multiple images/videos
            for node in post.get_sidecar_nodes():
                media_items.append(MediaItem(
                    url=node.video_url if node.is_video else node.display_url,
                    thumbnail=node.display_url,
                    is_video=node.is_video
                ))
        else:
            # Single post
            media_items.append(MediaItem(
                url=post.video_url if post.is_video else post.url,
                thumbnail=post.url,  # display_url
                is_video=post.is_video
            ))
        
        return ExtractResponse(
            status="success",
            message="Success",
            data=media_items
        )
        
    except Exception as e:
        logger.error(f"Post extraction error for {shortcode}: {e}")
        return ExtractResponse(
            status="error",
            message="Failed to extract post",
            error=str(e)
        )


async def extract_profile(username: str) -> ExtractResponse:
    """Extract profile picture and recent post thumbnails."""
    service = get_instaloader_service()
    
    try:
        profile = await service.get_profile(username)
        posts = await service.get_profile_posts(username, limit=12)
        
        media_items = []
        
        # Profile picture
        media_items.append(MediaItem(
            url=profile.profile_pic_url,
            thumbnail=profile.profile_pic_url,
            is_video=False
        ))
        
        # Recent posts
        for post in posts:
            if post.typename == 'GraphSidecar':
                # Just get first item from carousel
                for node in post.get_sidecar_nodes():
                    media_items.append(MediaItem(
                        url=node.video_url if node.is_video else node.display_url,
                        thumbnail=node.display_url,
                        is_video=node.is_video
                    ))
                    break  # Only first
            else:
                media_items.append(MediaItem(
                    url=post.video_url if post.is_video else post.url,
                    thumbnail=post.url,
                    is_video=post.is_video
                ))
        
        return ExtractResponse(
            status="success",
            message="Success",
            data=media_items
        )
        
    except Exception as e:
        logger.error(f"Profile extraction error for {username}: {e}")
        return ExtractResponse(
            status="error",
            message="Failed to extract profile",
            error=str(e)
        )


async def extract_story(username: str, story_id: str) -> ExtractResponse:
    """Extract a specific story."""
    service = get_instaloader_service()
    
    try:
        stories = await service.get_user_stories(username)
        
        media_items = []
        
        for story in stories:
            for item in story.get_items():
                # Check if this is the requested story
                if str(item.mediaid) == story_id or story_id == "all":
                    media_items.append(MediaItem(
                        url=item.video_url if item.is_video else item.url,
                        thumbnail=item.url,
                        is_video=item.is_video
                    ))
                    if story_id != "all":
                        break
        
        if not media_items:
            return ExtractResponse(
                status="error",
                message="Story not found",
                error=f"Story {story_id} not found or expired"
            )
        
        return ExtractResponse(
            status="success",
            message="Success",
            data=media_items
        )
        
    except Exception as e:
        logger.error(f"Story extraction error: {e}")
        return ExtractResponse(
            status="error",
            message="Failed to extract story",
            error=str(e)
        )


async def extract_highlight(highlight_id: str) -> ExtractResponse:
    """Extract highlight stories by ID."""
    service = get_instaloader_service()
    
    try:
        import asyncio
        
        def _fetch_highlight():
            # Get a rotated loader with authentication
            loader, account = service._get_rotated_loader()
            context = loader.context
            
            # Try the reels_media query
            query_hash = "45246d3fe16ccc6577e0bd297a5db1ab"
            variables = {
                "highlight_reel_ids": [str(highlight_id)],
                "reel_ids": [],
                "location_ids": [],
                "precomposed_overlay": False
            }
            
            try:
                data = context.graphql_query(query_hash, variables)
                reels_media = data.get("data", {}).get("reels_media", [])
                if reels_media:
                    return reels_media[0]
            except Exception as e:
                logger.debug(f"GraphQL query failed: {e}")
            
            # Alternative: try fetching via web API
            try:
                url = f"https://www.instagram.com/api/v1/feed/reels_media/?reel_ids=highlight:{highlight_id}"
                headers = {
                    "User-Agent": "Instagram 76.0.0.15.395 Android",
                    "X-CSRFToken": context._session.cookies.get("csrftoken", ""),
                }
                resp = context._session.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    reels = data.get("reels", {})
                    highlight_key = f"highlight:{highlight_id}"
                    if highlight_key in reels:
                        return reels[highlight_key]
            except Exception as e:
                logger.debug(f"Web API query failed: {e}")
            
            return None
        
        loop = asyncio.get_event_loop()
        highlight_data = await loop.run_in_executor(None, _fetch_highlight)
        
        if not highlight_data:
            return ExtractResponse(
                status="error",
                message="Highlight not found",
                error=f"Highlight {highlight_id} not found or is private"
            )
        
        media_items = []
        items = highlight_data.get("items", [])
        
        for item in items:
            is_video = item.get("is_video", False) or item.get("media_type") == 2
            
            if is_video:
                # Get video URL
                video_versions = item.get("video_versions", [])
                if video_versions:
                    url = video_versions[0].get("url", "")
                else:
                    url = item.get("video_url", "")
            else:
                # Get image URL  
                image_versions = item.get("image_versions2", {}).get("candidates", [])
                if image_versions:
                    url = image_versions[0].get("url", "")
                else:
                    url = item.get("display_url", "")
            
            # Thumbnail
            image_versions = item.get("image_versions2", {}).get("candidates", [])
            thumbnail = image_versions[0].get("url", "") if image_versions else url
            
            if url:
                media_items.append(MediaItem(
                    url=url,
                    thumbnail=thumbnail,
                    is_video=is_video
                ))
        
        if not media_items:
            return ExtractResponse(
                status="error",
                message="No media found",
                error="Highlight exists but contains no media"
            )
        
        return ExtractResponse(
            status="success",
            message="Success",
            data=media_items
        )
        
    except Exception as e:
        logger.error(f"Highlight extraction error for {highlight_id}: {e}")
        return ExtractResponse(
            status="error",
            message="Failed to extract highlight",
            error=str(e)
        )


async def extract_all_stories(username: str) -> ExtractResponse:
    """Extract all current stories from a user."""
    service = get_instaloader_service()
    
    try:
        stories = await service.get_user_stories(username)
        
        media_items = []
        
        for story in stories:
            for item in story.get_items():
                media_items.append(MediaItem(
                    url=item.video_url if item.is_video else item.url,
                    thumbnail=item.url,
                    is_video=item.is_video
                ))
        
        if not media_items:
            return ExtractResponse(
                status="error",
                message="No stories found",
                error=f"User {username} has no active stories"
            )
        
        return ExtractResponse(
            status="success",
            message="Success",
            data=media_items
        )
        
    except Exception as e:
        logger.error(f"All stories extraction error for {username}: {e}")
        return ExtractResponse(
            status="error",
            message="Failed to extract stories",
            error=str(e)
        )
