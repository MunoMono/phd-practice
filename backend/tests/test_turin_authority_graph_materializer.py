import sys
import unittest
from pathlib import Path
BACKEND_ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BACKEND_ROOT))
from app.services.turin_authority_graph_materializer import TurinAuthorityGraphMaterializer

class GraphMaterializerTests(unittest.TestCase):
    def test_only_exact_controlled_metadata_and_identifiers_create_links(self):
        documents=[{"document_id":"doc-171","pid":"media","authority_data":{"keywords":["Bruce Archer"],"record_title":"Job 171 records"}}]
        authorities=[{"authority_type":"agent_employment","authority_id":"BA","label":"Bruce Archer"},{"authority_type":"ddr_projects","authority_id":"171","label":"Interface project"}]
        links=TurinAuthorityGraphMaterializer.build_relations(documents,authorities)
        self.assertEqual({item["relation_type"] for item in links},{"PERSON_ASSOCIATED_WITH_SOURCE","PROJECT_SOURCE","SOURCE_COLLECTION"})
        person=next(item for item in links if item["relation_type"]=="PERSON_ASSOCIATED_WITH_SOURCE")
        self.assertEqual(person["trigger_field"],"keywords")
        self.assertEqual(person["trigger_value_normalized"],"bruce archer")
    def test_non_exact_name_does_not_create_link(self):
        links=TurinAuthorityGraphMaterializer.build_relations([{"document_id":"doc","authority_data":{"keywords":["Archer"]}}],[{"authority_type":"agent_employment","authority_id":"BA","label":"Bruce Archer"}])
        self.assertEqual([item for item in links if item["authority_type"]=="agent_employment"],[])

if __name__=='__main__':unittest.main()