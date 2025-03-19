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
import aiohttp
import nest_asyncio

import asyncio

from redisvl.schema import IndexSchema

from ..config import config
from .log import get_default_logger
from .doc_indexes import (embedding_dim, Source, Files, IndexStore, Document)
from . import get_dot_notation_value

nest_asyncio.apply()

class JIRA(Source):
    def __init__(self, namespace:str = "", field_mapping:dict = {}):
        self.logger = get_default_logger(self.__class__.__name__)
        self.namespace = namespace or f"{config.PROJECT_NAME}"
        self.auth = aiohttp.BasicAuth(config.JIRA_USERNAME, config.JIRA_API_KEY)
        self.base_url = config.JIRA_BASE_URL
        self.issues_to_reconcile = []
        self.field_mapping = field_mapping or {
            "id": "id",
            "status": "status.name",
            "title": "summary",
            "priority": "priority.name",
            "created_at": "created",
            "updated_at": "updated"
        }
        self.session = None

    async def _get_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession(auth=self.auth)
        return self.session

    def get_issue_metadata(self, issue: dict) -> dict:
        key_prefix = f"{self.namespace}"
        metadata={}
        for k, v in self.field_mapping.items():
            metadata[key_prefix + k]=get_dot_notation_value(issue, v, 'n/a')
        return metadata

    async def get_all_documents(self) -> list[Document]:
        """Retrieve all Jira documents that would be listed in list_issues()
        Will repeat Jira call as long as there are still next pages
        """
        documents = []
        issue_list = [get_dot_notation_value(i, self.field_mapping['id']) for i in await self.list_issues()]
        jira_batch_size = 10
        for batch_begin in range(0, len(issue_list), jira_batch_size):
            issue_list_batch = issue_list[batch_begin:batch_begin+jira_batch_size]
            issue_batch = await self.retrieve_issues(issue_list=issue_list_batch)
            document_batch = []
            for issue in issue_batch:
                doc_id = get_dot_notation_value(issue,self.field_mapping['id'])
                extra_info = self.get_issue_metadata(issue=issue)
                text = json.dumps(issue)
                issue_document = Document(doc_id=doc_id, extra_info=extra_info, text=text)
                document_batch.append(issue_document)
            documents.extend(document_batch)

        return documents

    async def get_documents(self, doc_id_list: list = []) -> list[Document]:
        documents = []
        issue_list = doc_id_list
        jira_batch_size = 10
        for batch_begin in range(0, len(issue_list), jira_batch_size):
            issue_list_batch = issue_list[batch_begin:batch_begin+jira_batch_size]
            issue_batch = await self.retrieve_issues(issue_list=issue_list_batch)
            document_batch = []
            for issue in issue_batch:
                doc_id = get_dot_notation_value(issue,self.field_mapping['id'])
                extra_info = self.get_issue_metadata(issue=issue)
                text = json.dumps(issue)
                issue_document = Document(doc_id=doc_id, extra_info=extra_info, text=text)
                document_batch.append(issue_document)
            documents.extend(document_batch)

        return documents

    async def get_all_metadata(self) -> dict:
        issue_list = await self.list_issues(jql='created >= startOfDay("-30d") ORDER BY created DESC')
        issue_dict = {}
        for issue in issue_list:
            _doc_id = get_dot_notation_value(issue,self.field_mapping['id']) or issue.get('id') or issue.get('key')

            metadata={}
            for k, v in self.field_mapping.items():
                metadata[self.namespace + k]=get_dot_notation_value(issue, v)

            issue_dict[_doc_id] = metadata
        return issue_dict

    async def list_issues(self, jql: str = 'created >= startOfDay("-3d") ORDER BY created DESC', force: bool = False):
        """return list of issue ids by jsql query
        Args:
            jql: the query to run, default value is issues created in the past 3 days DESC
            force: if force a reconcile, default is False, which means won't force reconcil, 
                   so some recently updated issues may not have their most recent updates included
        Returns:
            list of issue ids
        """
        if force:
            reconcileIssues = self.issues_to_reconcile
        else:
            reconcileIssues = []

        returned_issues = []
        session = await self._get_session()

        url = f"{self.base_url}/search/jql"
        headers = {
            "Accept": "application/json"
        }

        maxResults = 500
        fields = "*navigable"
        nextPageToken = "Not Yet Known"

        while nextPageToken:
            query = {
                'jql': jql,
                'fields': 'id,key,updated,status,summary,priority,created',
                'maxResults': maxResults,
                'reconcileIssues': reconcileIssues
            }
            if nextPageToken != "Not Yet Known":
                query["nextPageToken"] = nextPageToken

            async with session.get(url, headers=headers, params=query) as response:
                try:
                    result = await response.json()
                except Exception as e:
                    self.logger.warning("Jira jql response run into %s converting to JSON: %s", e, await response.text())
                    result = {}
                
                issues = result.get('issues', [])
                for issue in issues:
                    for k, v in issue.get("fields", {}).items():
                        issue[k] = v
                    del issue['fields']
                returned_issues.extend(issues)
                if (nextPageToken := result.get("nextPageToken", None)) is None:
                    break

        return returned_issues

    async def retrieve_issues(self, issue_list: list[str] = []):
        url = f"{self.base_url}/issue/bulkfetch"
        session = await self._get_session()
        
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        payload = {
            "expand": ["names","changelog"],
            "fields": ["*navigable","comment"],
            "fieldsByKeys": False,
            "issueIdsOrKeys": issue_list,
            "properties": []
        }

        async with session.post(url, headers=headers, json=payload) as response:
            result = await response.json()
            returned_issues = result.get("issues", [])
            
        issues_to_return = []
        def flattern_comment(content_obj, content_str: str = "") -> str:
            if isinstance(content_obj, dict):
                for content in content_obj.get("content", []):
                    content_str += flattern_comment(content)

            match content_obj.get('type', 'n/a'):
                case 'doc':
                    return content_str + "\n===EOF===\n"
                case 'paragraph':
                    return content_str + "\n\n"
                case 'text':
                    return content_obj.get("text") or str(content_obj)
                case 'inclienCard':
                    return str(content_obj.get('attrs'))
                case 'media':
                    media_attrs = content_obj.get('attrs', {})
                    media_type = media_attrs.get('type')
                    media_details = ""
                    for k, v in content_obj.get('attrs', {}).items():
                        if k in ['type']: continue
                        media_details += "," if media_details else ""
                        media_details += f"{k}:{v}"
                    return f"media:<{media_type}: <{media_details}>, {content_str}>"
                case 'mediaSingle':
                    return f"mediaSingle:<{content_str}>"
                case 'mediaGroup':
                    return f"mediaGroup:<{content_str}>"
                case 'hardBreak':
                    return "\n"
                case _:
                    return str(content_obj)

        for ri in returned_issues:
            issue_temp = {"id": ri["id"],
                          "key": ri["key"],
                          "customfields": {}}
            for fk, fv in ri["fields"].items():
                if fk.startswith("customfield"):
                    issue_temp["customfields"][fk] = fv
                elif fk == "comment" and "comments" in fv:
                    comments = []
                    for comment in fv["comments"]:
                        comment['author'] = comment['author']['displayName']
                        comment['date'] = comment.get('updated') or comment.get('created')
                        comment['content'] = flattern_comment(comment["body"])
                        comments.append(comment)
                    
                    issue_temp["comments"] = comments
                else:
                    issue_temp[fk] = fv

            issues_to_return.append(issue_temp)
        return issues_to_return

    async def __aenter__(self):
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):     
        if self.session:
            await self.session.close()
            self.session = None


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
        namespace = "IssManJira/"

        issue_index_schema = IndexSchema.from_dict(
            {
                "index": {
                    "name": f"{namespace}vector",
                    "prefix": "issidx",
                    "key_separator": ":",
                },
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
        jira_issues = JIRA(namespace=namespace)
        super().__init__(jira_issues, issue_index_schema, namespace=namespace)

    async def create(self):
        pass

    async def continuous_query(self):
        while question := input("\n### What do you want to ask?\n:"):
            response = await self.query(question)
            print(response.response)


async def main():
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        issue_manager = await IssueManager()

        match command:
            case "summary":
                response = await issue_manager.query(
                    "What is the highlevel summary of the current status of the project as a whole?")
                print(response)
            case "refresh":
                result = await issue_manager.refresh()
                print(f"Refresh completed: {result}")
            case "query":
                prompt = sys.argv[2]
                response = await issue_manager.query(prompt)
                print(response)
            case "test":
                doctest.testmod()
            case _:
                print("supported commnads: summary, refresh, test")
                doctest.testmod()
    else:
        print("supported commnads: summary, refresh, test")
        doctest.testmod()


if __name__ == "__main__":
    import sys
    import doctest
    asyncio.run(main())
