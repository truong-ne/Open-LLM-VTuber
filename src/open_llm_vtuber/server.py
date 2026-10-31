"""
Open-LLM-VTuber Server
========================
This module contains the WebSocket server for Open-LLM-VTuber, which handles
the WebSocket connections, serves static files, and manages the web tool.
It uses FastAPI for the server and Starlette for static file serving.
"""

import os
import asyncio
import shutil
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response
from starlette.staticfiles import StaticFiles as StarletteStaticFiles

from .routes import init_client_ws_route, init_webtool_routes, init_proxy_route
from .service_context import ServiceContext
from .config_manager.utils import Config
from .live.vua_tieng_viet import WordGameService
from .live.singing import SingingService


# Create a custom StaticFiles class that adds CORS headers
class CORSStaticFiles(StarletteStaticFiles):
    """
    Static files handler that adds CORS headers to all responses.
    Needed because Starlette StaticFiles might bypass standard middleware.
    """

    async def get_response(self, path: str, scope):
        if self.html and self.directory and path.lstrip("/") in {"", ".", "index.html"}:
            index = Path(self.directory) / "index.html"
            if index.is_file():
                html = index.read_text(encoding="utf-8")
                bridge = '<script type="module" src="/web-tool/mao-5070/delivery-bridge.mjs"></script>'
                html = html.replace("<head>", "<head>" + bridge, 1)
                return Response(
                    html,
                    media_type="text/html",
                    headers={
                        "Cache-Control": "no-store",
                        "Access-Control-Allow-Origin": "*",
                    },
                )
        response = await super().get_response(path, scope)

        # Add CORS headers to all responses
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"

        if path.endswith(".js"):
            response.headers["Content-Type"] = "application/javascript"

        return response


class AvatarStaticFiles(CORSStaticFiles):
    """
    Avatar files handler with security restrictions and CORS headers
    """

    async def get_response(self, path: str, scope):
        allowed_extensions = (".jpg", ".jpeg", ".png", ".gif", ".svg")
        if not any(path.lower().endswith(ext) for ext in allowed_extensions):
            return Response("Forbidden file type", status_code=403)
        response = await super().get_response(path, scope)
        return response


