import Foundation

// Photo model - matches our backend API
struct Photo: Identifiable, Codable {
    let id: String
    let filename: String
    let fileSize: Int
    let mimeType: String
    let width: Int?
    let height: Int?
    let processingStatus: String
    let userRating: Int? // 0-5 workflow rating
    let createdAt: Date
    let updatedAt: Date
    
    // Metadata - optional because not all photos have it
    let metadata: PhotoMetadata?
    
    // Computed properties for UI
    var ratingStars: String {
        guard let rating = userRating, rating > 0 else { return "No rating" }
        return String(repeating: "★", count: rating)
    }
    
    var workflowStage: String {
        guard let rating = userRating else { return "Unrated" }
        switch rating {
        case 0: return "Reject"
        case 1: return "Review"
        case 2: return "Archive"
        case 3: return "Edit Queue"
        case 4: return "Portfolio"
        case 5: return "Showcase"
        default: return "Unknown"
        }
    }
    
    var displaySize: String {
        let formatter = ByteCountFormatter()
        return formatter.string(fromByteCount: Int64(fileSize))
    }
}

struct PhotoMetadata: Codable {
    let cameraMake: String?
    let cameraModel: String?
    let lensModel: String?
    let dateTaken: Date?
    let gpsLatitude: Double?
    let gpsLongitude: Double?
    let focalLength: Double?
    let aperture: Double?
    let iso: Int?
    
    // Display formatted camera info
    var cameraInfo: String {
        if let make = cameraMake, let model = cameraModel {
            return "\(make) \(model)"
        } else if let make = cameraMake {
            return make
        } else if let model = cameraModel {
            return model
        }
        return "Unknown Camera"
    }
    
    var exposureInfo: String {
        var parts: [String] = []
        
        if let aperture = aperture {
            parts.append("f/\(String(format: "%.1f", aperture))")
        }
        
        if let iso = iso {
            parts.append("ISO \(iso)")
        }
        
        if let focalLength = focalLength {
            parts.append("\(Int(focalLength))mm")
        }
        
        return parts.joined(separator: " • ")
    }
}

// Mock data for development
extension Photo {
    static let mockPhotos: [Photo] = [
        Photo(
            id: "1",
            filename: "IMG_2847.jpg",
            fileSize: 15_200_000,
            mimeType: "image/jpeg",
            width: 6720,
            height: 4480,
            processingStatus: "completed",
            userRating: 4,
            createdAt: Date().addingTimeInterval(-86400), // 1 day ago
            updatedAt: Date().addingTimeInterval(-3600),  // 1 hour ago
            metadata: PhotoMetadata(
                cameraMake: "Canon",
                cameraModel: "EOS R5",
                lensModel: "RF 85mm f/2.8 Macro",
                dateTaken: Date().addingTimeInterval(-86400),
                gpsLatitude: 20.7984,
                gpsLongitude: -156.3319,
                focalLength: 85.0,
                aperture: 2.8,
                iso: 400
            )
        ),
        Photo(
            id: "2", 
            filename: "DSC_0123.jpg",
            fileSize: 8_400_000,
            mimeType: "image/jpeg",
            width: 4000,
            height: 6000,
            processingStatus: "completed",
            userRating: 5,
            createdAt: Date().addingTimeInterval(-172800), // 2 days ago
            updatedAt: Date().addingTimeInterval(-7200),   // 2 hours ago
            metadata: PhotoMetadata(
                cameraMake: "Nikon",
                cameraModel: "D850",
                lensModel: "70-200mm f/2.8",
                dateTaken: Date().addingTimeInterval(-172800),
                gpsLatitude: nil,
                gpsLongitude: nil,
                focalLength: 135.0,
                aperture: 4.0,
                iso: 800
            )
        ),
        Photo(
            id: "3",
            filename: "iPhone_sunset.HEIC",
            fileSize: 3_200_000,
            mimeType: "image/heic",
            width: 4032,
            height: 3024,
            processingStatus: "completed", 
            userRating: 3,
            createdAt: Date().addingTimeInterval(-259200), // 3 days ago
            updatedAt: Date().addingTimeInterval(-259200),
            metadata: PhotoMetadata(
                cameraMake: "Apple",
                cameraModel: "iPhone 15 Pro",
                lensModel: nil,
                dateTaken: Date().addingTimeInterval(-259200),
                gpsLatitude: 37.7749,
                gpsLongitude: -122.4194,
                focalLength: 77.0,
                aperture: 2.8,
                iso: 125
            )
        )
    ]
}