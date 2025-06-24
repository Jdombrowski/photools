#!/bin/bash
# Photools - System Dependency Checker (Fixed Version)
# Validates all system-level dependencies before setup
# Provides clear, actionable error messages and auto-fix suggestions

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PYTHON_MIN_VERSION="3.11"
POETRY_MIN_VERSION="1.6.0"
DOCKER_MIN_VERSION="20.10.0"
DOCKER_COMPOSE_MIN_VERSION="2.0.0"
REQUIRED_DISK_SPACE_GB=5
REQUIRED_MEMORY_GB=4

# Flags
STRICT_MODE=false
AUTO_INSTALL=false
VERBOSE=false
CHECK_OPTIONAL=true

# Counters
ERRORS=0
WARNINGS=0
FIXED=0

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --strict)
            STRICT_MODE=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --no-optional)
            CHECK_OPTIONAL=false
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --strict        Fail on warnings"
            echo "  --auto-install  Attempt to auto-install missing dependencies"
            echo "  --verbose       Verbose output"
            echo "  --no-optional   Skip optional dependency checks"
            echo "  --help          Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Utility functions
log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✅${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
    ((WARNINGS++))
}

log_error() {
    echo -e "${RED}❌${NC} $1"
    ((ERRORS++))
}

log_fixed() {
    echo -e "${GREEN}🔧${NC} $1"
    ((FIXED++))
}

verbose_log() {
    if [[ $VERBOSE == true ]]; then
        echo -e "${BLUE}[DEBUG]${NC} $1"
    fi
}

version_ge() {
    # Compare versions: returns 0 if $1 >= $2
    printf '%s\n%s\n' "$2" "$1" | sort -V -C
}

check_command() {
    local cmd=$1
    local name=${2:-$cmd}
    
    if command -v "$cmd" &> /dev/null; then
        verbose_log "$name found at $(which "$cmd")"
        return 0
    else
        return 1
    fi
}

get_os() {
    case "$(uname -s)" in
        Darwin*)    echo "macos" ;;
        Linux*)     echo "linux" ;;
        CYGWIN*|MINGW*|MSYS*)    echo "windows" ;;
        *)          echo "unknown" ;;
    esac
}

get_distro() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        echo "$ID"
    elif command -v lsb_release &> /dev/null; then
        lsb_release -si | tr '[:upper:]' '[:lower:]'
    else
        echo "unknown"
    fi
}

provide_install_instructions() {
    local package=$1
    local name=${2:-$package}
    local os=$(get_os)
    
    echo -e "${YELLOW}📋 To install $name:${NC}"
    
    case $os in
        macos)
            echo "  brew install $package"
            ;;
        linux)
            local distro=$(get_distro)
            case $distro in
                ubuntu|debian)
                    echo "  sudo apt-get update && sudo apt-get install -y $package"
                    ;;
                centos|rhel|fedora)
                    echo "  sudo dnf install -y $package  # or yum on older systems"
                    ;;
                arch)
                    echo "  sudo pacman -S $package"
                    ;;
                *)
                    echo "  Install $package using your system package manager"
                    ;;
            esac
            ;;
        windows)
            echo "  Use chocolatey: choco install $package"
            echo "  Or download from official website"
            ;;
        *)
            echo "  Install $package using your system package manager"
            ;;
    esac
}

check_python() {
    log_info "Checking Python installation..."
    
    if check_command python3; then
        local version=$(python3 --version 2>&1 | cut -d' ' -f2)
        verbose_log "Python version: $version"
        
        if version_ge "$version" "$PYTHON_MIN_VERSION"; then
            log_success "Python $version found (>= $PYTHON_MIN_VERSION required)"
            return 0
        else
            log_error "Python $version found, but >= $PYTHON_MIN_VERSION required"
            provide_install_instructions python3 "Python $PYTHON_MIN_VERSION+"
            return 1
        fi
    else
        log_error "Python 3 not found"
        provide_install_instructions python3 "Python $PYTHON_MIN_VERSION+"
        return 1
    fi
}

