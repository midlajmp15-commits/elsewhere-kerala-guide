# Elsewhere — Kerala destination guide

elsewhere-kerala-guide showcases God's Own Country: lush tea hills, tranquil backwaters, sunlit beaches, rich spice-scented culture and vibrant heritage. Experience houseboat cruises, wildlife safaris, traditional arts, Ayurvedic wellness and warm local hospitality—sustainable travel that connects you to nature and community.

This project has a small Python backend and a browser frontend. The server serves the site, reads the destination catalog, and provides a JSON API for searching/filtering places and loading their details.

## Run locally

1. Install Python 3.9 or newer if it is not already installed.
2. Open PowerShell in this folder.
3. Run `py -3 server.py`.
4. Open <http://127.0.0.1:8000>.
5. Press Ctrl+C in PowerShell to stop the server.

Do not open `index.html` directly as a file: the frontend needs the API server.

## Deploy to Render

The included `render.yaml` configures a Render web service that installs Waitress, runs the Python WSGI application, and checks `/api/health`. To publish, put this project in a GitHub repository, create a Render Blueprint connected to that repository, review the detected service settings, and confirm deployment. The site is not public until you complete those account and deployment steps. The free web service may sleep when idle; itinerary and saved-place data remain in each visitor's browser.

## API

- `GET /api/health` — local server status.
- `GET /api/destinations` — destination summaries.
- `GET /api/destinations?q=tea` — search names, descriptions and interests.
- `GET /api/destinations?category=coast` — filter by category.
- `GET /api/destinations/munnar` — one destination's details.

Edit `data/destinations.json` to update place descriptions and image paths. All six destinations include detailed place and food guides, local tips and official reference links; `guideSections`, `localTip` and `sources` are optional fields when adding detail to another place. Search also covers guide content. The supplied photos are connected as follows:

- `images/kochin.jpg` — Fort Kochi
- `images/munnar.jpg` — Munnar
- `images/alappey.jpg` — Alappuzha
- `images/wayanad.jpg` — Wayanad
- `images/thekkady.jpg` — Thekkady

`images/kozhikode.jpeg` — Kozhikode. Both `.jpg` and `.jpeg` extensions are supported.

Saved places, trip length, optional start date, personal stop notes and the day-by-day itinerary are stored in this browser on this device. Choose a duration from 1 to 14 days; shortening the trip moves later stops onto the final day rather than deleting them. An optional start date adds calendar dates to each day and print/PDF. Use “Add saved places” or “Add to trip” to start an itinerary, choose a day for each stop, add a reminder of up to 500 characters, and use the up/down controls to reorder stops within a day. Stop notes are included in print/PDF, but not in shared links or calendar exports. “Add to calendar (.ics)” downloads all-day calendar events for each planned stop and requires a start date; import the `.ics` file into your calendar app. “Share itinerary” uses your browser's share sheet or copies a link; the link contains the itinerary's destination IDs, day assignments, trip length and (if set) start date. Opening a shared link asks before replacing the local itinerary, and does not change saved places. Use “Print / Save as PDF” to print the itinerary or save it to PDF from your browser's print dialog. The site supports keyboard-visible focus, a skip-to-content link, and Escape to close the mobile menu. Accounts, cloud-synced saved trips, bookings and newsletter delivery are not implemented yet. Destination descriptions and visitor suggestions are a first draft; review them against current official local guidance before publishing. Official pages can contain older seasonal or operational notices, so the guide avoids relying on fixed schedules and directs visitors to verify current access, bookings and conditions with the relevant authority.

## Run the tests

```powershell
py -3 -m unittest discover -s tests -v
```