class WebSocketServer:
    """
    API server for Open-LLM-VTuber. This contains the websocket endpoint for the client, hosts the web tool, and serves static files.

    Creates and configures a FastAPI app, registers all routes
    (WebSocket, web tools, proxy) and mounts static assets with CORS.

    Args:
        config (Config): Application configuration containing system settings.
        default_context_cache (ServiceContext, optional):
            Pre‑initialized service context for sessions' service context to reference to.
            **If omitted, `initialize()` method needs to be called to load service context.**

    Notes:
        - If default_context_cache is omitted, call `await initialize()` to load service context cache.
        - Use `clean_cache()` to clear and recreate the local cache directory.
    """

    def __init__(self, config: Config, default_context_cache: ServiceContext = None):
        self.config = config
        self.word_game = WordGameService(require_presentation=True)
        self.singing = SingingService()
        self.autonomy = None
        self.proxy_handler = None

        @asynccontextmanager
        async def managed_services_lifespan(app):
            self.word_game.configure_speech(self.default_context_cache.tts_engine)
            await self.word_game.start()
            await self.singing.start()
            learning_task = None
            autonomy_task = None
            experience_task = None
            hybrid = getattr(self.default_context_cache.agent_engine, "_hybrid", None)
            if hybrid and hybrid.config.interaction_enabled:
                from .experience.worker import ExperienceWorker
                from .interaction.repository import Journal

                await asyncio.to_thread(Journal(hybrid.store).recover, True)

                self.experience_worker = ExperienceWorker(hybrid.store)
                experience_task = asyncio.create_task(self.experience_worker.run())
            if (
                hybrid
                and hybrid.config.learning_enabled
                and not hybrid.config.interaction_enabled
            ):
                from .agent.hybrid.learning import DailyLearning

                learning_task = asyncio.create_task(DailyLearning(hybrid.store).run())
            if hybrid and hybrid.config.autonomy.enabled:
                from .agent.hybrid.autonomy import AutonomyService

                self.autonomy = AutonomyService(hybrid.config, busy=self._autonomy_busy)
                self.default_context_cache.autonomy = self.autonomy
                autonomy_task = asyncio.create_task(self.autonomy.run())
            try:
                yield
            finally:
                if experience_task:
                    experience_task.cancel()
                    await asyncio.gather(experience_task, return_exceptions=True)
                if autonomy_task:
                    autonomy_task.cancel()
                    await asyncio.gather(autonomy_task, return_exceptions=True)
                    await self.autonomy.close()
                    self.default_context_cache.autonomy = None
                if learning_task:
                    learning_task.cancel()
                    await asyncio.gather(learning_task, return_exceptions=True)
                try:
                    await self.word_game.stop()
                finally:
                    try:
                        await self.singing.stop()
                    finally:
                        await self.default_context_cache.close()

        @asynccontextmanager
        async def lifespan(app):
            hybrid = getattr(self.default_context_cache.agent_engine, "_hybrid", None)
            lease = None
            if hybrid and hybrid.config.interaction_enabled:
                from .interaction.repository import Journal

                lease = await asyncio.to_thread(Journal(hybrid.store).acquire_lease)
            try:
                async with managed_services_lifespan(app):
                    yield
            finally:
                if lease:
                    await asyncio.to_thread(lease.close)

        self.app = FastAPI(title="Open-LLM-VTuber Server", lifespan=lifespan)
        from .interaction.control import install_local_control

        install_local_control(
            self.app, os.environ.get("MAO_RUNTIME_PROFILE", "local_companion")
        )

        @self.app.get("/api/vuatiengviet/state")
        async def word_game_state():
            return self.word_game.game.snapshot()

        self.default_context_cache = (
            default_context_cache or ServiceContext()
        )  # Use provided context or initialize a new empty one waiting to be loaded
        # It will be populated during the initialize method call

        # Add global CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Include routes, passing the context instance
        # The context will be populated during the initialize step
        client_routes = init_client_ws_route(
            default_context_cache=self.default_context_cache
        )
        self.client_handler = client_routes.mao_handler
        self.app.include_router(client_routes)
        self.app.include_router(
            init_webtool_routes(default_context_cache=self.default_context_cache),
        )

        # Initialize and include proxy routes if proxy is enabled
        system_config = config.system_config
        if hasattr(system_config, "enable_proxy") and system_config.enable_proxy:
            # Construct the server URL for the proxy
            host = system_config.host
            port = system_config.port
            server_url = f"ws://{host}:{port}/client-ws"
            proxy_routes = init_proxy_route(
                server_url=server_url,
                word_game=self.word_game,
                singing=self.singing,
                activity=self._autonomy_input,
            )
            self.proxy_handler = proxy_routes.mao_handler
            self.app.include_router(proxy_routes)

        # Mount cache directory first (to ensure audio file access)
        if not os.path.exists("cache"):
            os.makedirs("cache")
        self.app.mount(
            "/cache",
            CORSStaticFiles(directory="cache"),
            name="cache",
        )

        # Mount static files with CORS-enabled handlers
        self.app.mount(
            "/live2d-models",
            CORSStaticFiles(directory="live2d-models"),
            name="live2d-models",
        )
        self.app.mount(
            "/bg",
            CORSStaticFiles(directory="backgrounds"),
            name="backgrounds",
        )
        self.app.mount(
            "/avatars",
            AvatarStaticFiles(directory="avatars"),
            name="avatars",
        )

        # Mount web tool directory separately from frontend
        self.app.mount(
            "/web-tool",
            CORSStaticFiles(directory="web_tool", html=True),
            name="web_tool",
        )

        # Mount main frontend last (as catch-all)
        self.app.mount(
            "/",
            CORSStaticFiles(directory="frontend", html=True),
            name="frontend",
        )

    def _autonomy_input(self, message):
        if self.autonomy:
            self.autonomy.observe_input(message)

    def _autonomy_busy(self):
        proxy = self.proxy_handler
        return bool(
            any(
                task and not task.done()
                for task in self.client_handler.current_conversation_tasks.values()
            )
            or (
                proxy
                and (
                    proxy.message_queue.conversation_active
                    or proxy.message_queue.has_pending_messages()
                )
            )
            or self.word_game.game.active
            or self.singing.active
        )

    async def initialize(self):
        """Asynchronously load the service context from config.
        Calling this function is needed if default_context_cache was not provided to the constructor."""
        await self.default_context_cache.load_from_config(self.config)

    @staticmethod
    def clean_cache():
        """Clean the cache directory by removing and recreating it."""
        cache_dir = "cache"
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
            os.makedirs(cache_dir)
