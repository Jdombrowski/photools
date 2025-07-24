import Foundation
import SwiftUI

// Main data store - like Redux store but with SwiftUI integration
class LibraryStore: ObservableObject {
    // @Published makes SwiftUI automatically update views when these change
    @Published var photos: [Photo] = []
    @Published var selectedPhotos: Set<String> = []
    @Published var isLoading = false
    @Published var searchQuery = ""
    @Published var selectedRating: Int? = nil
    
    // Computed properties - like Redux selectors
    var filteredPhotos: [Photo] {
        var filtered = photos
        
        // Filter by search query
        if !searchQuery.isEmpty {
            filtered = filtered.filter { photo in
                photo.filename.localizedCaseInsensitiveContains(searchQuery) ||
                photo.metadata?.cameraMake?.localizedCaseInsensitiveContains(searchQuery) == true ||
                photo.metadata?.cameraModel?.localizedCaseInsensitiveContains(searchQuery) == true
            }
        }
        
        // Filter by rating
        if let rating = selectedRating {
            filtered = filtered.filter { $0.userRating == rating }
        }
        
        // Sort by date taken (newest first)
        return filtered.sorted { photo1, photo2 in
            guard let date1 = photo1.metadata?.dateTaken,
                  let date2 = photo2.metadata?.dateTaken else {
                return photo1.createdAt > photo2.createdAt
            }
            return date1 > date2
        }
    }
    
    var photoCount: Int {
        photos.count
    }
    
    var selectedPhotoCount: Int {
        selectedPhotos.count
    }
    
    // Actions - like Redux actions
    func loadPhotos() {
        isLoading = true
        
        // For now, use mock data - later we'll call the API
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { // Simulate network delay
            self.photos = Photo.mockPhotos
            // Add more mock photos to test the grid
            for i in 4...20 {
                let mockPhoto = Photo(
                    id: String(i),
                    filename: "IMG_\(String(format: "%04d", i)).jpg",
                    fileSize: Int.random(in: 2_000_000...20_000_000),
                    mimeType: "image/jpeg",
                    width: 4000,
                    height: 3000,
                    processingStatus: "completed",
                    userRating: Int.random(in: 0...5),
                    createdAt: Date().addingTimeInterval(-Double(i * 3600)),
                    updatedAt: Date().addingTimeInterval(-Double(i * 1800)),
                    metadata: PhotoMetadata(
                        cameraMake: ["Canon", "Nikon", "Sony", "Apple"].randomElement(),
                        cameraModel: ["EOS R5", "D850", "α7R V", "iPhone 15 Pro"].randomElement(),
                        lensModel: nil,
                        dateTaken: Date().addingTimeInterval(-Double(i * 3600)),
                        gpsLatitude: nil,
                        gpsLongitude: nil,
                        focalLength: Double.random(in: 24...200),
                        aperture: [1.4, 2.0, 2.8, 4.0, 5.6].randomElement(),
                        iso: [100, 200, 400, 800, 1600].randomElement()
                    )
                )
                self.photos.append(mockPhoto)
            }
            self.isLoading = false
        }
    }
    
    func selectPhoto(_ photoId: String) {
        if selectedPhotos.contains(photoId) {
            selectedPhotos.remove(photoId)
        } else {
            selectedPhotos.insert(photoId)
        }
    }
    
    func selectAllPhotos() {
        selectedPhotos = Set(filteredPhotos.map { $0.id })
    }
    
    func deselectAllPhotos() {
        selectedPhotos.removeAll()
    }
    
    func deleteSelectedPhotos() {
        photos.removeAll { selectedPhotos.contains($0.id) }
        selectedPhotos.removeAll()
    }
    
    func updatePhotoRating(_ photoId: String, rating: Int) {
        if let index = photos.firstIndex(where: { $0.id == photoId }) {
            var updatedPhoto = photos[index]
            updatedPhoto = Photo(
                id: updatedPhoto.id,
                filename: updatedPhoto.filename,
                fileSize: updatedPhoto.fileSize,
                mimeType: updatedPhoto.mimeType,
                width: updatedPhoto.width,
                height: updatedPhoto.height,
                processingStatus: updatedPhoto.processingStatus,
                userRating: rating,
                createdAt: updatedPhoto.createdAt,
                updatedAt: Date(), // Update timestamp
                metadata: updatedPhoto.metadata
            )
            photos[index] = updatedPhoto
        }
    }
}