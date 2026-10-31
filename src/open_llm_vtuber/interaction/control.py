"""Local process control is authenticated by a host-only secret, never an actor role."""

import secrets
from fastapi import Request, HTTPException
from .ingress import control_token


def install_local_control(app, profile):
    @app.post("/api/runtime/shutdown")
    async def shutdown(request: Request):
        if request.client.host not in {
            "127.0.0.1",
            "::1",
        } or not secrets.compare_digest(
            request.headers.get("X-Mao-Control", ""), control_token(profile)
        ):
            raise HTTPException(
                status_code=403, detail="Local host authorization required"
            )
        runner = getattr(app.state, "runtime_runner", None)
        if runner is None:
            raise HTTPException(status_code=503, detail="Runner unavailable")
        runner.should_exit = True
        return {"status": "stopping"}
