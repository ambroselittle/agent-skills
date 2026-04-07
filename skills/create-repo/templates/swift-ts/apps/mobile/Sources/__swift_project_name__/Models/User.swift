import Foundation

struct User: Codable, Identifiable {
    let id: Int
    let email: String
    let name: String?
    let createdAt: Date
}
