"""
Issue management system, where issues are stored and indexed for querying
Issue are created, updated and can be listed, and read. 
The issues are saved as json files in a recursive directory structure where 
the directory names represents the hierarchy of the issues (and sub-issues).

The issues are indexed using the llama_index library, which provides a vector store
index for querying the issues. The index is created from the documents in the issue directory.

"""
import os
from tracemalloc import stop
from idna import decode
from redisvl.schema import IndexSchema

from ..config import config

from .doc_indexes import (embedding_dim, Files, IndexStore)


class IssueManager(IndexStore):
    """This is the class for issue index store that derived from IndexStore

    """

    # Issue Manager should be a singleton within a project
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.name: str = "issue_indexes"
        issue_index_schema = IndexSchema.from_dict(
            {
                # customize basic index specs
                "index": {
                    "name": f"{self.name}.vector",
                    "prefix": "issidx",
                    "key_separator": ":",
                },
                # customize fields that are indexed
                "fields": [
                    # required fields for llamaindex
                    {"type": "tag", "name": "id"},
                    {"type": "tag", "name": "doc_id"},
                    {"type": "text", "name": "text"},
                    # custom metadata fields
                    {"type": "text", "name": "last_modified_date"},
                    {"type": "tag", "name": "file_path"},
                    # custom vector field definition for cohere embeddings
                    {
                        "type": "vector",
                        "name": "vector",
                        "attrs": {
                            "dims": embedding_dim,
                            "algorithm": "hnsw",
                            "distance_metric": "cosine",
                        },
                    },
                ],
            }
        )
        issue_dir = os.path.join(config.PROJECT_NAME, config.ISSUE_BOARD_DIR)
        issue_files = Files(issue_dir)
        super().__init__(issue_files, issue_index_schema)


if __name__ == "__main__":
    import sys
    import doctest
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        issue_manager = IssueManager()

        match command:
            case "summary":
                response = issue_manager.query(
                    "What is the highlevel summary of the current status of the project as a whole?")
                print(response)
            case "refresh":
                result = issue_manager.refresh()
                print(f"Refresh completed: {result}")
            case "query":
                prompt = sys.argv[2]
                response = issue_manager.query(prompt)
                print(response)
            case "test":
                doctest.testmod()
            case _:
                print("supported commnads: summary, refresh, test")
                doctest.testmod()
    else:
        print("supported commnads: summary, refresh, test")
        doctest.testmod()
