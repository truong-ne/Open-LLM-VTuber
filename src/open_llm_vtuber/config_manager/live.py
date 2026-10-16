from pydantic import Field
from typing import Dict, ClassVar, List
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
    batch_size: int = Field(3, alias="batch_size")
    max_pending_comments: int = Field(20, alias="max_pending_comments")
    min_interval: float = Field(2.0, alias="min_interval")
    response_timeout: float = Field(90.0, alias="response_timeout")
    include_nickname: bool = Field(True, alias="include_nickname")
    blocked_words: List[str] = Field([], alias="blocked_words")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "unique_id": Description(
            en="TikTok username of the streamer (e.g. '@your_name')",
            zh="主播的TikTok用户名（例如 '@your_name'）",
        ),
        "batch_size": Description(
            en="Max number of recent comments merged into one VTuber reply",
            zh="每次回复合并的最近评论数上限",
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
            en="Seconds to wait for a reply to finish before sending the next comments",
            zh="等待回复结束的最长时间（秒），超时后发送下一批评论",
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


class LiveConfig(I18nMixin):
    """Configuration for live streaming platforms integration."""

    bilibili_live: BiliBiliLiveConfig = Field(
        BiliBiliLiveConfig(), alias="bilibili_live"
    )
    tiktok_live: TikTokLiveConfig = Field(TikTokLiveConfig(), alias="tiktok_live")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "bilibili_live": Description(
            en="Configuration for BiliBili Live platform", zh="B站直播平台配置"
        ),
        "tiktok_live": Description(
            en="Configuration for TikTok Live platform", zh="TikTok直播平台配置"
        ),
    }
