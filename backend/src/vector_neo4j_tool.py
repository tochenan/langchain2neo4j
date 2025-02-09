from __future__ import annotations
from database import Neo4jDatabase
from langchain.embeddings import OpenAIEmbeddings
from langchain.chains.base import Chain
import os

from typing import Any, Dict, List

from pydantic import Field
from logger import logger

neo4j_url = os.environ.get('NEO4J_URL')
neo4j_user = os.environ.get('NEO4J_USER')
neo4j_pass = os.environ.get('NEO4J_PASS')

vector_search = """
WITH $embedding AS e
MATCH (m)
WHERE m.embedding IS NOT NULL AND size(m.embedding) = 1536
WITH m, gds.similarity.cosine(m.embedding, e) AS similarity
ORDER BY similarity DESC LIMIT 5
CALL {
  WITH m
  MATCH (m)-[r]->(target)
  RETURN coalesce(m.name, m.synonyms) + " " + type(r) + " " + coalesce(target.name, target.synonyms) AS result
  UNION
  WITH m
  MATCH (m)<-[r]-(target)
  RETURN coalesce(target.name, target.synonyms) + " " + type(r) + " " + coalesce(m.name, m.synonyms) AS result
}
RETURN result LIMIT 100
"""


class LLMNeo4jVectorChain(Chain):
    """Chain for question-answering against a graph."""

    graph: Neo4jDatabase = Field(exclude=True)
    input_key: str = "query"  #: :meta private:
    output_key: str = "result"  #: :meta private:
    embeddings: OpenAIEmbeddings = OpenAIEmbeddings()

    @property
    def input_keys(self) -> List[str]:
        """Return the input keys.
        :meta private:
        """
        return [self.input_key]

    @property
    def output_keys(self) -> List[str]:
        """Return the output keys.
        :meta private:
        """
        _output_keys = [self.output_key]
        return _output_keys

    def _call(self, inputs: Dict[str, str]) -> Dict[str, Any]:
        """Embed a question and do vector search."""
        question = inputs[self.input_key]
        logger.debug(f"Vector search input: {question}")
        embedding = self.embeddings.embed_query(question)
        self.callback_manager.on_text(
            "Vector search embeddings:", end="\n", verbose=self.verbose
        )
        self.callback_manager.on_text(
            embedding[:5], color="green", end="\n", verbose=self.verbose
        )
        context = self.graph.query(
            vector_search, {'embedding': embedding}) 
        return {self.output_key: context}


if __name__ == '__main__':
    from langchain.chat_models import ChatOpenAI

    llm = ChatOpenAI(temperature=0.0)
    database = Neo4jDatabase(host=neo4j_url,
                             user=neo4j_user, password=neo4j_pass)
    chain = LLMNeo4jVectorChain(llm=llm, verbose=True, graph=database)

    output = chain.run(
        "What is related to diabetes?"
    )

    print(output)
