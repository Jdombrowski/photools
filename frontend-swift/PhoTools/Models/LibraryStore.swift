import Foundation
import SwiftUI

// Main data store - like Redux store but with SwiftUI integration
@MainActor
class LibraryStore: ObservableObject {
    // @Published makes SwiftUI automatically update views when these change
    @Published var photos: [Photo] = []
    @Published var selectedPhotos: Set<String> = []
    @Published var isLoading = false
    @Published var searchQuery = ""
    @Published var selectedRating: Int? = nil
    @Published var errorMessage: String? = nil
    @Published var isBackendConnected = false
    
    // API service
    private let apiService: APIService
    
    // Pagination
    private var currentPage = 1
    private var hasMorePages = true
    
    init() {
        // Initialize API service - it will handle connection failures gracefully
        self.apiService = APIService()
    }
    
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
    func loadPhotos(refresh: Bool = false) {
        Task {
            if refresh {
                currentPage = 1
                hasMorePages = true
                photos = []
            }
            
            guard hasMorePages else { return }
            
            isLoading = true
            errorMessage = nil
            
            // Check backend connection
            let isConnected = await apiService.healthCheck()
            isBackendConnected = isConnected
            
            if !isConnected {
                print("Backend not connected, using mock data")
                fallbackToMockData()
                isLoading = false
                return
            }
            
            do {
                // Fetch photos from API
                let response = try await apiService.fetchPhotos(
                    limit: 50,
                    offset: (currentPage - 1) * 50, // Convert page to offset
                    search: searchQuery.isEmpty ? nil : searchQuery,
                    rating: selectedRating
                )
                
                let newPhotos = response.photos.map { $0.toPhoto() }
                
                if refresh {
                    photos = newPhotos
                } else {
                    photos.append(contentsOf: newPhotos)
                }
                
                hasMorePages = response.hasMore
                currentPage += 1
                
            } catch {
                errorMessage = error.localizedDescription
                print("API Error: \(error)")
                
                // Fallback to mock data on error
                if photos.isEmpty {
                    fallbackToMockData()
                }
            }
            
            isLoading = false
        }
    }
    
    private func fallbackToMockData() {
        print("Using mock data as fallback")
        photos = Photo.mockPhotos
        
        // Add more mock photos for testing
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
            photos.append(mockPhoto)
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
        // Optimistically update UI first
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
        
        // Then sync with backend if available
        Task {
            do {
                if isBackendConnected {
                    try await apiService.updatePhotoRating(photoId: photoId, rating: rating)
                }
            } catch {
                errorMessage = "Failed to update photo rating: \(error.localizedDescription)"
                print("Rating update error: \(error)")
            }
        }
    }
    
    // Search with debouncing
    func performSearch() {
        loadPhotos(refresh: true)
    }
    
    // Get thumbnail URL for photo (returns nil if backend not connected)
    func thumbnailURL(for photoId: String, size: Int = 200) -> URL? {
        guard isBackendConnected else {
            return nil // Will trigger fallback in UI
        }
        return apiService.thumbnailURL(for: photoId, size: size)
    }
    
    // Get full image URL for photo (returns nil if backend not connected)
    func imageURL(for photoId: String) -> URL? {
        guard isBackendConnected else {
            return nil // Will trigger fallback in UI
        }
        return apiService.photoURL(for: photoId)
    }
}