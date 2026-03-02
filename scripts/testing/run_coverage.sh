#!/bin/bash
# Coverage Report Generator
# Usage: ./scripts/testing/run_coverage.sh [options]
#
# Options:
#   --open    Open HTML report in browser
#   --xml     Generate XML report (for CI/CD)
#   --fail    Fail if coverage is below threshold
#   --help    Show this help message
#
# Examples:
#   ./scripts/testing/run_coverage.sh --open
#   ./scripts/testing/run_coverage.sh --fail --threshold 80

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
OPEN_REPORT=false
GENERATE_XML=true
FAIL_BELOW_THRESHOLD=false
THRESHOLD=80

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --open)
      OPEN_REPORT=true
      shift
      ;;
    --xml)
      GENERATE_XML=true
      shift
      ;;
    --fail)
      FAIL_BELOW_THRESHOLD=true
      shift
      ;;
    --threshold)
      THRESHOLD="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [options]"
      echo ""
      echo "Options:"
      echo "  --open    Open HTML report in browser"
      echo "  --xml     Generate XML report (for CI/CD)"
      echo "  --fail    Fail if coverage is below threshold"
      echo "  --threshold  Coverage threshold percentage (default: 80)"
      echo "  -h, --help    Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Print header
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}📊 Coverage Report Generator${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
  echo -e "${RED}❌ Poetry is not installed${NC}"
  exit 1
fi

# Run tests with coverage
echo "Running tests with coverage..."
poetry run pytest \
  tests/ \
  --cov=src \
  --cov-report=html:htmlcov \
  --cov-report=xml:coverage.xml \
  --cov-report=term-missing \
  --cov-fail-under=$THRESHOLD \
  -v \
  --tb=short

echo ""
echo -e "${GREEN}✅ Coverage report generated successfully${NC}"
echo ""
echo "📁 Report locations:"
echo "  - HTML: htmlcov/index.html"
echo "  - XML:  coverage.xml"
echo ""

# Check if coverage is above threshold
if [ "$FAIL_BELOW_THRESHOLD" = true ]; then
  COVERAGE=$(grep -o '"totals": {"percent_covered": [0-9.]*' coverage.xml | grep -o '[0-9.]*$' || echo "0")
  echo "Current coverage: ${COVERAGE}%"
  
  if (( $(echo "$COVERAGE < $THRESHOLD" | bc -l) )); then
    echo -e "${RED}❌ Coverage ${COVERAGE}% is below threshold ${THRESHOLD}%${NC}"
    exit 1
  else
    echo -e "${GREEN}✅ Coverage ${COVERAGE}% meets threshold ${THRESHOLD}%${NC}"
  fi
fi

# Open HTML report if requested
if [ "$OPEN_REPORT" = true ]; then
  if [[ "$OSTYPE" == "darwin"* ]]; then
    open htmlcov/index.html
  elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    start htmlcov/index.html
  elif [[ -n "$WSL_DISTRO_NAME" ]]; then
    explorer.exe htmlcov/index.html
  else
    echo "Please open htmlcov/index.html in your browser"
  fi
fi

echo ""
echo -e "${GREEN}🎉 Done!${NC}"
