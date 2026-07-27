"""CNS dialog option ordering checks."""

import unittest

from dialog.cns_table import CNS_FACILITY_TYPES


class CnsTableOrderTests(unittest.TestCase):
    def test_facility_types_follow_dialog_order(self):
        self.assertEqual(
            CNS_FACILITY_TYPES,
            [
                "High Frequency (HF)",
                "Very High Frequency (VHF)",
                "Satellite Ground Station (SGS)",
                "Non-Directional Beacon (NDB)",
                "Distance Measuring Equipment (DME)",
                "VHF Omni-Directional Range (VOR)",
                "Conventional VHF Omni-Directional Range (CVOR)",
                "Doppler VHF Omni-Directional Range (DVOR) - Elevated",
                "Doppler VHF Omni-Directional Range (DVOR) - Ground Mounted",
                "Middle and Outer Marker",
                "Automatic Dependent Surveillance Broadcast (ADS-B)",
                "Wide Area Multilateration (WAM)",
                "Primary Surveillance Radar (PSR)",
                "Secondary Surveillance Radar (SSR)",
                "Ground Based Augmentation System (GBAS) - RSMU",
                "GBAS - VDB",
                "Link Dishes",
                "Radar Site Monitor - Type A",
                "Radar Site Monitor - Type B",
            ],
        )


if __name__ == "__main__":
    unittest.main()
