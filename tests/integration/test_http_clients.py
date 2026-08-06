import unittest

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiohttp import ClientSession, web


class ExternalHttpIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.requests = []

        async def telegram(request: web.Request) -> web.Response:
            self.requests.append(await request.post())
            return web.json_response(
                {
                    "ok": True,
                    "result": {
                        "id": 42,
                        "is_bot": True,
                        "first_name": "BotFunilm",
                        "username": "botfunilm_test_bot",
                    },
                }
            )

        async def json_response(request: web.Request) -> web.Response:
            return web.json_response({"status": "ok"})

        app = web.Application()
        app.router.add_post("/bot{token}/getMe", telegram)
        app.router.add_get("/json", json_response)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await self.site.start()
        port = self.site._server.sockets[0].getsockname()[1]
        self.base_url = f"http://127.0.0.1:{port}"

    async def asyncTearDown(self) -> None:
        await self.runner.cleanup()

    async def test_aiohttp_uses_real_transport(self) -> None:
        async with ClientSession() as session:
            async with session.get(f"{self.base_url}/json") as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(await response.json(), {"status": "ok"})

    async def test_aiogram_parses_real_bot_api_response(self) -> None:
        api = TelegramAPIServer.from_base(self.base_url, is_local=True)
        session = AiohttpSession(api=api)
        bot = Bot("123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi", session=session)
        try:
            user = await bot.get_me()
        finally:
            await session.close()

        self.assertEqual(user.id, 42)
        self.assertEqual(user.username, "botfunilm_test_bot")
        self.assertEqual(len(self.requests), 1)
