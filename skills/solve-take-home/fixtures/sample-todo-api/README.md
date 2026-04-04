# Todo API Challenge

Build a RESTful API for managing todo items. This is a take-home coding challenge — spend no more than 3 hours.

## Requirements

1. **CRUD operations** for todo items:
   - `POST /todos` — create a new todo
   - `GET /todos` — list all todos (support filtering by `completed` status)
   - `GET /todos/:id` — get a single todo
   - `PUT /todos/:id` — update a todo
   - `DELETE /todos/:id` — delete a todo

2. **Todo item fields:**
   - `id` — unique identifier
   - `title` — string, required, max 200 characters
   - `description` — string, optional
   - `completed` — boolean, defaults to false
   - `createdAt` — timestamp
   - `updatedAt` — timestamp

3. **Validation:**
   - Title is required and must be ≤ 200 characters
   - Return appropriate error responses (400 for validation, 404 for not found)

4. **Persistence:**
   - Use any data store you prefer (in-memory is acceptable, but a real database is a plus)

## Bonus (if time allows)

- User authentication (JWT)
- Pagination on the list endpoint
- Search/filter by title
- Rate limiting

## What We're Looking For

- Clean, well-structured code
- Proper error handling
- Tests (unit and/or integration)
- Clear documentation
- Good git commit history showing your process

## Getting Started

The project is set up with TypeScript and Node.js. Install dependencies and start building:

```bash
npm install
npm run dev
```

## Submission

Push your solution to this repo and open a pull request against `main`.
