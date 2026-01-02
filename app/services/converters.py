"""
Converter utilities for transforming Instaloader objects to Pydantic models.
Keeps the mapping logic separate from the service layer.
"""

from datetime import datetime
from typing import Any, Optional

from instaloader import (
    Post,
    Profile,
    Story,
    StoryItem,
    Highlight,
    Hashtag,
)

from app.models.profile import ProfileResponse, ProfileBase
from app.models.post import (
    PostResponse,
    PostType,
    MediaItem,
    LocationInfo,
    CommentInfo,
    HashtagInfo,
)
from app.models.story import (
    StoryResponse,
    StoryItemResponse,
    StoryItemType,
    HighlightResponse,
)


class ProfileConverter:
    """Convert Instaloader Profile objects to Pydantic models."""
    
    @staticmethod
    def to_base(profile: Profile) -> ProfileBase:
        """Convert to base profile model (minimal info)."""
        return ProfileBase(
            username=profile.username,
            user_id=profile.userid,
            full_name=profile.full_name or "",
            biography=profile.biography or "",
            is_private=profile.is_private,
            is_verified=profile.is_verified,
            is_business=profile.is_business_account,
        )
    
    @staticmethod
    def to_response(profile: Profile) -> ProfileResponse:
        """Convert to full profile response."""
        return ProfileResponse(
            username=profile.username,
            user_id=profile.userid,
            full_name=profile.full_name or "",
            biography=profile.biography or "",
            is_private=profile.is_private,
            is_verified=profile.is_verified,
            is_business=profile.is_business_account,
            followers=profile.followers,
            followees=profile.followees,
            media_count=profile.mediacount,
            igtv_count=profile.igtvcount,
            profile_pic_url=profile.profile_pic_url,
            external_url=profile.external_url,
            business_category=profile.business_category_name if profile.is_business_account else None,
            followed_by_viewer=getattr(profile, 'followed_by_viewer', None),
            follows_viewer=getattr(profile, 'follows_viewer', None),
            blocked_by_viewer=getattr(profile, 'blocked_by_viewer', None),
        )


class PostConverter:
    """Convert Instaloader Post objects to Pydantic models."""
    
    @staticmethod
    def get_post_type(typename: str) -> PostType:
        """Map typename to PostType enum."""
        mapping = {
            "GraphImage": PostType.IMAGE,
            "GraphVideo": PostType.VIDEO,
            "GraphSidecar": PostType.SIDECAR,
        }
        return mapping.get(typename, PostType.IMAGE)
    
    @staticmethod
    def get_sidecar_items(post: Post) -> list[MediaItem]:
        """Extract sidecar items from a post."""
        if post.typename != "GraphSidecar":
            return []
        
        items = []
        try:
            for node in post.get_sidecar_nodes():
                items.append(MediaItem(
                    is_video=node.is_video,
                    display_url=node.display_url,
                    video_url=node.video_url,
                ))
        except Exception:
            pass
        return items
    
    @staticmethod
    def get_location(post: Post) -> Optional[LocationInfo]:
        """Extract location info from a post."""
        loc = post.location
        if loc is None:
            return None
        
        return LocationInfo(
            id=loc.id,
            name=loc.name,
            slug=loc.slug,
            lat=loc.lat,
            lng=loc.lng,
        )
    
    @staticmethod
    def to_response(post: Post, include_location: bool = True) -> PostResponse:
        """Convert to full post response."""
        sidecar_items = PostConverter.get_sidecar_items(post)
        
        return PostResponse(
            shortcode=post.shortcode,
            media_id=post.mediaid,
            typename=PostConverter.get_post_type(post.typename),
            owner_username=post.owner_username,
            owner_id=post.owner_id,
            caption=post.caption,
            caption_hashtags=post.caption_hashtags or [],
            caption_mentions=post.caption_mentions or [],
            tagged_users=post.tagged_users or [],
            display_url=post.url,
            video_url=post.video_url if post.is_video else None,
            sidecar_items=sidecar_items,
            media_count=post.mediacount,
            likes=post.likes,
            comments_count=post.comments,
            video_view_count=post.video_view_count if post.is_video else None,
            video_duration=post.video_duration if post.is_video else None,
            date_utc=post.date_utc,
            location=PostConverter.get_location(post) if include_location else None,
            is_video=post.is_video,
            is_sponsored=post.is_sponsored,
            viewer_has_liked=getattr(post, 'viewer_has_liked', None),
        )


class StoryConverter:
    """Convert Instaloader Story/StoryItem objects to Pydantic models."""
    
    @staticmethod
    def get_item_type(typename: str) -> StoryItemType:
        """Map typename to StoryItemType enum."""
        if "Video" in typename:
            return StoryItemType.VIDEO
        return StoryItemType.IMAGE
    
    @staticmethod
    def item_to_response(item: StoryItem) -> StoryItemResponse:
        """Convert StoryItem to response model."""
        return StoryItemResponse(
            media_id=item.mediaid,
            shortcode=item.shortcode,
            typename=StoryConverter.get_item_type(item.typename),
            owner_username=item.owner_username,
            owner_id=item.owner_id,
            display_url=item.url,
            video_url=item.video_url if item.is_video else None,
            caption=item.caption,
            caption_hashtags=item.caption_hashtags or [],
            caption_mentions=item.caption_mentions or [],
            date_utc=item.date_utc,
            expiring_utc=item.expiring_utc,
            is_video=item.is_video,
        )
    
    @staticmethod
    def to_response(story: Story, include_items: bool = True) -> StoryResponse:
        """Convert Story to response model."""
        items = []
        if include_items:
            try:
                items = [StoryConverter.item_to_response(item) for item in story.get_items()]
            except Exception:
                pass
        
        return StoryResponse(
            owner_username=story.owner_username,
            owner_id=story.owner_id,
            item_count=story.itemcount,
            items=items,
            latest_media_utc=story.latest_media_utc,
            last_seen_utc=story.last_seen_utc,
        )


class HighlightConverter:
    """Convert Instaloader Highlight objects to Pydantic models."""
    
    @staticmethod
    def to_response(
        highlight: Highlight,
        include_items: bool = False
    ) -> HighlightResponse:
        """Convert Highlight to response model."""
        items = []
        if include_items:
            try:
                items = [StoryConverter.item_to_response(item) for item in highlight.get_items()]
            except Exception:
                pass
        
        return HighlightResponse(
            highlight_id=highlight.unique_id,
            title=highlight.title,
            owner_username=highlight.owner_username,
            owner_id=highlight.owner_id,
            item_count=highlight.itemcount,
            cover_url=highlight.cover_url,
            cover_cropped_url=highlight.cover_cropped_url,
            items=items,
        )


class HashtagConverter:
    """Convert Instaloader Hashtag objects to Pydantic models."""
    
    @staticmethod
    def to_response(hashtag: Hashtag) -> HashtagInfo:
        """Convert Hashtag to response model."""
        return HashtagInfo(
            name=hashtag.name,
            hashtag_id=hashtag.hashtagid,
            media_count=hashtag.mediacount,
            profile_pic_url=hashtag.profile_pic_url,
            description=hashtag.description,
            is_following=getattr(hashtag, 'is_following', None),
        )
