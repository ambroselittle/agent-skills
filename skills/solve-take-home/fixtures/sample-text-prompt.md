# URL Shortener — Take-Home Challenge

Build a simple URL shortener service with a web frontend and a REST API.

## Requirements

### API
1. `POST /api/shorten` — accepts a URL, returns a shortened URL
2. `GET /api/:code` — redirects to the original URL
3. `GET /api/:code/stats` — returns click count and creation date for a shortened URL
4. URLs must be validated (reject non-URL strings)
5. Short codes should be unique and URL-safe (6–8 characters)

### Frontend
1. A single-page interface where users can paste a URL and get a shortened version
2. Display the shortened URL with a copy-to-clipboard button
3. A simple analytics view showing click count for a given short URL

### Storage
- Use any data store (in-memory, SQLite, PostgreSQL, etc.)
- Track: original URL, short code, creation timestamp, click count

## Constraints

- **Time limit: 4 hours** — we value a complete, working solution over a polished partial one
- Use any language/framework you're comfortable with
- Include a README with setup instructions, design decisions, and what you'd improve with more time

## Submission

Create a GitHub repository with your solution. Send us the link when you're done.

## Evaluation Criteria

We'll be looking at:
- Does it work? (Can we run it and use it?)
- Code quality and organization
- Testing (any level of testing is appreciated)
- Documentation
- Git history (we read your commits)