check_poetry() {
    log_info "Checking Poetry installation..."
    
    if check_command poetry; then
        local version=$(poetry --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        verbose_log "Poetry version: $version"
        
        if version_ge "$version" "$POETRY_MIN_VERSION"; then
            log_success "Poetry $version found (>= $POETRY_MIN_VERSION required)"
            return 0
        else
            log_error "Poetry $version found, but >= $POETRY_MIN_VERSION required"
            echo -e "${YELLOW}📋 To update Poetry:${NC}"
            echo "  curl -sSL https://install.python-poetry.org | python3 -"
            return 1
        fi
    else
        log_error "Poetry not found"
        echo -e "${YELLOW}📋 To install Poetry:${NC}"
        echo "  curl -sSL https://install.python-poetry.org | python3 -"
        echo "  Then add ~/.local/bin to your PATH"
        return 1
    fi
}

check_docker() {
    log_info "Checking Docker installation..."
    
    if check_command docker; then
        # Check if Docker daemon is running
        if docker info &> /dev/null; then
            local version=$(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
            verbose_log "Docker version: $version"
            
            if version_ge "$version" "$DOCKER_MIN_VERSION"; then
                log_success "Docker $version found and running (>= $DOCKER_MIN_VERSION required)"
            else
                log_warning "Docker $version found, but >= $DOCKER_MIN_VERSION recommended"
            fi
        else
            log_error "Docker found but daemon not running"
            echo -e "${YELLOW}📋 To start Docker:${NC}"
            case $(get_os) in
                macos)
                    echo "  Start Docker Desktop application"
                    ;;
                linux)
                    echo "  sudo systemctl start docker"
                    echo "  sudo systemctl enable docker  # Start on boot"
                    ;;
                windows)
                    echo "  Start Docker Desktop application"
                    ;;
            esac
            return 1
        fi
    else
        log_error "Docker not found"
        echo -e "${YELLOW}📋 To install Docker:${NC}"
        case $(get_os) in
            macos)
                echo "  Download Docker Desktop from https://docker.com"
                echo "  Or: brew install --cask docker"
                ;;
            linux)
                echo "  curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh"
                echo "  sudo usermod -aG docker \$USER  # Add user to docker group"
                ;;
            windows)
                echo "  Download Docker Desktop from https://docker.com"
                ;;
        esac
        return 1
    fi
    
    # Check Docker Compose
    if docker compose version &> /dev/null; then
        local compose_version=$(docker compose version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        if version_ge "$compose_version" "$DOCKER_COMPOSE_MIN_VERSION"; then
            log_success "Docker Compose $compose_version found"
        else
            log_warning "Docker Compose $compose_version found, but >= $DOCKER_COMPOSE_MIN_VERSION recommended"
        fi
    else
        log_error "Docker Compose not found or not working"
        echo -e "${YELLOW}📋 Docker Compose should be included with modern Docker installations${NC}"
        echo "  Try updating Docker to the latest version"
        return 1
    fi
    
    return 0
}

check_git() {
    log_info "Checking Git installation..."
    
    if check_command git; then
        local version=$(git --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        log_success "Git $version found"
        
        # Check Git configuration
        if ! git config user.name &> /dev/null || ! git config user.email &> /dev/null; then
            log_warning "Git user configuration missing"
            echo -e "${YELLOW}📋 Configure Git:${NC}"
            echo "  git config --global user.name \"Your Name\""
            echo "  git config --global user.email \"your.email@example.com\""
        fi
        return 0
    else
        log_error "Git not found"
        provide_install_instructions git
        return 1
    fi
}

check_exiftool() {
    if [[ $CHECK_OPTIONAL != true ]]; then
        return 0
    fi
    
    log_info "Checking ExifTool installation..."
    
    if check_command exiftool; then
        local version=$(exiftool -ver 2>/dev/null)
        log_success "ExifTool $version found"
        return 0
    else
        log_warning "ExifTool not found (recommended for better metadata extraction)"
        echo -e "${YELLOW}📋 To install ExifTool:${NC}"
        case $(get_os) in
            macos)
                echo "  brew install exiftool"
                ;;
            linux)
                echo "  sudo apt-get install libimage-exiftool-perl  # Ubuntu/Debian"
                echo "  sudo dnf install perl-Image-ExifTool         # Fedora/RHEL"
                ;;
            windows)
                echo "  Download from https://exiftool.org/"
                ;;
        esac
        echo "  Note: The application will fall back to PIL if ExifTool is unavailable"
        return 1
    fi
}

