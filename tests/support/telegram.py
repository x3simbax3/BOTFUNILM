from types import SimpleNamespace
from unittest.mock import AsyncMock


class StateStub:
    def __init__(self, data: dict | None = None) -> None:
        self.data = data or {}
        self.state = None
        self.cleared = False

    async def clear(self) -> None:
        self.data.clear()
        self.state = None
        self.cleared = True

    async def set_state(self, state) -> None:
        self.state = state

    async def get_data(self) -> dict:
        return self.data

    async def set_data(self, data: dict) -> None:
        self.data = data

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)


class SentMessageStub:
    def __init__(self, message_id: int) -> None:
        self.message_id = message_id
        self.last_text = None

    async def edit_text(self, text: str, **kwargs) -> None:
        self.last_text = text


class MessageStub:
    def __init__(self, text: str | None = "Title", message_id: int = 10) -> None:
        self.text = text
        self.message_id = message_id
        self.answers = []
        self.photo_answers = []
        self.edit_text_calls = []
        self.photo = []
        self.deleted = False
        self.from_user = SimpleNamespace(id=123)
        self.chat = SimpleNamespace(id=123)
        self.bot = SimpleNamespace(delete_message=AsyncMock())

    async def answer(self, text: str, **kwargs) -> SentMessageStub:
        stub = SentMessageStub(100 + len(self.answers) + len(self.photo_answers))
        self.answers.append({"text": text, "stub": stub, **kwargs})
        return stub

    async def answer_photo(self, photo: str, **kwargs) -> SentMessageStub:
        stub = SentMessageStub(200 + len(self.answers) + len(self.photo_answers))
        self.photo_answers.append({"photo": photo, "stub": stub, **kwargs})
        return stub

    async def edit_text(self, text: str, **kwargs) -> None:
        self.edit_text_calls.append({"text": text, **kwargs})

    async def delete(self) -> None:
        self.deleted = True


class CallbackStub:
    def __init__(
        self,
        data: str | None,
        message: MessageStub | None = None,
    ) -> None:
        self.data = data
        self.message = message
        self.from_user = SimpleNamespace(id=123)
        self.bot = SimpleNamespace(
            me=AsyncMock(return_value=SimpleNamespace(username="BotFunilmBot"))
        )
        self.answers = []

    async def answer(self, text: str | None = None, **kwargs) -> None:
        self.answers.append({"text": text, **kwargs})
