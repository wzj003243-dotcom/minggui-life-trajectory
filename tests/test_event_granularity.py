import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"research"))
from ontology.event_granularity_v1 import Granularity, classify, enrich


class GranularityTests(unittest.TestCase):
    def test_high_volume_output_kept_distinct(self):
        self.assertEqual(classify("creation","creation.music_release_group"),
                         Granularity.REPEATED_OUTPUT)
        self.assertEqual(classify("creation","creation.scholar_work"),
                         Granularity.REPEATED_OUTPUT)
        self.assertEqual(classify("performance","performance.music_event"),
                         Granularity.REPEATED_OUTPUT)

    def test_major_transitions(self):
        self.assertEqual(classify("relationship","relationship.marriage"),
                         Granularity.LIFE_TRANSITION)
        self.assertEqual(classify("migration","migration.cross_region"),
                         Granularity.LIFE_TRANSITION)
        self.assertEqual(classify("creation","creation.organization_founded"),
                         Granularity.LIFE_TRANSITION)
        self.assertEqual(classify("career","career.retirement"),
                         Granularity.LIFE_TRANSITION)

    def test_achievement_not_compressed_to_other(self):
        self.assertEqual(classify("recognition","recognition.award"),
                         Granularity.ACHIEVEMENT)

    def test_unknown_kept_unclassified(self):
        self.assertEqual(classify("career","career.future_type"),
                         Granularity.UNKNOWN)
        self.assertEqual(classify(None,None),Granularity.UNKNOWN)

    def test_enrichment_keeps_original(self):
        row={"canonical_event_key":"z123", "domain":"creation",
             "event_type":"creation.release", "source":"wikidata",
             "source_original":{"citation":4}}
        out=enrich(row)
        self.assertEqual(out["model_granularity_v1"],Granularity.REPEATED_OUTPUT.value)
        for key,value in row.items():
            self.assertEqual(out[key],value)
        self.assertNotIn("model_granularity_v1",row)


if __name__ == "__main__":
    unittest.main()
