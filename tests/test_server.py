import base64
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from server import application, filter_destinations, load_destinations


class DestinationCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.destinations = load_destinations()

    def test_catalog_contains_nine_kerala_destinations(self):
        self.assertEqual(
            {place["slug"] for place in self.destinations},
            {
                "fort-kochi", "munnar", "alappuzha", "wayanad", "thekkady",
                "kozhikode", "varkala", "kovalam", "athirappilly",
            },
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
            {"fort-kochi", "alappuzha", "kozhikode", "varkala", "kovalam"},
        )

    def test_unknown_search_returns_no_results(self):
        self.assertEqual(filter_destinations(self.destinations, "not-a-place"), [])

    def request(self, path, query="", method="GET", headers=None):
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
                    **(headers or {}),
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
        culture_status, culture_headers, culture_body = self.request("/culture.html")
        self.assertEqual(culture_status, 200)
        self.assertIn("text/html", culture_headers["Content-Type"])
        self.assertIn(b"Kerala's culture is lived", culture_body)
        self.assertIn(b'href="/navigation.css"', culture_body)
        self.assertIn(b'href="/#trip-planner"', culture_body)
        for path in ("/unknown-page", "/images/missing.jpg", "/404.html", "/%2e%2e/server.py"):
            with self.subTest(path=path):
                not_found_status, not_found_headers, not_found_body = self.request(path)
                self.assertEqual(not_found_status, 404)
                self.assertIn("text/html", not_found_headers["Content-Type"])
                self.assertIn(b"Page not found", not_found_body)
                self.assertIn(b'href="/#destinations"', not_found_body)
        about_status, about_headers, about_body = self.request("/about.html")
        self.assertEqual(about_status, 200)
        self.assertIn("text/html", about_headers["Content-Type"])
        self.assertIn(b"Built as a BCA learning project", about_body)
        contact_status, contact_headers, contact_body = self.request("/contact.html")
        self.assertEqual(contact_status, 200)
        self.assertIn("text/html", contact_headers["Content-Type"])
        self.assertIn(b"mailto:miduxx18@gmail.com", contact_body)
        self.assertIn(b"miduxx18@gmail.com", contact_body)
        self.assertEqual(self.request("/server.py")[0], 404)
        self.assertEqual(self.request("/README.md")[0], 404)
        api_status, api_headers, api_body = self.request("/api/destinations/not-a-place")
        self.assertEqual(api_status, 404)
        self.assertIn("application/json", api_headers["Content-Type"])
        self.assertEqual(json.loads(api_body), {"error": "Destination not found."})

    def test_shared_navigation_assets_are_served(self):
        css_status, css_headers, css_body = self.request("/navigation.css")
        js_status, js_headers, js_body = self.request("/navigation.js")
        self.assertEqual(css_status, 200)
        self.assertIn("text/css", css_headers["Content-Type"])
        self.assertIn(b".nav-links", css_body)
        self.assertEqual(js_status, 200)
        self.assertIn("javascript", js_headers["Content-Type"])
        self.assertIn(b"aria-expanded", js_body)

    def test_culture_images_are_served_and_described(self):
        status, _, body = self.request("/culture.html")
        self.assertEqual(status, 200)
        for filename, alt_text in (
            ("kathakali.jpg", "Kathakali dancer"),
            ("theyyam.jpg", "Theyyam performer"),
            ("onam.jpg", "associated with Onam"),
            ("thrissurpooram.jpg", "Thrissur Pooram procession"),
        ):
            with self.subTest(image=filename):
                image_status, image_headers, image_body = self.request(f"/images/{filename}")
                self.assertEqual(image_status, 200)
                self.assertTrue(image_headers["Content-Type"].startswith("image/jpeg"))
                self.assertGreater(len(image_body), 0)
                self.assertIn(f'src="/images/{filename}"'.encode(), body)
                self.assertIn(alt_text.encode(), body)

    def test_wsgi_rejects_non_get_requests(self):
        status, headers, body = self.request("/api/health", method="POST")
        self.assertEqual(status, 405)
        self.assertEqual(json.loads(body), {"error": "Method not allowed."})
        self.assertIn("application/json", headers["Content-Type"])

    def test_private_preview_fails_closed_without_credentials(self):
        with patch.dict(os.environ, {"PREVIEW_AUTH_REQUIRED": "true"}, clear=False):
            os.environ.pop("PREVIEW_USERNAME", None)
            os.environ.pop("PREVIEW_PASSWORD", None)
            status, _, body = self.request("/")
            culture_status, _, culture_body = self.request("/culture.html")
            about_status, _, about_body = self.request("/about.html")
            contact_status, _, contact_body = self.request("/contact.html")
            health_status, _, health_body = self.request("/api/health")
        self.assertEqual(status, 503)
        self.assertEqual(
            json.loads(body),
            {"error": "Private preview authentication is not configured."},
        )
        self.assertEqual(culture_status, 503)
        self.assertEqual(
            json.loads(culture_body),
            {"error": "Private preview authentication is not configured."},
        )
        self.assertEqual(about_status, 503)
        self.assertEqual(
            json.loads(about_body),
            {"error": "Private preview authentication is not configured."},
        )
        self.assertEqual(contact_status, 503)
        self.assertEqual(
            json.loads(contact_body),
            {"error": "Private preview authentication is not configured."},
        )
        self.assertEqual(health_status, 200)
        self.assertEqual(json.loads(health_body), {"status": "ok"})

    def test_private_preview_rejects_invalid_basic_credentials(self):
        credential = base64.b64encode(b"preview:wrong").decode("ascii")
        with patch.dict(
            os.environ,
            {
                "PREVIEW_AUTH_REQUIRED": "true",
                "PREVIEW_USERNAME": "preview",
                "PREVIEW_PASSWORD": "a long test password",
            },
            clear=False,
        ):
            status, headers, body = self.request(
                "/api/destinations",
                headers={"HTTP_AUTHORIZATION": f"Basic {credential}"},
            )
        self.assertEqual(status, 401)
        self.assertIn("Basic realm=", headers["WWW-Authenticate"])
        self.assertEqual(json.loads(body), {"error": "Authentication required."})

    def test_private_preview_allows_correct_basic_credentials(self):
        credential = base64.b64encode(b"preview:a long test password").decode("ascii")
        with patch.dict(
            os.environ,
            {
                "PREVIEW_AUTH_REQUIRED": "true",
                "PREVIEW_USERNAME": "preview",
                "PREVIEW_PASSWORD": "a long test password",
            },
            clear=False,
        ):
            status, headers, body = self.request(
                "/api/health",
                headers={"HTTP_AUTHORIZATION": f"Basic {credential}"},
            )
            homepage_status, homepage_headers, homepage_body = self.request(
                "/",
                headers={"HTTP_AUTHORIZATION": f"Basic {credential}"},
            )
            culture_status, culture_headers, culture_body = self.request(
                "/culture.html",
                headers={"HTTP_AUTHORIZATION": f"Basic {credential}"},
            )
            about_status, about_headers, about_body = self.request(
                "/about.html",
                headers={"HTTP_AUTHORIZATION": f"Basic {credential}"},
            )
            contact_status, contact_headers, contact_body = self.request(
                "/contact.html",
                headers={"HTTP_AUTHORIZATION": f"Basic {credential}"},
            )
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(homepage_status, 200)
        self.assertIn("text/html", homepage_headers["Content-Type"])
        self.assertIn(b"Discover Kerala", homepage_body)
        self.assertEqual(culture_status, 200)
        self.assertIn("text/html", culture_headers["Content-Type"])
        self.assertIn(b"Kerala's culture is lived", culture_body)
        self.assertEqual(about_status, 200)
        self.assertIn("text/html", about_headers["Content-Type"])
        self.assertIn(b"Built as a BCA learning project", about_body)
        self.assertEqual(contact_status, 200)
        self.assertIn("text/html", contact_headers["Content-Type"])
        self.assertIn(b"mailto:miduxx18@gmail.com", contact_body)

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

    def test_varkala_has_a_clifftop_and_coastal_safety_guide(self):
        varkala = next(place for place in self.destinations if place["slug"] == "varkala")
        guide_text = " ".join(
            item
            for section in varkala["guideSections"]
            for item in section["items"]
        ).casefold()
        self.assertIn("cliff path", guide_text)
        self.assertIn("lifeguard", guide_text)
        self.assertIn("appam", guide_text)
        self.assertTrue(varkala["sources"])
        self.assertTrue(all(source["url"].startswith("https://") for source in varkala["sources"]))
        self.assertEqual(varkala["image"], "/images/varkala.jpg")
        self.assertEqual(varkala["imageAlt"], "Waves break along the beach below Varkala's green cliffside")

    def test_search_matches_varkala_destination(self):
        results = filter_destinations(self.destinations, "varkala cliff")
        self.assertEqual([place["slug"] for place in results], ["varkala"])

    def test_kovalam_has_a_beach_and_lighthouse_guide(self):
        kovalam = next(place for place in self.destinations if place["slug"] == "kovalam")
        guide_text = " ".join(
            item
            for section in kovalam["guideSections"]
            for item in section["items"]
        ).casefold()
        self.assertIn("lighthouse", guide_text)
        self.assertIn("lifeguard", guide_text)
        self.assertIn("appam", guide_text)
        self.assertTrue(kovalam["sources"])
        self.assertTrue(all(source["url"].startswith("https://") for source in kovalam["sources"]))
        self.assertEqual(kovalam["image"], "/images/kovalam.jpg")
        self.assertEqual(kovalam["imageAlt"], "Kovalam's red-and-white lighthouse above a palm-lined rocky shore")

    def test_search_matches_kovalam_destination(self):
        results = filter_destinations(self.destinations, "kovalam lighthouse")
        self.assertEqual([place["slug"] for place in results], ["kovalam"])

    def test_athirappilly_has_a_waterfall_and_river_safety_guide(self):
        athirappilly = next(place for place in self.destinations if place["slug"] == "athirappilly")
        guide_text = " ".join(
            item
            for section in athirappilly["guideSections"]
            for item in section["items"]
        ).casefold()
        self.assertIn("approved viewpoints", guide_text)
        self.assertIn("avoid entering the river", guide_text)
        self.assertIn("thrissur district", athirappilly["description"].casefold())
        self.assertTrue(athirappilly["sources"])
        self.assertTrue(all(source["url"].startswith("https://") for source in athirappilly["sources"]))
        self.assertEqual(athirappilly["image"], "/images/athirappilly.jpeg")
        self.assertEqual(athirappilly["imageAlt"], "Athirappilly Falls cascade over a rocky ledge through forest")

    def test_search_matches_athirappilly_destination(self):
        results = filter_destinations(self.destinations, "athirappilly waterfalls")
        self.assertEqual([place["slug"] for place in results], ["athirappilly"])


if __name__ == "__main__":
    unittest.main()
