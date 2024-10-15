from pydantic import BaseModel, field_validator, Field
from typing import List, Any

from llama_index.core.llms import ChatMessage, MessageRole


class Message(BaseModel):
    role: MessageRole
    content: str


class ChatData(BaseModel):
    messages: List[Message]
    data: Any = None

    class Config:
        json_schema_extra = {
            "example": {
                "messages": [
                    {
                        "role": "user",
                        "content": "What standards for letters exist?",
                    }
                ]
            }
        }

    @field_validator("messages")
    def messages_must_not_be_empty(cls, v):
        if len(v) == 0:
            raise ValueError("Messages must not be empty")
        return v

    def get_last_message_content(self) -> str:
        """
        Get the content of the last message along with the data content if available.
        Fallback to use data content from previous messages
        """
        if len(self.messages) == 0:
            raise ValueError("There is not any message in the chat")
        last_message = self.messages[-1]
        message_content = last_message.content
        return message_content

    def get_history_messages(
        self,
    ) -> List[ChatMessage]:
        """
        Get the history messages
        """
        chat_messages = [
            ChatMessage(role=message.role, content=message.content)
            for message in self.messages[:-1]
        ]
        return chat_messages

    def is_last_message_from_user(self) -> bool:
        return self.messages[-1].role == MessageRole.USER


class ExtractedQuery(BaseModel):
    standalone_query: str = Field(
        ..., description="The standalone query from all the previous chat messages."
    )
    order_id: int | None = Field(
        None,
        description="The order id extracted from the latest user message. If not found, it will be None.",
    )
