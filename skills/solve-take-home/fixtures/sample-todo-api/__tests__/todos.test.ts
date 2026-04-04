// These test stubs define the expected behavior of the Todo API.
// Implement the API to make these tests pass.

describe("POST /todos", () => {
  test.todo("creates a new todo with valid data");
  test.todo("returns 400 when title is missing");
  test.todo("returns 400 when title exceeds 200 characters");
  test.todo("sets completed to false by default");
  test.todo("sets createdAt and updatedAt timestamps");
});

describe("GET /todos", () => {
  test.todo("returns all todos");
  test.todo("filters by completed status when query param is provided");
  test.todo("returns empty array when no todos exist");
});

describe("GET /todos/:id", () => {
  test.todo("returns a single todo by id");
  test.todo("returns 404 for non-existent id");
});

describe("PUT /todos/:id", () => {
  test.todo("updates an existing todo");
  test.todo("returns 404 for non-existent id");
  test.todo("updates the updatedAt timestamp");
  test.todo("returns 400 when title exceeds 200 characters");
});

describe("DELETE /todos/:id", () => {
  test.todo("deletes an existing todo");
  test.todo("returns 404 for non-existent id");
});
