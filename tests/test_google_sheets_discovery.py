"""Test tap discovery mode and metadata."""
import re

from tap_tester import menagerie, connections
from base import GoogleSheetsBaseTest

class DiscoveryTest(GoogleSheetsBaseTest):
    """Test tap discovery mode and metadata conforms to standards."""

    @staticmethod
    def name():
        return "tap_tester_google_sheets_discovery_test"

    def test_run(self):
        """
        Testing that discovery creates the appropriate catalog with valid metadata.

        • Verify number of actual streams discovered match expected
            -verify that sheets with empty header row in the first row are skipped
        • Verify the stream names discovered were what we expect
        • Verify stream names follow naming convention
          streams should only have lowercase alphas and underscores
        • verify there is only 1 top level breadcrumb
        • verify replication key(s)
        • verify primary key(s)
        • verify that if there is a replication key we are doing INCREMENTAL otherwise FULL
        • verify the actual replication matches our expected replication method
        • verify that primary, replication keys are given the inclusion of automatic.
        • verify that all other fields have inclusion of available metadata.
       
        """
        streams_to_test = self.expected_streams()

        conn_id = connections.ensure_connection(self)

        found_catalogs = self.run_and_verify_check_mode(conn_id)
        self.assertEqual(len(streams_to_test), len(found_catalogs))

        # Verify stream names follow naming convention
        # streams should only have lowercase alphas and underscores
        found_catalog_names = {c['tap_stream_id'] for c in found_catalogs}
       

        # NB | The original product requirements specify that sheet names (streams) should NOT BE CHANGED.
        #      This is at odds with the general expectations for a stream name, and makes the following
         #      assertion not applicable to this tap.

        # self.assertTrue(all([re.fullmatch(r"[a-z_]+",  name) for name in found_catalog_names]),
        #               msg="One or more streams don't follow standard naming")

        
        for stream in streams_to_test:
            with self.subTest(stream=stream):

                # Verify ensure the caatalog is found for a given stream
                catalog = next(iter([catalog for catalog in found_catalogs
                                     if catalog["stream_name"] == stream]))
                self.assertIsNotNone(catalog)

                # collecting expected values
                expected_primary_keys = self.expected_primary_keys()[stream]
                expected_replication_keys = self.expected_replication_keys()[stream]
                expected_automatic_fields = self.expected_automatic_fields()[stream]
                expected_unsupported_fields = self.expected_unsupported_fields()[stream]
                expected_replication_method = self.expected_replication_method()[stream]

                # collecting actual values...
                schema_and_metadata = menagerie.get_annotated_schema(conn_id, catalog['stream_id'])
                metadata = schema_and_metadata["metadata"]
                stream_properties = [item for item in metadata if item.get("breadcrumb") == []]
                actual_primary_keys = set(
                    stream_properties[0].get(
                        "metadata", {self.PRIMARY_KEYS: []}).get(self.PRIMARY_KEYS, [])
                )
                actual_replication_keys = set(
                    stream_properties[0].get(
                        "metadata", {self.REPLICATION_KEYS: []}).get(self.REPLICATION_KEYS, [])
                )
                actual_replication_method = stream_properties[0].get(
                    "metadata", {self.REPLICATION_METHOD: None}).get(self.REPLICATION_METHOD)
                actual_automatic_fields = set(
                    item.get("breadcrumb", ["properties", None])[1] for item in metadata
                    if item.get("metadata").get("inclusion") == "automatic"
                )
                actual_unsupported_fields = set(
                    item.get("breadcrumb", ["properties", None])[1] for item in metadata
                    if item.get("metadata").get("inclusion") == "unsupported"
                )

                ##########################################################################
                ### metadata assertions
                ##########################################################################

                # verify there is only 1 top level breadcrumb in metadata
                self.assertTrue(len(stream_properties) == 1,
                                msg="There is NOT only one top level breadcrumb for {}".format(stream) + \
                                "\nstream_properties | {}".format(stream_properties))

                # verify replication key(s) match expectations
                self.assertSetEqual(expected_replication_keys, actual_replication_keys)

                # verify primary key(s) match expectations
                self.assertSetEqual(expected_primary_keys, actual_primary_keys)

                # verify the replication method matches our expectations
                self.assertEqual(expected_replication_method, actual_replication_method)

                # verify that if there is a replication key we are doing INCREMENTAL otherwise FULL
                if expected_replication_keys:
                    self.assertEqual(self.INCREMENTAL, actual_replication_method)
                else:
                    self.assertEqual(self.FULL_TABLE, actual_replication_method)

                # verify that primary keys and replication keys
                # are given the inclusion of automatic in metadata.
                # BUG TDL-14241 | Replication keys are not automatic
                if stream  == 'file_metadata':
                    expected_automatic_fields.remove('modifiedTime')
                self.assertSetEqual(expected_automatic_fields, actual_automatic_fields)

                # verify missing values where __sdc_row = 2
                # are marked with inclusion of unsupported
                # The card TDL-14475 was only about adding unsupported 
                # inclusion property for empty header values. The sheet 
                # `Item Master` has columns with empty row values
                failing_streams = {'Item Master'}
                if stream not in failing_streams:
                    self.assertSetEqual(expected_unsupported_fields, actual_unsupported_fields)

                # verify that all other fields have inclusion of available
                field_metadata = [item for item in metadata if item["breadcrumb"] != []]
                expected_available_field_metadata = [fmd for fmd in field_metadata
                                                     if fmd["breadcrumb"][1] not in expected_automatic_fields
                                                     and fmd["breadcrumb"][1] not in expected_unsupported_fields]
                for item in expected_available_field_metadata:
                    with self.subTest(field=item["breadcrumb"][1]):
                        self.assertEqual("available", item["metadata"]["inclusion"])

                
