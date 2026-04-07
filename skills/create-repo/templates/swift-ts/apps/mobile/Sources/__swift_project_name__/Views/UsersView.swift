import SwiftUI

struct UsersView: View {
    @State private var users: [User] = []
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        List {
            if isLoading {
                ProgressView("Loading users...")
            } else if let error = errorMessage {
                Text(error)
                    .foregroundStyle(.red)
            } else if users.isEmpty {
                Text("No users found")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(users) { user in
                    VStack(alignment: .leading) {
                        Text(user.email)
                            .font(.headline)
                        if let name = user.name {
                            Text(name)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
        .navigationTitle("Users")
        .task {
            await loadUsers()
        }
        .refreshable {
            await loadUsers()
        }
    }

    private func loadUsers() async {
        isLoading = true
        errorMessage = nil
        do {
            users = try await APIClient.shared.listUsers()
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

#Preview {
    NavigationStack {
        UsersView()
    }
}
