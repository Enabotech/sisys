#!/bin/bash
# Test Runner Script
# Usage: ./scripts/testing/run_tests.sh [options]
#
# Options:
#   --unit        Run only unit tests
#   --integration Run only integration tests
#   --e2e         Run only E2E tests
#   --all         Run all tests (default)
#   --coverage    Generate coverage report
#   --fast        Run only fast tests (no slow tests)
#   --watch       Watch mode (rerun on file changes)
#
# Examples:
#   ./scripts/testing/run_tests.sh --unit --coverage
#   ./scripts/testing/run_tests.sh --all --fast

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
RUN_UNIT=false
RUN_INTEGRATION=false
RUN_E2E=false
RUN_ALL=true
RUN_COVERAGE=false
RUN_FAST=false
RUN_WATCH=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --unit)
      RUN_UNIT=true
      RUN_ALL=false
      shift
      ;;
    --integration)
      RUN_INTEGRATION=true
      RUN_ALL=false
      shift
      ;;
    --e2e)
      RUN_E2E=true
      RUN_ALL=false
      shift
      ;;
    --all)
      RUN_ALL=true
      shift
      ;;
    --coverage)
      RUN_COVERAGE=true
      shift
      ;;
    --fast)
      RUN_FAST=true
      shift
      ;;
    --watch)
      RUN_WATCH=true
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [options]"
      echo ""
      echo "Options:"
      echo "  --unit        Run only unit tests"
      echo "  --integration Run only integration tests"
      echo "  --e2e         Run only E2E tests"
      echo "  --all         Run all tests (default)"
      echo "  --coverage    Generate coverage report"
      echo "  --fast        Run only fast tests (no slow tests)"
      echo "  --watch       Watch mode (rerun on file changes)"
      echo "  -h, --help    Show this help message"
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

# Function to print section header
print_header() {
  echo -e "\n${BLUE}========================================${NC}"
  echo -e "${BLUE}$1${NC}"
  echo -e "${BLUE}========================================${NC}\n"
}

# Function to print success
print_success() {
  echo -e "${GREEN}✅ $1${NC}"
}

# Function to print warning
print_warning() {
  echo -e "${YELLOW}⚠️  $1${NC}"
}

# Function to print error
print_error() {
  echo -e "${RED}❌ $1${NC}"
}

# Check if Poetry is installed
check_poetry() {
  if ! command -v poetry &> /dev/null; then
    print_error "Poetry is not installed. Please install Poetry first."
    exit 1
  fi
}

# Check if virtual environment exists
check_venv() {
  if [ ! -d ".venv" ]; then
    print_warning "Virtual environment not found. Installing dependencies..."
    poetry install
  fi
}

# Run unit tests
run_unit_tests() {
  print_header "Running Unit Tests"

  # Check if unit test directory exists and has test files
  if [ ! -f "tests/unit/test_*.py" ] && \
      [ -z "$(find tests/unit -name 'test_*.py' 2>/dev/null)" ]; then
    print_warning "No unit tests found in tests/unit/"
    print_warning "Unit tests will be created in Story 0.3: Test Framework Setup"
    return 0
  fi

  if [ "$RUN_FAST" = true ]; then
    poetry run pytest tests/unit/ -v --tb=short -m "not slow"
  else
    poetry run pytest tests/unit/ -v --tb=short
  fi

  print_success "Unit tests passed"
}

# Run integration tests
run_integration_tests() {
  print_header "Running Integration Tests"

  # Check if integration test directory exists and has test files
  if [ ! -f "tests/integration/test_*.py" ] && \
      [ -z "$(find tests/integration -name 'test_*.py' 2>/dev/null)" ]; then
    print_warning "No integration tests found in tests/integration/"
    print_warning "Integration tests will be created in Story 0.3: Test Framework Setup"
    return 0
  fi

  # Check if Docker is running
  if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Integration tests require Docker."
    exit 1
  fi

  # Start test containers if needed
  echo "Starting test containers..."
  docker compose -f docker/docker-compose.test.yml up -d || true

  # Wait for containers to be ready
  echo "Waiting for test containers to be ready..."
  sleep 10

  if [ "$RUN_FAST" = true ]; then
    poetry run pytest tests/integration/ -v --tb=short -m "not slow"
  else
    poetry run pytest tests/integration/ -v --tb=short
  fi

  print_success "Integration tests passed"
}

# Run E2E tests
run_e2e_tests() {
  print_header "Running E2E Tests"

  # Check if Docker is running
  if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. E2E tests require Docker."
    exit 1
  fi

  if [ "$RUN_FAST" = true ]; then
    poetry run pytest tests/e2e/ -v --tb=short -m "not slow"
  else
    poetry run pytest tests/e2e/ -v --tb=short
  fi

  print_success "E2E tests passed"
}

# Generate coverage report
generate_coverage() {
  print_header "Generating Coverage Report"

  poetry run pytest \
    --cov=src \
    --cov-report=html:htmlcov \
    --cov-report=xml:coverage.xml \
    --cov-report=term-missing \
    tests/

  echo ""
  print_success "Coverage report generated:"
  echo "  - HTML: htmlcov/index.html"
  echo "  - XML: coverage.xml"

  # Open HTML report if on macOS or Windows (WSL)
  if [[ "$OSTYPE" == "darwin"* ]]; then
    open htmlcov/index.html
  elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    start htmlcov/index.html
  elif [[ -n "$WSL_DISTRO_NAME" ]]; then
    explorer.exe htmlcov/index.html
  fi
}

# Main execution
main() {
  print_header "🧪 sisys Test Runner"

  check_poetry
  check_venv

  # Activate virtual environment
  source .venv/bin/activate 2>/dev/null || true

  TESTS_RUN=false
  TESTS_PASSED=true

  if [ "$RUN_ALL" = true ]; then
    TESTS_RUN=true
    run_unit_tests || TESTS_PASSED=false
    run_integration_tests || TESTS_PASSED=false
    run_e2e_tests || TESTS_PASSED=false
  else
    if [ "$RUN_UNIT" = true ]; then
      TESTS_RUN=true
      run_unit_tests || TESTS_PASSED=false
    fi

    if [ "$RUN_INTEGRATION" = true ]; then
      TESTS_RUN=true
      run_integration_tests || TESTS_PASSED=false
    fi

    if [ "$RUN_E2E" = true ]; then
      TESTS_RUN=true
      run_e2e_tests || TESTS_PASSED=false
    fi
  fi

  if [ "$RUN_COVERAGE" = true ]; then
    generate_coverage
  fi

  echo ""
  if [ "$TESTS_RUN" = true ]; then
    if [ "$TESTS_PASSED" = true ]; then
      print_success "All tests completed successfully! 🎉"
      echo ""
      echo "Next steps:"
      echo "  - Run 'pytest tests/e2e/' to verify Story 0.1 and 0.2 acceptance criteria"
      echo "  - Story 0.3 will add unit and integration tests"
    else
      print_error "Some tests failed. Please check the output above."
      exit 1
    fi
  else
    print_warning "No tests were run. Use --help for usage information."
  fi
}

# Run main function
main
