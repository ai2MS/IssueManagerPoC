import os
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from ..config import config
from .log import get_logger

ollama_embedding = OllamaEmbedding(
    model_name="llama3.2",
    base_url=config.OLLAMA_HOST,
    ollama_additional_kwargs={"mirostat": 0},
)

# pass_embedding = ollama_embedding.get_text_embedding_batch(
#     ["This is a passage!", "This is another passage"], show_progress=True
# )
# print(pass_embedding)

Settings.embed_model = OllamaEmbedding(model_name="llama3.2",
                                       base_url=config.OLLAMA_HOST,
                                       ollama_additional_kwargs={"mirostat": 0},
                                       )
Settings.llm = Ollama(model="llama3.2",
                      base_url=config.OLLAMA_HOST,
                      request_timeout=360.0)


class IssueVectorStore():
    """vector store of issues to check for duplicates and provide summaries"""

    def __init__(self) -> None:
        self.logger = get_logger(self.__class__.__name__)
        issue_dir = os.path.join(config.PROJECT_NAME, config.ISSUE_BOARD_DIR)
        documents = SimpleDirectoryReader(issue_dir, recursive=True).load_data()

        self.index = VectorStoreIndex.from_documents(documents)

        self.logger.debug(f"initialized Issue Index Vector Store...")

    def query(self, question: str) -> str:
        """query the index about the content indexed"""
        query_engine = self.index.as_query_engine()

        response = query_engine.query(question)

        self.logger.debug(f"answered query '{question}'")
        return response

    def refresh(self) -> str:
        # Load the updated documents
        updated_documents = SimpleDirectoryReader("path/to/your/directory").load_data()

        # Refresh the index
        refreshed_docs = self.index.refresh_ref_docs(updated_documents)

        self.logger.debug(f"updated the Issue Index Vector Store with {refreshed_docs}")
        return f"{refreshed_docs}"


if __name__ == "__main__":
    print(f"Searching index returned:", IssueVectorStore().query(
        "What is the highlevel summary of the current status of the project as a whole?"))
