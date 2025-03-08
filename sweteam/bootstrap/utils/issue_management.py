"""
Issue management system, where issues are stored and indexed for querying
Issue are created, updated and can be listed, and read. 
The issues are saved as json files in a recursive directory structure where 
the directory names represents the hierarchy of the issues (and sub-issues).

The issues are indexed using the llama_index library, which provides a vector store
index for querying the issues. The index is created from the documents in the issue directory.

"""
import json
from requests.auth import HTTPBasicAuth
import requests
import os
from tracemalloc import stop
from idna import decode
from redisvl.schema import IndexSchema

from .log import get_default_logger

from ..config import config

from .doc_indexes import (embedding_dim, Source, Files, IndexStore, Document)


class JIRA(Source):
    def __init__(self):
        self.logger = get_default_logger(self.__class__.__name__)
        self.namespace = f"{config.PROJECT_NAME}_Jira"
        self.auth = HTTPBasicAuth(config.JIRA_USERNAME, config.JIRA_API_KEY)
        self.base_url = config.JIRA_BASE_URL
        self.issues_to_reconcile = []

    def get_all_documents(self, doc_id_field_name: str = "id") -> list[Document]:
        documents = []
        issue_list = [i for i in self.list_issues()]
        jira_batch_size = 10
        for batch_begin in range(0, len(issue_list), jira_batch_size):
            issue_list_batch = issue_list[batch_begin:batch_begin+jira_batch_size]
            issue_batch = self.retrieve_issues(issue_list=issue_list_batch)
            document_batch = []
            for issue in issue_batch:
                issue_json = {f"doc_id": f"{issue[doc_id_field_name]}",
                              "extra_info": issue, "text": issue['description']}
                issue_document = Document(text=issue_json)
                issue_document.metadata[f"{config.PROJECT_NAME}_doc_id"] = f"{issue[doc_id_field_name]}"
                issue_document.metadata["doc_size"] = len(issue)
                issue_document.metadata["updated_at"] = issue['updated']
                document_batch.append(issue_document)
            documents.extend(document_batch)

        return documents

    def get_documents(self, doc_id_list: list = [], doc_id_field_name: str = "id") -> list[Document]:
        documents = []
        issue_list = doc_id_list
        jira_batch_size = 10
        for batch_begin in range(0, len(issue_list), jira_batch_size):
            issue_list_batch = issue_list[batch_begin:batch_begin+jira_batch_size]
            issue_batch = self.retrieve_issues(issue_list=issue_list_batch)
            document_batch = []
            for issue in issue_batch:
                issue_json = {f"doc_id": f"{issue[doc_id_field_name]}",
                              "extra_info": issue, "text": issue['description']}
                issue_document = Document(text=issue_json)
                issue_document.metadata[f"{config.PROJECT_NAME}_doc_id"] = f"{issue[doc_id_field_name]}"
                issue_document.metadata["doc_size"] = len(issue)
                issue_document.metadata["updated_at"] = issue['updated']
                document_batch.append(issue_document)
            documents.extend(document_batch)

        return documents

    def get_all_metadata(self) -> dict:
        issue_list = self.list_issues(jql='created >= startOfDay("-30d") ORDER BY created DESC')
        issue_dict = {}
        for issue in issue_list:
            _doc_id= issue.get("id") or issue.get("doc_id") or issue[f"{config.PROJECT_NAME}_doc_id"]

            metadata = {f'{config.PROJECT_NAME}_doc_id': issue["fields"].get(f"{config.PROJECT_NAME}_doc_id") or _doc_id,
                        f'{config.PROJECT_NAME}_doc_updated_at': issue["fields"]["updated"],
                        f'{config.PROJECT_NAME}_doc_hash': "",
                        f'{config.PROJECT_NAME}_doc_size': len(str(issue)),
                        'key': issue["key"]} 
            issue_dict[issue[f"{config.PROJECT_NAME}_doc_id"]] = metadata
        return issue_dict

    def list_issues(self, jql: str = 'created >= startOfDay("-3d") ORDER BY created DESC', force: bool = False):
        """return list of issue ids by jsql query
        Args:
            jql: the query to run, default value is issues created in the past 3 days DESC
            force: if force a reconcile, default is False, which means won't force reconcil, 
                   so some recently updated issues may not have their most recent updates included
        Returns:
            list of issue ids
        """
        if force:
            # to be implemented by leveraging Jira webhook that listen to issue change events
            # then, the list of issue ids that are changed will be included in the reconcileIssues list.
            reconcileIssues = self.issues_to_reconcile
        else:
            reconcileIssues = []

        returned_issues = []

        url = f"{self.base_url}/search/jql"
        headers = {
            "Accept": "application/json"
        }

        maxResults = 500
        fields = "*navigable"
        nextPageToken = None

        while True:
            query = {
                'jql': jql,
                'nextPageToken': nextPageToken,
                'fields': 'id,key,updated',
                'maxResults': maxResults,
                'reconcileIssues': reconcileIssues
            }

            response = requests.request(
                "GET",
                url,
                headers=headers,
                params=query,
                auth=self.auth
            )
            try:
                result = json.loads(response.text)
            except Exception as e:
                self.logger.warning("Jira jql response run into %s converting to JSON: %s", e,  response)
                result = {}

            returned_issues.extend(result)
            if (nextPageToken := result.get("nextPageToken", None)) is None:
                # Last page will return null as nextPageToken
                break

        return returned_issues

    def retrieve_issues(self, issue_list: list[str] = []):
        url = f"{self.base_url}/issue/bulkfetch"
        # pull the issue details
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        payload = json.dumps({
            "expand": [
                "names"
            ],
            "fields": [
                "*navigable"
            ],
            "fieldsByKeys": False,
            "issueIdsOrKeys": issue_list,
            "properties": []
        })

        response = requests.request(
            "POST",
            url,
            data=payload,
            headers=headers,
            auth=self.auth
        )

        returned_issues = json.loads(response.text).get("issues", [])
        issues_to_return = []
        for ri in returned_issues:
            # separate customfields into its own sub group
            issue_temp = {"id": ri["id"],
                          "key": ri["key"],
                          "customfields": {}}
            for f in ri["fields"]:
                if f.startswith("customfield"):
                    issue_temp["customfields"][f] = (ri["fields"][f])
                else:
                    issue_temp[f] = ri["fields"][f]

            issues_to_return.append(issue_temp)
        return issues_to_return


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
        self.name: str = "issue_man"
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
        issue_dir = os.path.join(config.PROJECT_NAME, "Jira.jsons", "subset")
        issue_files = Files(issue_dir)
        # jira_issues = JIRA()
        super().__init__(issue_files, issue_index_schema)

    def create(self):
        pass

    def continuous_query(self):
        while question := input("\n### What do you want to ask?\n:"):
            response = self.query(question)
            print(response.response)


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
