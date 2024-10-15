from os import environ
from textwrap import dedent
from typing import Optional, List
from dotenv import load_dotenv

from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as HTTPSpanExporter,
)
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor

from llama_index.core.workflow import (
    Workflow,
    Event,
    StartEvent,
    StopEvent,
    Context,
    step,
)
from llama_index.core.prompts import PromptTemplate
from llama_index.core.chat_engine.types import ChatMessage
from llama_index.llms.openai import OpenAI

from models import ExtractedQuery
from dynamic_few_shot import dynamic_few_shot_fn

load_dotenv()


environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"api_key={environ.get('PHOENIX_API_KEY')}"

# Add Arize Phoenix
span_phoenix_processor = SimpleSpanProcessor(
    HTTPSpanExporter(endpoint="https://app.phoenix.arize.com/v1/traces")
)

# Add them to the tracer
tracer_provider = trace_sdk.TracerProvider()
tracer_provider.add_span_processor(span_processor=span_phoenix_processor)

# Instrument the application
LlamaIndexInstrumentor().instrument(tracer_provider=tracer_provider)


class StreamEvent(Event):
    token: str


class PromptEvent(Event):
    query: ExtractedQuery


class OrderFetchEvent(Event):
    query: ExtractedQuery


class DataFetchedEvent(Event):
    data: str


class ExamplesFetchedEvent(Event):
    examples: str


class PromptCreatedEvent(Event):
    prompt: PromptTemplate


class CustomerSupportWorkflow(Workflow):
    def __init__(
        self,
        timeout: int = 360,
        chat_history: Optional[List[ChatMessage]] = None,
        last_message: Optional[str] = None,
    ):
        super().__init__(timeout=timeout)
        self.chat_history = chat_history or []
        self.last_message = last_message
        self.chat_history_str = "\n".join(
            [f"{msg.role}: {msg.content}" for msg in self.chat_history]
        )
        self.llm = OpenAI(model="gpt-4o-mini")

    @step()
    async def extract_query(
        self, ev: StartEvent, ctx: Context
    ) -> OrderFetchEvent | PromptEvent:
        prompt = PromptTemplate(
            dedent(
                """
                From the previous chat history between human and assistant, and the last message from the human, rewrite the last message from the human as a standalone query that doesn't rely on any context from the previous chat history. And also extract any information available that can be used to fulfill human's query. Follow the provided structure. Below are the chat history and the last message from the human:
                <chat_history>
                {chat_history}
                </chat_history>
                <last_message>
                {last_message}
                </last_message>
                """
            )
        )
        structured_query = await self.llm.astructured_predict(
            output_cls=ExtractedQuery,
            prompt=prompt,
            last_message=self.last_message,
            chat_history=self.chat_history_str,
        )

        await ctx.set("structured_query", structured_query)

        if structured_query.order_id:
            await ctx.set("wait_for_data", True)
            ctx.send_event(OrderFetchEvent(query=structured_query))

        return PromptEvent(query=structured_query)

    @step
    async def fetch_data(self, ev: OrderFetchEvent, ctx: Context) -> DataFetchedEvent:
        from db import get_order

        order = get_order(ev.query.order_id)
        order_str = (
            f"Order details for order id {ev.query.order_id}:\n<data>\n{order}\n</data>"
        )
        await ctx.set("data", order_str)
        return DataFetchedEvent(data=order_str)

    @step
    async def create_prompt(self, ev: PromptEvent, ctx: Context) -> PromptCreatedEvent:
        prompt = PromptTemplate(
            dedent(
                """
                Following is the conversation history between human and assistant.
                ---
                {chat_history}
                ---
                Here is the human's question:
                <query>
                {query}
                </query>
                Now using the information below, answer the human's query. If there are example query-response pairs, then you must follow the same response structure as the examples below.
                {data}
                {examples}
                ---
                Query to answer:{query}
                Your Response: """
            ),
            function_mappings={
                "examples": dynamic_few_shot_fn,
            },
        )

        return PromptCreatedEvent(prompt=prompt)

    @step
    async def answer_query(
        self, ev: PromptCreatedEvent | DataFetchedEvent, ctx: Context
    ) -> StopEvent:
        wait_for_data = await ctx.get("wait_for_data", False)
        events_to_wait_for = [PromptCreatedEvent]
        if wait_for_data:
            events_to_wait_for.append(DataFetchedEvent)
        events = ctx.collect_events(ev, events_to_wait_for)
        if not events:
            return None

        resp_event = events[0]

        data = ""
        if wait_for_data:
            data_event = events[1]
            data = data_event.data

        structured_query = await ctx.get("structured_query")
        response_generator = await self.llm.astream(
            prompt=resp_event.prompt,
            chat_history=self.chat_history_str,
            data=data,
            query=structured_query.standalone_query,
        )
        async for token in response_generator:
            # print(token, end="")
            ctx.write_event_to_stream(StreamEvent(token=token))
        return StopEvent(result={"response": "done"})
