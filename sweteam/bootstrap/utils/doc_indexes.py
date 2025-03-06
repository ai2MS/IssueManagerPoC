"""
Issue management system, where issues are stored and indexed for querying
Issue are created, updated and can be listed, and read. 
The issues are saved as json files in a recursive directory structure where 
the directory names represents the hierarchy of the issues (and sub-issues).

The issues are indexed using the llama_index library, which provides a vector store
index for querying the issues. The index is created from the documents in the issue directory.

"""
from abc import ABC, abstractmethod
import os
import json
from datetime import datetime
from pydoc import Doc
from click import pass_context
from llama_index.core import (VectorStoreIndex, load_index_from_storage,
                              SimpleKeywordTableIndex, KeywordTableIndex, SummaryIndex,
                              SimpleDirectoryReader, StorageContext, Settings, Document)
from llama_index.core.node_parser import SentenceSplitter, JSONNodeParser
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.retrievers import QueryFusionRetriever

from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.redis import RedisVectorStore
from llama_index.storage.index_store.redis import RedisIndexStore
from llama_index.storage.docstore.redis import RedisDocumentStore

from redis import Redis

from ..config import config
from .log import get_logger, get_default_logger
from .file_utils import dir_contains


# bge-m3 embedding model uses 1024 dimmesions
embedding_dim = 1024
ollama_embedding = OllamaEmbedding(
    model_name=config.OLLAMA_EMBEDDING_MODEL,
    base_url=config.OLLAMA_HOST,
    ollama_additional_kwargs={"mirostat": 0},
)

Settings.embed_model = ollama_embedding

Settings.llm = Ollama(model=config.OLLAMA_DEFAULT_BASE_MODEL,
                      base_url=config.OLLAMA_HOST,
                      request_timeout=360.0)


class Source(ABC):
    @abstractmethod
    def get_all_documents() -> list[Document]:
        pass

    @abstractmethod
    def get_all_metadata() -> list:
        pass


class Files(Source):
    """Interface class to abstract files to documents converstion
    it uses SImpleDirectoryReader() to read all documents preserving their full_path

    """

    def __init__(self, path_: str, namespace: str = ""):
        self.logger = get_default_logger(self.__class__.__name__)
        self.namespace = namespace or config.PROJECT_NAME
        self.path = path_
        if not os.path.exists(self.path):
            self.logger.info("Issue directory does not exist, creating it...")
            os.makedirs(self.path, exist_ok=True)

    def get_all_documents(self) -> list[str]:
        """return list of llama-index Document objects with _doc_id, doc_size and updated_at special meta data
        """
        documents = []
        if os.path.exists(self.path) and dir_contains(self.path, recursive=True):
            self.logger.info("Issue directory <%s> found, using it...", self.path)
            documents = SimpleDirectoryReader(self.path, recursive=True).load_data()
            for document in documents:
                if hasattr(document, "metadata"):
                    file_path = document.metadata["file_path"]
                    document.metadata[f"{self.namespace}_doc_id"] = file_path
                    document.metadata["doc_size"] = document.metadata["file_size"]
                    updated_at = os.stat(file_path).st_mtime
                    document.metadata["updated_at"] = updated_at
                else:
                    self.warning("Document %s does not have metadata, this is strange!", document)

        return documents

    def get_documents(self, document_list: list) -> list[Document]:
        documents = []
        if any([os.path.exists(f) for f in document_list]):
            documents = SimpleDirectoryReader(input_files=document_list)
            for document in documents:
                if hasattr(document, "metadata"):
                    file_path = document.metadata["file_path"]
                    document.metadata[f"{self.namespace}_doc_id"] = file_path
                    document.metadata["doc_size"] = document.metadata["file_size"]
                    updated_at = os.stat(file_path).st_mtime
                    document.metadata["updated_at"] = updated_at
                else:
                    self.warning("Document %s does not have metadata, this is strange!", document)

        return documents

    def get_all_metadata(self) -> dict:
        """return metadata that are compatible with {doc_id: {doc_size:int, updated_at:datetime}}
        """
        file_metadata = {}

        def scan_dir_populate_metadata(dir_path):
            nonlocal file_metadata
            for entry in os.scandir(dir_path):
                if entry.is_file():  # Check if it's a file
                    _doc_id = os.path.abspath(entry.path)
                    metadata = {
                        f"{self.namespace}_doc_id": _doc_id,
                        "doc_size": entry.stat().st_size,
                        "updated_at": entry.stat().st_mtime
                    }
                    file_metadata[_doc_id] = metadata
                elif entry.is_dir():  # Recurse into subdirectories
                    scan_dir_populate_metadata(entry.path)

        scan_dir_populate_metadata(self.path)

        return file_metadata


