import os
import json
from dotenv import load_dotenv

from llama_index.core import (
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)
from llama_index.core.schema import TextNode
from llama_index.embeddings.openai import OpenAIEmbedding

load_dotenv()

# Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")
EMBED_MODEL = "text-embedding-3-small"


def create_or_load_index():
    persist_dir = "./.data"
    if os.path.exists(persist_dir):
        print("Loading index from storage")
        return load_index_from_storage(
            StorageContext.from_defaults(persist_dir=persist_dir)
        )

    print("Creating index")
    nodes = []
    dataset = {}
    with open("./dataset.json", "r") as f:
        dataset = json.load(f)

    for query, response in dataset.items():
        node = TextNode(text=query)
        node.metadata["response"] = response
        node.excluded_embed_metadata_keys.append("response")
        nodes.append(node)

    index = VectorStoreIndex(nodes, embed_model=OpenAIEmbedding(model=EMBED_MODEL))
    index.storage_context.persist(persist_dir)
    return index


def dynamic_few_shot_fn(**kwargs):
    query_str = kwargs["query"]
    index = create_or_load_index()
    retriever = index.as_retriever(
        top_k=2, embed_model=OpenAIEmbedding(model=EMBED_MODEL)
    )
    nodes = retriever.retrieve(query_str)
    filtered_nodes = list(filter(lambda node: node.score > 0.5, nodes))
    few_shot_examples = []
    for node in filtered_nodes:
        query = node.text
        response = node.metadata["response"]
        few_shot_examples.append(f"Query: {query}\nResponse: {response}")

    to_return = (
        (
            f"Below are some examples of the structure of your response:\n"
            + "\n---\n".join(few_shot_examples)
        )
        if few_shot_examples
        else ""
    )

    return to_return
