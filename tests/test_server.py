import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from server import application, filter_destinations, load_destinations


class DestinationCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.destinations = load_destinations()

    def test_catalog_contains_six_kerala_destinations(self):
        self.assertEqual(
            {place["slug"] for place in self.destinations},
            {"fort-kochi", "munnar", "alappuzha", "wayanad", "thekkady", "kozhikode"},
        )

    def test_search_matches_destination_names_without_case_sensitivity(self):
        results = filter_destinations(self.destinations, "MUNNAR")
        self.assertEqual([place["slug"] for place in results], ["munnar"])

    def test_search_matches_experiences(self):
        results = filter_destinations(self.destinations, "tea gardens")
        self.assertIn("munnar", [place["slug"] for place in results])

    def test_categories_can_match_more_than_one_destination_type(self):
        results = filter_destinations(self.destinations, category="coast")
        self.assertEqual(
            {place["slug"] for place in results},
            {"fort-kochi", "alappuzha", "kozhikode"},
        )

    def test_unknown_search_returns_no_results(self):
        self.assertEqual(filter_destinations(self.destinations, "not-a-place"), [])

    def request(self, path, query="", method="GET"):
        response = {}

        def start_response(status, headers):
            response["status"] = int(status.split(" ", 1)[0])
            response["headers"] = dict(headers)

        body = b"".join(
            application(
                {
                    "REQUEST_METHOD": method,
                    "PATH_INFO": path,
                    "QUERY_STRING": query,
                },
                start_response,
            )
        )
        return response["status"], response["headers"], body

    def test_wsgi_health_endpoint(self):
        status, headers, body = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"status": "ok"})
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_wsgi_destination_search_returns_summaries(self):
        status, _, body = self.request("/api/destinations", "q=tea")
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertIn("munnar", [place["slug"] for place in payload["results"]])
        self.assertNotIn("guideSections", payload["results"][0])

    def test_wsgi_destination_detail_and_not_found(self):
        status, _, body = self.request("/api/destinations/munnar")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["slug"], "munnar")
        self.assertEqual(self.request("/api/destinations/not-a-place")[0], 404)

    def test_wsgi_static_file_allowlist_and_path_traversal(self):
        status, headers, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b"Discover Kerala", body)
        self.assertEqual(self.request("/README.md")[0], 404)
        self.assertEqual(self.request("/%2e%2e/README.md")[0], 404)

    def test_wsgi_rejects_non_get_requests(self):
        status, headers, body = self.request("/api/health", method="POST")
        self.assertEqual(status, 405)
        self.assertEqual(json.loads(body), {"error": "Method not allowed."})
        self.assertIn("application/json", headers["Content-Type"])

    def test_uploaded_destination_images_exist(self):
        for place in self.destinations:
            if place["image"]:
                image_path = PROJECT_ROOT / place["image"].lstrip("/")
                self.assertTrue(image_path.is_file(), f"Missing image for {place['slug']}")

    def test_kozhikode_has_a_local_food_and_places_guide(self):
        kozhikode = next(place for place in self.destinations if place["slug"] == "kozhikode")
        guide_text = " ".join(
            item
            for section in kozhikode["guideSections"]
            for item in section["items"]
        ).casefold()
        self.assertIn("biryani", guide_text)
        self.assertIn("halwa", guide_text)
        self.assertIn("beypore", guide_text)
        self.assertIn("mishkal mosque", guide_text)
        self.assertIn("kozhikode beach", guide_text)
        self.assertIn("pathiri", guide_text)
        self.assertTrue(kozhikode["sources"])
        self.assertTrue(all(source["url"].startswith("https://") for source in kozhikode["sources"]))

    def test_fort_kochi_has_a_local_heritage_and_food_guide(self):
        fort_kochi = next(place for place in self.destinations if place["slug"] == "fort-kochi")
        guide_text = " ".join(
            item
            for section in fort_kochi["guideSections"]
            for item in section["items"]
        ).casefold()
        self.assertIn("chinese fishing nets", guide_text)
        self.assertIn("st. francis church", guide_text)
        self.assertIn("santa cruz basilica", guide_text)
        self.assertIn("mattancherry palace", guide_text)
        self.assertIn("appam", guide_text)
        self.assertTrue(fort_kochi["sources"])
        self.assertTrue(all(source["url"].startswith("https://") for source in fort_kochi["sources"]))

    def test_search_matches_detail_guide_content(self):
        results = filter_destinations(self.destinations, "santa cruz basilica")
        self.assertEqual([place["slug"] for place in results], ["fort-kochi"])

    def test_munnar_has_a_local_highlands_and_food_guide(self):
        munnar = next(place for place in self.destinations if place["slug"] == "munnar")
        guide_text = " ".join(
            item
            for section in munnar["guideSections"]
            for item in section["items"]
        ).casefold()
        self.assertIn("eravikulam national park", guide_text)
        self.assertIn("nilgiri tahr", guide_text)
        self.assertIn("tea", guide_text)
        self.assertIn("appam", guide_text)
        self.assertTrue(munnar["localTip"])
        self.assertTrue(munnar["sources"])
        self.assertTrue(all(source["url"].startswith("https://") for source in munnar["sources"]))
        self.assertTrue(
            any("eravikulamnationalpark.in" in source["url"] for source in munnar["sources"])
        )

    def test_search_matches_munnar_guide_content(self):
        results = filter_destinations(self.destinations, "nilgiri tahr")
        self.assertEqual([place["slug"] for place in results], ["munnar"])

    def test_alappuzha_has_a_local_backwaters_and_food_guide(self):
        alappuzha = next(place for place in self.destinations if place["slug"] == "alappuzha")
        guide_text = " ".join(
            item
            for section in alappuzha["guideSections"]
            for item in section["items"]
        ).casefold()
        self.assertIn("public ferry", guide_text)
        self.assertIn("life jackets", guide_text)
        self.assertIn("alappuzha beach", guide_text)
        self.assertIn("appam", guide_text)
        self.assertTrue(alappuzha["localTip"])
        self.assertTrue(alappuzha["sources"])
        self.assertTrue(all(source["url"].startswith("https://") for source in alappuzha["sources"]))

    def test_search_matches_alappuzha_guide_content(self):
        results = filter_destinations(self.destinations, "life jackets")
        self.assertEqual([place["slug"] for place in results], ["alappuzha"])

    def test_wayanad_has_a_local_outdoors_and_food_guide(self):
        wayanad = next(place for place in self.destinations if place["slug"] == "wayanad")
        guide_text = " ".join(
            item
            for section in wayanad["guideSections"]
            for item in section["items"]
        ).casefold()
        self.assertIn("edakkal caves", guide_text)
        self.assertIn("authorised guides", guide_text)
        self.assertIn("coffee", guide_text)
        self.assertIn("puttu", guide_text)
        self.assertTrue(wayanad["localTip"])
        self.assertTrue(wayanad["sources"])
        self.assertTrue(all(source["url"].startswith("https://") for source in wayanad["sources"]))
        self.assertTrue(
            any("wayanad.gov.in/en/tourist-place/edakkal-caves/" in source["url"] for source in wayanad["sources"])
        )

    def test_search_matches_wayanad_guide_content(self):
        results = filter_destinations(self.destinations, "edakkal caves")
        self.assertEqual([place["slug"] for place in results], ["wayanad"])

    def test_thekkady_has_a_local_wildlife_and_spice_guide(self):
        thekkady = next(place for place in self.destinations if place["slug"] == "thekkady")
        guide_text = " ".join(
            item
            for section in thekkady["guideSections"]
            for item in section["items"]
        ).casefold()
        self.assertIn("periyar tiger reserve", guide_text)
        self.assertIn("wildlife sightings are never guaranteed", guide_text)
        self.assertIn("spice garden", guide_text)
        self.assertIn("cardamom", guide_text)
        self.assertTrue(thekkady["localTip"])
        self.assertTrue(thekkady["sources"])
        self.assertTrue(all(source["url"].startswith("https://") for source in thekkady["sources"]))

    def test_search_matches_thekkady_guide_content(self):
        results = filter_destinations(self.destinations, "cardamom")
        self.assertEqual([place["slug"] for place in results], ["thekkady"])


if __name__ == "__main__":
    unittest.main()
