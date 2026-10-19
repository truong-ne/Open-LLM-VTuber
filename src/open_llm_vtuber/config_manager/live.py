from pydantic import Field
from typing import Dict, ClassVar, List, Literal
from .i18n import I18nMixin, Description


class BiliBiliLiveConfig(I18nMixin):
    """Configuration for BiliBili Live platform."""

    room_ids: List[int] = Field([], alias="room_ids")
    sessdata: str = Field("", alias="sessdata")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "room_ids": Description(
            en="List of BiliBili live room IDs to monitor", zh="要监控的B站直播间ID列表"
        ),
        "sessdata": Description(
            en="SESSDATA cookie value for authenticated requests (optional)",
            zh="用于认证请求的SESSDATA cookie值（可选）",
        ),
    }


class TikTokLiveConfig(I18nMixin):
    """Configuration for TikTok Live platform."""

    unique_id: str = Field("", alias="unique_id")
    batch_size: int = Field(3, ge=1, le=10, alias="batch_size")
    max_pending_comments: int = Field(20, ge=1, le=100, alias="max_pending_comments")
    batch_window: float = Field(2.0, ge=0, le=10, alias="batch_window")
    min_interval: float = Field(2.0, alias="min_interval")
    response_timeout: float = Field(90.0, gt=0, alias="response_timeout")
    include_nickname: bool = Field(True, alias="include_nickname")
    blocked_words: List[str] = Field([], alias="blocked_words")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "unique_id": Description(
            en="TikTok username of the streamer (e.g. '@your_name')",
            zh="主播的TikTok用户名（例如 '@your_name'）",
        ),
        "batch_size": Description(
            en="Max distinct topics answered from a bounded comment digest",
            zh="每批评论摘要最多回复的不同话题数",
        ),
        "batch_window": Description(
            en="Seconds to collect a burst of comments before replying",
            zh="回复前收集一批评论的等待秒数",
        ),
        "max_pending_comments": Description(
            en="Max comments kept while the VTuber is busy (oldest dropped first)",
            zh="VTuber忙碌时最多保留的评论数（超出时丢弃最旧的）",
        ),
        "min_interval": Description(
            en="Minimum seconds between two VTuber replies",
            zh="两次VTuber回复之间的最短间隔（秒）",
        ),
        "response_timeout": Description(
            en="Warn after this many seconds without progress; never ends a spoken turn",
            zh="无进展时发出警告的秒数；不会中断正在播放的回复",
        ),
        "include_nickname": Description(
            en="Prefix each comment with the viewer's nickname",
            zh="在每条评论前加上观众昵称",
        ),
        "blocked_words": Description(
            en="Comments containing any of these words are ignored",
            zh="包含这些词的评论将被忽略",
        ),
    }


class YouTubeLiveConfig(TikTokLiveConfig):
    """Read public YouTube live chat; no credentials stored in config."""

    channel: str = Field("", alias="channel")
    video_url: str = Field("", alias="video_url")
    poll_interval: float = Field(30, ge=10, le=300, alias="poll_interval")
    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        **TikTokLiveConfig.DESCRIPTIONS,
        "channel": Description(
            en="YouTube channel URL or @handle", zh="YouTube频道网址或标识"
        ),
        "video_url": Description(
            en="Optional explicit livestream URL", zh="可选的直播网址"
        ),
        "poll_interval": Description(
            en="Seconds between checks while offline", zh="离线时检查间隔秒数"
        ),
    }


class LiveConfig(I18nMixin):
    """Configuration for live streaming platforms integration."""

    bilibili_live: BiliBiliLiveConfig = Field(
        BiliBiliLiveConfig(), alias="bilibili_live"
    )
    tiktok_live: TikTokLiveConfig = Field(TikTokLiveConfig(), alias="tiktok_live")
    active_platform: Literal["local", "youtube", "tiktok"] = "local"
    youtube_live: YouTubeLiveConfig = Field(default_factory=YouTubeLiveConfig)

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "active_platform": Description(
            en="Default local livestream chat reader", zh="默认直播聊天来源"
        ),
        "youtube_live": Description(
            en="YouTube live chat configuration", zh="YouTube直播聊天配置"
        ),
        "bilibili_live": Description(
            en="Configuration for BiliBili Live platform", zh="B站直播平台配置"
        ),
        "tiktok_live": Description(
            en="Configuration for TikTok Live platform", zh="TikTok直播平台配置"
        ),
    }
