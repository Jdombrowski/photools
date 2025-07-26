import Foundation

// MARK: - API Configuration
struct APIConfig {
    static let baseURL = "http://localhost:8090"
    static let apiVersion = "/api/v1"
    
    static var photosEndpoint: String { "\(baseURL)\(apiVersion)/photos" }
    static var collectionsEndpoint: String { "\(baseURL)\(apiVersion)/collections" }
}

// MARK: - API Models (matching your backend)
struct APIPhoto: Codable, Identifiable {
    let id: String
    let filename: String
    let mimeType: String
    let fileSize: Int
    let width: Int?
    let height: Int?
    let processingStatus: String
    let processingStage: String?
    let priorityLevel: Int?
    let needsAttention: Bool?
    // Note: user_rating is not returned by backend API currently
    // let userRating: Int? 
    // let ratingUpdatedAt: String?
    let createdAt: String
    let updatedAt: String
    let metadata: APIPhotoMetadata?
    
    // Convert to our local Photo model
    func toPhoto() -> Photo {
        let dateFormatter = ISO8601DateFormatter()
        
        return Photo(
            id: id,
            filename: filename,
            fileSize: fileSize,
            mimeType: mimeType,
            width: width,
            height: height,
            processingStatus: processingStatus,
            userRating: nil, // Backend doesn't return this field currently
            createdAt: dateFormatter.date(from: createdAt) ?? Date(),
            updatedAt: dateFormatter.date(from: updatedAt) ?? Date(),
            metadata: metadata?.toPhotoMetadata()
        )
    }
}

struct APIPhotoMetadata: Codable {
    let cameraMake: String?
    let cameraModel: String?
    let lensModel: String?
    let focalLength: Double?
    let aperture: Double?
    let shutterSpeed: String?
    let iso: Int?
    let dateTaken: String?
    let gpsLatitude: Double?
    let gpsLongitude: Double?
    
    func toPhotoMetadata() -> PhotoMetadata {
        let dateFormatter = ISO8601DateFormatter()
        
        return PhotoMetadata(
            cameraMake: cameraMake,
            cameraModel: cameraModel,
            lensModel: lensModel,
            dateTaken: dateTaken != nil ? dateFormatter.date(from: dateTaken!) : nil,
            gpsLatitude: gpsLatitude,
            gpsLongitude: gpsLongitude,
            focalLength: focalLength,
            aperture: aperture,
            iso: iso
        )
    }
}

// MARK: - API Request/Response Models
struct PhotosResponse: Codable {
    let photos: [APIPhoto]
    let total: Int
    let limit: Int
    let offset: Int
    let search: String?
    let processingStage: String?
    let cameraMake: String?
    let hasMore: Bool
}

struct UpdateRatingRequest: Codable {
    let rating: Int
}

struct APIError: Codable {
    let detail: String
}

// MARK: - API Service
@MainActor
class APIService: ObservableObject {
    private let session = URLSession.shared
    private let decoder = JSONDecoder()
    private let encoder = JSONEncoder()
    
    init() {
        // Configure JSON decoder for snake_case conversion
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        encoder.keyEncodingStrategy = .convertToSnakeCase
    }
    
    // MARK: - Photos API
    
    /// Fetch photos with optional filtering
    func fetchPhotos(
        limit: Int = 50,
        offset: Int = 0,
        search: String? = nil,
        rating: Int? = nil,
        processingStage: String? = nil,
        cameraMake: String? = nil,
    ) async throws -> PhotosResponse {
        
        var components = URLComponents(string: APIConfig.photosEndpoint)!
        var queryItems: [URLQueryItem] = [
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "offset", value: String(offset))
        ]
        
        if let search = search, !search.isEmpty {
            queryItems.append(URLQueryItem(name: "search", value: search))
        }
        
        if let rating = rating {
            queryItems.append(URLQueryItem(name: "rating", value: String(rating)))
        }
        
        if let processingStage = processingStage {
            queryItems.append(URLQueryItem(name: "processing_stage", value: processingStage))
        }
        
        if let cameraMake = cameraMake {
            queryItems.append(URLQueryItem(name: "camera_make", value: cameraMake))
        }
        
        components.queryItems = queryItems
        
        let request = URLRequest(url: components.url!)
        
        do {
            let (data, response) = try await session.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIServiceError.invalidResponse
            }
            
            if httpResponse.statusCode == 200 {
                return try decoder.decode(PhotosResponse.self, from: data)
            } else {
                let apiError = try? decoder.decode(APIError.self, from: data)
                throw APIServiceError.serverError(apiError?.detail ?? "Unknown error")
            }
            
        } catch is DecodingError {
            throw APIServiceError.decodingError
        } catch {
            throw APIServiceError.networkError(error.localizedDescription)
        }
    }
    
    /// Update photo rating
    func updatePhotoRating(photoId: String, rating: Int) async throws {
        let url = URL(string: "\(APIConfig.photosEndpoint)/\(photoId)/rating")!
        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let requestBody = UpdateRatingRequest(rating: rating)
        request.httpBody = try encoder.encode(requestBody)
        
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIServiceError.invalidResponse
        }
        
        if httpResponse.statusCode != 200 {
            let apiError = try? decoder.decode(APIError.self, from: data)
            throw APIServiceError.serverError(apiError?.detail ?? "Failed to update rating")
        }
    }
    
    /// Get photo thumbnail URL
    func thumbnailURL(for photoId: String, size: Int = 200) -> URL? {
        URL(string: "\(APIConfig.baseURL)/api/v1/photos/\(photoId)/thumbnail?size=\(size)")
    }
    
    /// Get full-size photo URL
    func photoURL(for photoId: String) -> URL? {
        URL(string: "\(APIConfig.baseURL)/api/v1/photos/\(photoId)/image")
    }
    
    // MARK: - Health Check
    
    /// Check if backend is available
    func healthCheck() async -> Bool {
        guard let url = URL(string: "\(APIConfig.baseURL)/health") else {
            return false
        }
        
        do {
            let (_, response) = try await session.data(from: url)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }
}

// MARK: - Error Handling
enum APIServiceError: LocalizedError {
    case networkError(String)
    case invalidResponse
    case decodingError
    case serverError(String)
    
    var errorDescription: String? {
        switch self {
        case .networkError(let message):
            return "Network error: \(message)"
        case .invalidResponse:
            return "Invalid response from server"
        case .decodingError:
            return "Failed to decode server response"
        case .serverError(let message):
            return "Server error: \(message)"
        }
    }
}
