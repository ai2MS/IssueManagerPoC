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
from click import pass_context
from llama_index.core import VectorStoreIndex, load_index_from_storage, SimpleKeywordTableIndex, KeywordTableIndex, SummaryIndex
from llama_index.core import SimpleDirectoryReader, StorageContext, Settings
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
    def get_all_documents():
        pass

    @abstractmethod
    def get_all_metadata():
        pass


class Files(Source):
    """Interface class to abstract files to documents converstion
    it uses SImpleDirectoryReader() to read all documents preserving their full_path

    """

    def __init__(self, path_: str):
        self.logger = get_default_logger(self.__class__.__name__)
        self.path = path_
        if not os.path.exists(self.path):
            os.makedirs(self.path, exist_ok=True)

    def get_all_documents(self):
        if os.path.exists(self.path) and dir_contains(self.path, recursive=True):
            self.logger.info("Issue directory <%s> found, using it...", self.path)
            documents = SimpleDirectoryReader(self.path, recursive=True).load_data()
        else:
            self.logger.info("Issue directory does not exist, creating it...")
            os.makedirs(self.path, exist_ok=True)
            documents = []
        return documents

    def get_all_metadata(self) -> dict:
        file_metadata = {}

        def scan_dir_populate_metadata(dir_path):
            nonlocal file_metadata
            for entry in os.scandir(dir_path):
                if entry.is_file():  # Check if it's a file
                    metadata = {
                        "file_size": entry.stat().st_size,
                        "last_modified_date": entry.stat().st_mtime
                    }
                    file_metadata[os.path.abspath(entry.path)] = metadata
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

    def connect_to_redis_stores(self):
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

    def create_index(self, documents, force: bool = False):
        # Check if the index already exists
        index_exists = False

        if force is True:
            self.logger.info("force=%s specified, flushing all in Redis", force)
            self.redis_client.execute_command("flushall")

        # list existing indexes
        index_list = self.redis_client.execute_command("FT._LIST")
        self.logger.debug("Existing indexes: %s", index_list)

        # if index already in the existing indexes list, check structure compatibility
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
                index_exists = True
            else:
                self.logger.warning(
                    "data in the index is imcompatible with defined schema: index_store=%s, instead of %s", stored_fields_set, defined_fields_set)
                # Drop the index and recreate it
                self.redis_client.execute_command("FT.DROPINDEX", f"{self.name}.vector")
                index_list = self.redis_client.execute_command("FT._LIST")
                self.logger.info("Index %s.vector dropped. Remaining indexes are:%s", self.name, index_list)
                index_exists = False

        self.storage_context = self.connect_to_redis_stores()

        if index_exists:
            new_documents = self.load_documents()

            vector_index = VectorStoreIndex.from_vector_store(
                vector_store=self.storage_context.vector_store
            )
            # Insert new documents to vector_index_store
            vector_index.insert_nodes(self.docs_to_nodes(new_documents))

            all_nodes = list(self.storage_context.docstore.docs.values())

            # refresh (or fully reload SummaryIndex)
            try:
                # load SummaryIndex from storage
                summary_index = load_index_from_storage(
                    storage_context=self.storage_context,
                    index_id=self.get_index_id_from_name(f"{self.name}_summary")
                )
                summary_index.refresh_ref_docs(new_documents)
            except Exception as e:
                self.logger.warning("Unable to load and refresh summaryindex from storage because of %s", e)
                # completely rebuild the index
                summary_index = SummaryIndex(
                    nodes=all_nodes,
                    storage_context=self.storage_context
                )
                self.set_index_id_name_mapping(f"{self.name}_summary", summary_index.index_id)

            # refresh (or fully reload KeywordTableIndex)
            try:
                # load KeywordTableIndex from storage
                keyword_index = load_index_from_storage(
                    storage_context=self.storage_context,
                    index_id=self.get_index_id_from_name(f"{self.name}_keyword")
                )
                keyword_index.refresh_ref_docs(new_documents)
            except Exception as e:
                self.logger.warning("Unable to load and refresh keywordindex from storage because of %s", e, exc_info=e)
                # completely rebuild the index
                keyword_index = SimpleKeywordTableIndex(
                    nodes=all_nodes,
                    storage_context=self.storage_context
                )
                self.set_index_id_name_mapping(f"{self.name}_keyword", keyword_index.index_id)

        else:
            # newly created index, so load data and create index.
            nodes = self.docs_to_nodes(documents)
            self.storage_context.docstore.add_documents(nodes)

            self.logger.debug("added %s docs to storage context", len(self.storage_context.docstore.docs))

            # build and load index from documents and storage context
            vector_index = VectorStoreIndex.from_documents(
                documents, storage_context=self.storage_context
            )
            # completely rebuild the index
            summary_index = SummaryIndex(
                nodes=all_nodes,
                storage_context=self.storage_context
            )
            self.set_index_id_name_mapping(f"{self.name}_summary", summary_index.index_id)

            keyword_index = SimpleKeywordTableIndex(
                nodes=all_nodes,
                storage_context=self.storage_context
            )
            self.set_index_id_name_mapping(f"{self.name}_keyword", keyword_index.index_id)

        # Create retrievers from each index
        summary_retriever = summary_index.as_retriever()
        vector_retriever = vector_index.as_retriever()
        keyword_retriever = keyword_index.as_retriever()

        # Combine retrievers using fusion
        fusion_retriever = QueryFusionRetriever(
            retrievers=[summary_retriever, vector_retriever, keyword_retriever],
            similarity_top_k=3,  # Number of results from each retriever
            num_queries=1,       # Number of query variations to generate
            mode="simple"        # Can be "simple" or "reciprocal_rank_fusion"
        )

        # Create a query engine from the fusion retriever
        fusion_query_engine = RetrieverQueryEngine.from_args(
            retriever=fusion_retriever
        )
        return fusion_query_engine

    def load_documents(self, force: bool = False):
        """Scan the given directory and load the files in it to the self.index doc store
        """

        def extract_stored_document_metadata(nodes) -> dict[str: dict]:
            """Extract metadata from stored document nodes."""
            stored_metadata = {}

            for node in nodes:
                # Check if the node has file_path in metadata
                if hasattr(node, "metadata") and "file_path" in node.metadata:
                    file_path = node.metadata["file_path"]
                    file_hash = node.metadata.get("file_hash", "") or node.hash
                    file_size = node.metadata.get("file_size", "")
                    file_date = node.metadata.get("last_modified_date", "")
                    stored_metadata[file_path] = {
                        "file_size": file_size,
                        "hash": file_hash,
                        "last_modified_date": file_date,
                        "node_id": node.node_id
                    }

            return stored_metadata

        file_metadata: dict = self.source.get_all_metadata()

        all_nodes = list(self.storage_context.docstore.docs.values())
        self.logger.debug("Found %s nodes in storage", len(all_nodes))
        stored_metadata = extract_stored_document_metadata(all_nodes)
        self.logger.debug("Found %s documents with file_path metadata", len(stored_metadata))

        files_to_remove = []
        files_to_add = []
        for file_path, metadata in file_metadata.items():
            if force:
                self.logger.debug("force=True specified, adding File %s ...", file_path)
                files_to_add.append(file_path)
            elif (file_path not in stored_metadata):
                self.logger.debug("File %s was not found in the docstore, will be added...", file_path)
                files_to_add.append(file_path)
            elif metadata["file_size"] != stored_metadata[file_path]["file_size"]:
                self.logger.debug("File %s in the docstore is different in size, will be replaced...", file_path)
                files_to_remove.append(file_path)
                files_to_add.append(file_path)
            elif (datetime.fromtimestamp(metadata["last_modified_date"]).strftime("%Y-%m-%d")
                  != stored_metadata[file_path]["last_modified_date"]):
                self.logger.debug("File %s mtime and hash do not match docstore, will be replaced...")
                files_to_remove.append(file_path)
                files_to_add.append(file_path)
            else:
                # if modified date is the same, or has are the same, then don't process it
                self.logger.debug("File %s was not changed compare to docstore, skipping", file_path)

        for stored_file_path, metadata in stored_metadata.items():
            if force:
                self.logger.debug("force=True specified, removing File %s ...", stored_file_path)
                files_to_remove.append(stored_file_path)
            elif stored_file_path not in file_metadata:
                self.logger.debug("force=True specified, removing File %s ...", stored_file_path)
                files_to_remove.append(stored_file_path)

        remove_count = 0
        for node in all_nodes:
            node_id = node.node_id
            if (hasattr(node, "metadata") and node.metadata.get("file_path") in files_to_remove):
                remove_count += 1
                del self.storage_context.docstore.docs[node_id]
                if hasattr(self.storage_context.vector_store, "delete"):
                    self.storage_context.vector_store.delete(node_id)
        self.logger.debug("Removed %s documents from index", remove_count)

        new_documents = []
        if files_to_add:
            docreader = SimpleDirectoryReader(input_files=files_to_add)
            new_documents = docreader.load_data()

            self.logger.debug("Updated docstore with %s new/modified documents", len(files_to_add))
        return new_documents

    def __init__(self, source: Source, index_schema: dict | None = None) -> None:
        self.logger = get_default_logger(self.__class__.__name__)
        self.index_schema = index_schema
        if (not hasattr(self, "name")):
            # incase inherited instance did not define name
            if "index" in index_schema:
                # if index_schema has ["index"]["name"], use as self.name
                self.name = index_schema["index"].get("name", "default").removesuffix(".vector")
            else:
                # otherwise use "default"
                self.name = self.__class__.__name__

        self.source = source

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
            # self.storage_context = StorageContext.from_defaults(persist_dir=self.persist_dir)
            if f"{self.name}.vector".encode('utf-8') not in self.redis_client.execute_command("FT._LIST"):
                raise IndexError("Vector Index not found in Redis")
            redis_keys = self.redis_client.execute_command("keys", f"{self.name}*")

            for store_type in ["doc", "index"]:
                if f"{self.name}.{store_type}".encode('utf-8') not in redis_keys:
                    raise IndexError(f"{store_type} store is not found in Redis")

            # if all 3 stores are found to be in Redis already:
            self.storage_context = self.connect_to_redis_stores()

            vector_index = VectorStoreIndex.from_vector_store(
                vector_store=self.storage_context.vector_store
            )
            summary_index = load_index_from_storage(self.storage_context, index_id=f"{self.name}_summary")
            keyword_index = load_index_from_storage(self.storage_context, index_id=f"{self.name}_keyword")

            # Create retrievers from each index
            summary_retriever = summary_index.as_retriever()
            vector_retriever = vector_index.as_retriever()
            keyword_retriever = keyword_index.as_retriever()

            # Combine retrievers using fusion
            fusion_retriever = QueryFusionRetriever(
                retrievers=[summary_retriever, vector_retriever, keyword_retriever],
                similarity_top_k=3,  # Number of results from each retriever
                num_queries=1,       # Number of query variations to generate
                mode="simple"        # Can be "simple" or "reciprocal_rank_fusion"
            )

            # Create a query engine from the fusion retriever
            fusion_query_engine = RetrieverQueryEngine.from_args(
                retriever=fusion_retriever
            )

        except Exception:
            # if storage_context can't be loaded from disk, call create_index() to build it.
            self.query_engine = self.create_index(source.get_all_documents())

        self.logger.debug(f"initialized Issue Index Vector Store...")

        # self.persist_dir = persist_dir or os.path.join(config.INDEX_STORE_PERSIST_DIR, self.name)
        self.storage_context.persist()

    def query(self, question: str) -> str:
        """query the index about the content indexed"""

        response = self.query_engine.query(question)

        self.logger.debug(f"answered query '{question}'")
        return response

    def refresh(self) -> str:
        # Load the updated documents

        # Query using the fusion engine
        response = self.query_engine.query("Tell me about renewable energy")


if __name__ == "__main__":
    import doctest
    doctest.testmod()