class IndexStore():
    """Using docstore, vector_store and index_store to facilitate queries contents of documents
    This implementation uses Redis for all three stores. Once documents are read and loaded, 
    will create 3 indexes: SummaryIndex, KeywordTableIndex and VectorIndex. 
    Then create a fusion query engine to enable query using all 3 indexes. 
    """

    def get_index_id_from_name(self, name: str) -> str:
        """retrieve mapping between a given index_name to index_id. 
        The map should be persisted across program start/restart so that we can continue 
        Typical implementation (as below) is using Redis K:V pair
        """
        namespace = f"{self.name}:registry" if hasattr(self, "name") else "index_registry"
        return self.redis_client.get(f"{namespace}:{name}")

    def set_index_id_name_mapping(self, name: str, id: str):
        """Record index name to id mapping. A typeical implementation is using Redis
        """
        namespace = f"{self.name}:registry" if hasattr(self, "name") else "index_registry"
        self.redis_client.set(f"{namespace}:{name}", id)

    def docs_to_nodes(self, documents):
        nodes = []
        try:
            nodes = JSONNodeParser().get_nodes_from_documents(documents)
            self.logger.debug("Loaded %s document as %s nodes.", len(documents), len(nodes))
        except Exception as e:
            self.logger.warning("could not load all files as json, parsing individually...")
            for document in documents:
                try:
                    # validate if the document is proper JSON
                    json.JSONDecoder().decode(document)
                    nodes_ = JSONNodeParser().get_nodes_from_documents(document)
                    self.logger.debug("document parsed as %s JSON nodes", len(nodes_))
                    nodes.extend(nodes_)
                except Exception:
                    nodes_ = SentenceSplitter().get_nodes_from_documents(documents)
                    self.logger.debug("document parsed as %s plain text nodes", len(nodes_))
                    nodes.extend(nodes_)
        return nodes

    def connect_to_redis_stores(self) -> StorageContext:
        # create the vector store wrapper
        vector_store = RedisVectorStore(redis_client=self.redis_client, overwrite=True,
                                        schema=self.index_schema)

        index_store = RedisIndexStore.from_redis_client(
            redis_client=self.redis_client, namespace=f"{self.name}.index")

        doc_store = RedisDocumentStore.from_redis_client(
            redis_client=self.redis_client, namespace=f"{self.name}.doc")
        # load storage context

        storage_context = StorageContext.from_defaults(
            docstore=doc_store, vector_store=vector_store, index_store=index_store)

        return storage_context

    def create_index(self, force: bool = False):

        if force is True:
            self.logger.info("force=%s specified, flushing all in Redis", force)
            self.redis_client.execute_command("flushall")

        # Check if the index already exists
        # list existing indexes
        index_list = self.redis_client.execute_command("FT._LIST")
        self.logger.debug("Existing indexes: %s", index_list)

        # if vector index already in the existing indexes list, check structure compatibility
        if f"{self.name}.vector".encode('utf-8') in index_list:
            self.logger.info("Index %s.vector already exists, checking compatibility...", self.name)
            # FT.INFO returns a list of key-value pairs if index exists.
            info = self.redis_client.execute_command("FT.INFO", f"{self.name}.vector")
            # self.logger.debug("Index info: %s", info)

            # Extract the stored schema from FT.INFO output.
            info_dict = {info[i]: info[i+1] for i in range(0, len(info), 2)}
            # self.logger.debug("info dict: %s", info_dict)
            stored_attributes = info_dict.get(b"attributes", [])
            # self.logger.debug("Stored attributes: %s", stored_attributes)
            # Normalize Redis stored attributes: create a set with (name, type)
            list_of_dict_attributes = [{attr[i]: attr[i+1] for i in range(0, len(attr), 2)}
                                       for attr in stored_attributes]
            stored_fields_set = {(attr.get(b"identifier").decode('utf-8').lower(), attr.get(b"type").decode().lower())
                                 for attr in list_of_dict_attributes}
            # Retrieve the defined schema as a dict. Assume the IndexSchema has a to_dict() method.
            defined_schema = self.index_schema.to_dict() if hasattr(
                self.index_schema, "to_dict") else self.index_schema
            defined_fields = defined_schema.get("fields", [])
            defined_fields_set = {(field.get("name"), field.get("type")) for field in defined_fields}
            if stored_fields_set == defined_fields_set:
                self.logger.info("Index %s.vector is compatible with defined schema", self.name)
                # should check changes and refresh file if needed.
            else:
                self.logger.warning(
                    "data in the index is imcompatible with defined schema: index_store=%s, instead of %s", stored_fields_set, defined_fields_set)
                # Drop the index and recreate it
                self.redis_client.execute_command("FT.DROPINDEX", f"{self.name}.vector")
                index_list = self.redis_client.execute_command("FT._LIST")
                self.logger.info("Index %s.vector dropped. Remaining indexes are:%s", self.name, index_list)

        # since we used redis_client directly manipulate Redis content, let's reconnect:
        self.storage_context = self.connect_to_redis_stores()

        vector_index = VectorStoreIndex.from_vector_store(
            vector_store=self.storage_context.vector_store
        )

        self.indexes["vector_index"] = vector_index
        all_nodes = []

        # try load summary index, if fail, create empty one
        try:
            # load SummaryIndex from storage
            summary_index = load_index_from_storage(
                storage_context=self.storage_context,
                index_id=self.get_index_id_from_name(f"{self.name}_summary")
            )
            # summary_index.refresh_ref_docs(new_documents)
        except Exception as e:
            self.logger.warning("Unable to load and refresh summaryindex from storage because of %s", e)
            # completely rebuild the index
            summary_index = SummaryIndex(
                nodes=all_nodes,
                storage_context=self.storage_context
            )
            self.set_index_id_name_mapping(f"{self.name}_summary", summary_index.index_id)
        self.indexes["summary_index"] = summary_index

        # try load keyword index, if fail, create empty one
        try:
            # load KeywordTableIndex from storage
            keyword_index = load_index_from_storage(
                storage_context=self.storage_context,
                index_id=self.get_index_id_from_name(f"{self.name}_keyword")
            )
            # keyword_index.refresh_ref_docs(new_documents)
        except Exception as e:
            self.logger.warning("Unable to load and refresh keywordindex from storage because of %s", e, exc_info=e)
            # completely rebuild the index
            keyword_index = SimpleKeywordTableIndex(
                nodes=all_nodes,
                storage_context=self.storage_context
            )
            self.set_index_id_name_mapping(f"{self.name}_keyword", keyword_index.index_id)
        self.indexes["keyword_index"] = keyword_index

        # Create retrievers from each index
        summary_retriever = summary_index.as_retriever()
        vector_retriever = vector_index.as_retriever()
        keyword_retriever = keyword_index.as_retriever()

        # Combine retrievers using fusion
        fusion_retriever = QueryFusionRetriever(
            retrievers=[summary_retriever, vector_retriever, keyword_retriever],
            similarity_top_k=5,  # Number of results from each retriever
            num_queries=1,       # Number of query variations to generate
            mode="simple"        # Can be "simple" or "reciprocal_rank_fusion"
        )

        # Create a query engine from the fusion retriever
        fusion_query_engine = RetrieverQueryEngine.from_args(
            retriever=fusion_retriever
        )

        return fusion_query_engine

    def load_documents(self, document_list: list[Document] = [], force: bool = False):
        """Scan the given directory and load the files in it to the self.index doc store
        """

        def extract_stored_document_metadata(nodes) -> dict[str: dict]:
            """Extract metadata from stored document nodes."""
            stored_metadata = {}

            for node in nodes:
                # Check if the node has _doc_id in metadata
                if hasattr(node, "metadata") and f"{self.namespace}_doc_id" in node.metadata:
                    _doc_id = node.metadata[f"{self.namespace}_doc_id"]
                    doc_hash = node.metadata.get("file_hash", "") or node.hash
                    doc_size = node.metadata.get("doc_size", -1)
                    updated_at = node.metadata.get("updated_at", 0)
                    stored_metadata[_doc_id] = {
                        "doc_size": doc_size,
                        "hash": doc_hash,
                        "updated_at": updated_at,
                        "node_id": node.node_id
                    }

            return stored_metadata

        source_docs_metadata: dict = self.source.get_all_metadata()

        all_nodes = list(self.storage_context.docstore.docs.values())
        self.logger.debug("Found %s nodes in storage", len(all_nodes))
        stored_metadata = extract_stored_document_metadata(all_nodes)
        self.logger.debug("Found %s documents with _doc_id metadata", len(stored_metadata))

        docs_to_remove = []
        docs_to_add = []
        for _doc_id, metadata in source_docs_metadata.items():
            if force:
                self.logger.debug("force=True specified, adding File %s ...", _doc_id)
                docs_to_add.append(_doc_id)
            elif (_doc_id not in stored_metadata):
                self.logger.debug("Source doc %s was not found in the docstore, will be added...", _doc_id)
                docs_to_add.append(_doc_id)
            elif metadata["doc_size"] != stored_metadata[_doc_id]["doc_size"]:
                self.logger.debug("Source doc %s in the docstore is different in size, will be replaced...", _doc_id)
                docs_to_remove.append(_doc_id)
                docs_to_add.append(_doc_id)
            elif (metadata["updated_at"] != stored_metadata[_doc_id]["updated_at"]):
                self.logger.debug("Source doc %s mtime do not match docstore, will be replaced...")
                docs_to_remove.append(_doc_id)
                docs_to_add.append(_doc_id)
            else:
                self.logger.debug("Source doc %s was not changed compare to docstore, skipping", _doc_id)

        for stored__doc_id, metadata in stored_metadata.items():
            if force:
                self.logger.debug("force=True specified, removing File %s ...", stored__doc_id)
                docs_to_remove.append(stored__doc_id)
            elif stored__doc_id not in source_docs_metadata:
                self.logger.debug("force=True specified, removing File %s ...", stored__doc_id)
                docs_to_remove.append(stored__doc_id)

        remove_count = 0
        for node in all_nodes:
            node_id = node.node_id
            if (hasattr(node, "metadata") and node.metadata.get(f"{self.namespace}_doc_id") in docs_to_remove):
                remove_count += 1
                del self.storage_context.docstore.docs[node_id]
                # or
                # self.storage_context.docstore.delete_document(node_id)
                # also delete from vector store
                if hasattr(self.storage_context.vector_store, "delete"):
                    self.storage_context.vector_store.delete(node_id)
                # and delete from index
        self.logger.debug("Removed %s documents from index", remove_count)

        new_documents = []
        if docs_to_add:
            ############ need to fix: this shoudl not read doc from file
            # this needs to be converting a text to a document  
            # ############
            
            new_documents = [d for d in document_list if d[f"{self.namespace}_doc_id"] in docs_to_add]

            self.logger.debug("Updated docstore with %s new/modified documents", len(docs_to_add))

        # Insert new documents to vector_index_store
        self.indexes["vector_index"].insert_nodes(self.docs_to_nodes(new_documents))
        self.indexes["summary_index"].insert_nodes(self.docs_to_nodes(new_documents))
        self.indexes["keyword_index"].insert_nodes(self.docs_to_nodes(new_documents))

        return None

    def __init__(self, source: Source, index_schema: dict | None = None,
                 namespace: str = "", reset: bool = False) -> None:
        self.logger = get_default_logger(self.__class__.__name__)
        self.namespace = namespace or config.PROJECT_NAME
        self.index_schema = index_schema
        if (not hasattr(self, "name")):
            # incase inherited instance did not define name
            if "index" in index_schema:
                # if index_schema has ["index"]["name"], use it as self.name, or use self.namespace as self.name
                self.name = index_schema["index"].get("name", self.namespace).removesuffix(".vector")
            else:
                # otherwise use "default"
                self.name = f"{self.namespace}:{self.__class__.__name__}"

        self.source = source

        self.indexes = {str: SummaryIndex | KeywordTableIndex | VectorStoreIndex}

        # Redis client is needed to perform other activities like cleaning up
        self.logger.debug("creating Redis client... %s:%s", config.REDIS_HOST, config.REDIS_PORT)
        self.redis_client = Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            password=config.REDIS_PASSWORD,
            username=config.REDIS_USERNAME,
            db=0
        )
        self.logger.debug("Redis client created: %s", self.redis_client.ping())

        try:

            if f"{self.name}.vector".encode('utf-8') not in self.redis_client.execute_command("FT._LIST"):
                raise IndexError("Vector Index not found in Redis")

            redis_keys = self.redis_client.execute_command("keys", f"{self.name}*")
            for store_type in ["doc", "index"]:
                if f"{self.name}.{store_type}".encode('utf-8') not in redis_keys:
                    raise IndexError(f"{store_type} store is not found in Redis")

            # if all 3 stores are found to be in Redis already:
            self.storage_context = self.connect_to_redis_stores()

            self.indexes["vector_index"] = VectorStoreIndex.from_vector_store(
                vector_store=self.storage_context.vector_store
            )
            self.indexes["summary_index"] = load_index_from_storage(
                self.storage_context, index_id=f"{self.name}_summary")
            self.indexes["keyword_index"] = load_index_from_storage(
                self.storage_context, index_id=f"{self.name}_keyword")

            # Create retrievers from each index
            summary_retriever = self.indexes["summary_index"].as_retriever()
            vector_retriever = self.indexes["vector_index"].as_retriever()
            keyword_retriever = self.indexes["keyword_index"].as_retriever()

            # Combine retrievers using fusion
            fusion_retriever = QueryFusionRetriever(
                retrievers=[summary_retriever, vector_retriever, keyword_retriever],
                similarity_top_k=3,  # Number of results from each retriever
                num_queries=1,       # Number of query variations to generate
                mode="simple"        # Can be "simple" or "reciprocal_rank_fusion"
            )

            # Create a query engine from the fusion retriever
            self.query_engine = RetrieverQueryEngine.from_args(
                retriever=fusion_retriever
            )

        except Exception:
            # if storage_context can't be loaded from storage, call create_index() to build it.
            self.query_engine = self.create_index(force=(reset is True))

        self.logger.debug(f"initialized Issue Index Vector Store...")

        self.load_documents(source.get_all_documents(), force=reset)
        self.logger.debug("Loaded / refreshed documents for all indexes")

        # self.persist_dir = persist_dir or os.path.join(config.INDEX_STORE_PERSIST_DIR, self.name)
        self.storage_context.persist()

    def query(self, question: str) -> str:
        """query the index about the content indexed"""

        response = self.query_engine.query(question)

        self.logger.debug("answered query '%s' with '%s'", question, response)
        return response

    def refresh(self) -> str:
        # Load the updated documents

        # Query using the fusion engine
        response = self.query_engine.query("Tell me about renewable energy")


if __name__ == "__main__":
    import doctest
    doctest.testmod()