check_system_resources() {
    log_info "Checking system resources..."
    
    # Check available disk space
    local available_space_kb
    case $(get_os) in
        macos|linux)
            available_space_kb=$(df . | tail -1 | awk '{print $4}')
            ;;
        *)
            log_warning "Cannot check disk space on this system"
            return 0
            ;;
    esac
    
    local available_space_gb=$((available_space_kb / 1024 / 1024))
    
    if [[ $available_space_gb -ge $REQUIRED_DISK_SPACE_GB ]]; then
        log_success "Sufficient disk space: ${available_space_gb}GB available (${REQUIRED_DISK_SPACE_GB}GB required)"
    else
        log_error "Insufficient disk space: ${available_space_gb}GB available, ${REQUIRED_DISK_SPACE_GB}GB required"
        echo "  AI models and photo processing require significant storage"
        echo "  Consider cleaning up or using external storage"
        return 1
    fi
    
    return 0
}

check_network_connectivity() {
    log_info "Checking network connectivity..."
    
    # Check internet connectivity
    if curl -s --max-time 5 https://www.google.com > /dev/null; then
        log_success "Internet connectivity verified"
    else
        log_error "No internet connectivity - required for downloading models and dependencies"
        return 1
    fi
    
    return 0
}

print_summary() {
    echo
    echo "=========================================="
    echo "  DEPENDENCY CHECK SUMMARY"
    echo "=========================================="
    
    if [[ $ERRORS -eq 0 && $WARNINGS -eq 0 ]]; then
        echo -e "${GREEN}🎉 All dependencies satisfied!${NC}"
        echo "You're ready to run: make install && make dev"
        exit 0
    elif [[ $ERRORS -eq 0 ]]; then
        echo -e "${YELLOW}⚠️  $WARNINGS warning(s) found${NC}"
        echo "You can proceed, but some features may be limited"
        if [[ $STRICT_MODE == true ]]; then
            echo -e "${RED}❌ Strict mode enabled - treating warnings as errors${NC}"
            exit 1
        else
            exit 0
        fi
    else
        echo -e "${RED}❌ $ERRORS error(s) found${NC}"
        if [[ $WARNINGS -gt 0 ]]; then
            echo -e "${YELLOW}⚠️  $WARNINGS warning(s) found${NC}"
        fi
        echo "Please fix the errors above before proceeding"
        
        if [[ $FIXED -gt 0 ]]; then
            echo -e "${GREEN}🔧 $FIXED issue(s) auto-fixed${NC}"
        fi
        
        echo
        echo "Run with --help to see all options"
        exit 1
    fi
}

main() {
    echo "🔍 Photools - Dependency Checker"
    echo "================================="
    echo
    
    if [[ $VERBOSE == true ]]; then
        echo "System: $(get_os) $(get_distro 2>/dev/null || echo '')"
        echo "Mode: $([ $STRICT_MODE == true ] && echo 'strict' || echo 'permissive')"
        echo "Auto-install: $AUTO_INSTALL"
        echo
    fi
    
    # Track overall success/failure
    local overall_result=0
    
    # Core dependencies (required) - don't exit on individual failures
    check_python || overall_result=1
    check_poetry || overall_result=1
    check_docker || overall_result=1
    check_git || overall_result=1
    
    # System resources
    check_system_resources || overall_result=1
    
    # Network connectivity
    check_network_connectivity || overall_result=1
    
    # Optional dependencies (warnings only)
    if [[ $CHECK_OPTIONAL == true ]]; then
        check_exiftool || true  # Don't fail on optional deps
    fi
    
    # Summary and exit
    print_summary
}

# Run main function and ensure we always exit properly
main "$@"

# Failsafe: This should never be reached due to explicit exits in print_summary
echo "ERROR: Script should have exited in print_summary function"
exit 1