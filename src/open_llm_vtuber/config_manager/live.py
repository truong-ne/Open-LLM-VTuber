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


class NeuroGameConfig(I18nMixin):
    """Configuration for the Neuro Game API bridge (games made for Neuro-sama)."""

    host: str = Field("localhost", alias="host")
    port: int = Field(8000, alias="port")
    model: str = Field("", alias="model")
    temperature: float = Field(0.3, alias="temperature")
    max_retries: int = Field(3, alias="max_retries")
    max_context: int = Field(20, alias="max_context")
    act_on_context: bool = Field(False, alias="act_on_context")
    comment_on_context: bool = Field(True, alias="comment_on_context")
    comment_on_actions: bool = Field(True, alias="comment_on_actions")
    max_pending_comments: int = Field(3, alias="max_pending_comments")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "host": Description(en="Host the game connects to", zh="游戏连接的主机地址"),
        "port": Description(
            en="Port the game connects to (NEURO_SDK_WS_URL=ws://host:port)",
            zh="游戏连接的端口（NEURO_SDK_WS_URL=ws://host:port）",
        ),
        "model": Description(
            en="LLM used to pick actions; empty = same model as the character",
            zh="用于选择游戏动作的LLM；留空则与角色使用同一模型",
        ),
        "temperature": Description(
            en="Sampling temperature for picking actions (lower = steadier play)",
            zh="选择动作时的温度（越低越稳定）",
        ),
        "max_retries": Description(
            en="Retries when the chosen action is invalid or fails",
            zh="动作无效或失败时的重试次数",
        ),
        "max_context": Description(
            en="Number of recent game messages kept for decisions",
            zh="决策时保留的最近游戏消息数",
        ),
        "act_on_context": Description(
            en="Let the character act on game events without being asked by the game",
            zh="允许角色在游戏未要求时主动执行动作",
        ),
        "comment_on_context": Description(
            en="Let the character talk about game events",
            zh="让角色评论游戏事件",
        ),
        "comment_on_actions": Description(
            en="Let the character talk about the actions it takes",
            zh="让角色评论自己执行的动作",
        ),
        "max_pending_comments": Description(
            en="Max game texts kept while the character is talking (oldest dropped first)",
            zh="角色说话时最多保留的游戏消息数（超出时丢弃最旧的）",
        ),
    }


class LiveConfig(I18nMixin):
    """Configuration for live streaming platforms integration."""

    bilibili_live: BiliBiliLiveConfig = Field(
        BiliBiliLiveConfig(), alias="bilibili_live"
    )
    tiktok_live: TikTokLiveConfig = Field(TikTokLiveConfig(), alias="tiktok_live")
    neuro_game: NeuroGameConfig = Field(NeuroGameConfig(), alias="neuro_game")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "bilibili_live": Description(
            en="Configuration for BiliBili Live platform", zh="B站直播平台配置"
        ),
        "tiktok_live": Description(
            en="Configuration for TikTok Live platform", zh="TikTok直播平台配置"
        ),
        "neuro_game": Description(
            en="Neuro Game API bridge for games made for Neuro-sama",
            zh="Neuro游戏API桥接（适配为Neuro-sama制作的游戏）",
        ),
    }
