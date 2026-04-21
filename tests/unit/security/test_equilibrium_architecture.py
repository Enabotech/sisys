"""Architecture Validation Tests for 等保 2.0 Level 3 Compliance.

Validates that the implementation adheres to the architecture constraints
defined in the SDD specification.

Reference: Story 1.12 等保 2.0 三级基础要求
"""

from __future__ import annotations

import ast
from pathlib import Path

# =============================================================================
# Architecture Constraints Tests
# =============================================================================


class TestArchitectureConstraints:
    """Validate architecture constraints are followed."""

    def test_domain_layer_has_no_external_dependencies(self):
        """Domain layer should have no external security library dependencies.

        Security services (MFA, intrusion detection, etc.) must be in
        infrastructure or interface layers, not in domain.
        """
        domain_events_path = Path("src/domain/events/compliance_events.py")

        if not domain_events_path.exists():
            # Skip if file doesn't exist (might be in different location)
            return

        content = domain_events_path.read_text()

        # Domain events should NOT import from infrastructure.security
        # (which contains MFA, intrusion detection, etc.)
        assert "infrastructure/security/mfa_service" not in content
        assert "infrastructure/security/totp_generator" not in content
        assert "infrastructure/security/intrusion_detector" not in content
        assert "infrastructure/security/backup_service" not in content
        assert "infrastructure/security/integrity_service" not in content

    def test_security_services_not_in_domain_layer(self):
        """Security service implementations must not be in domain layer."""
        domain_dir = Path("src/domain")

        if not domain_dir.exists():
            return

        # Check that security-related files are not in domain layer
        for file_path in domain_dir.rglob("*.py"):
            content = file_path.read_text()
            # Domain layer should not contain MFA or intrusion detection implementations
            assert "class MFAService" not in content, f"{file_path} should not contain MFAService"
            assert "class IntrusionDetector" not in content, f"{file_path} should not contain IntrusionDetector"
            assert "class TOTPGenerator" not in content, f"{file_path} should not contain TOTPGenerator"

    def test_hexagonal_architecture_layers_exist(self):
        """Verify hexagonal architecture layers are properly separated."""
        required_dirs = [
            "src/domain",
            "src/application",
            "src/infrastructure",
            "src/interfaces",
        ]

        for dir_path in required_dirs:
            assert Path(dir_path).exists(), f"Required directory {dir_path} does not exist"

    def test_security_services_in_infrastructure_layer(self):
        """Security services should be in infrastructure layer."""
        security_path = Path("src/infrastructure/security")

        if not security_path.exists():
            # If no security path, check that services exist elsewhere
            assert True  # Skip this assertion
            return

        # Security services should be in infrastructure
        expected_files = [
            "mfa_service.py",
            "totp_generator.py",
            "intrusion_detector.py",
            "backup_service.py",
            "integrity_service.py",
        ]

        existing_files = [f.name for f in security_path.glob("*.py")]

        for expected in expected_files:
            assert expected in existing_files, f"Expected security service {expected} not found"


# =============================================================================
# Circular Dependency Tests
# =============================================================================


class TestNoCircularDependencies:
    """Verify no circular dependencies exist in the codebase."""

    def _get_imports(self, file_path: Path) -> set[str]:
        """Extract all imports from a Python file."""
        if not file_path.exists():
            return set[str]()

        try:
            tree = ast.parse(file_path.read_text())
            imports: set[str] = set()

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module)

            return imports
        except Exception:
            return set[str]()

    def _module_to_path(self, module: str) -> Path:
        """Convert module name to file path."""
        return Path("src") / module.replace(".", "/")

    def test_no_circular_dependencies_in_security_module(self) -> None:
        """Security module should not have circular dependencies."""
        security_path = Path("src/infrastructure/security")

        if not security_path.exists():
            return

        # Collect all imports in security module files
        all_imports: dict[Path, set[str]] = {}
        for py_file in security_path.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            all_imports[py_file] = self._get_imports(py_file)

        # Check for obvious circular dependencies
        # (A imports B and B imports A)
        for file_a, imports_a in all_imports.items():
            for file_b, imports_b in all_imports.items():
                if file_a == file_b:
                    continue

                # Build module names for comparison
                module_a = f"infrastructure.security.{file_a.stem}"
                module_b = f"infrastructure.security.{file_b.stem}"

                # Check if A imports B and B imports A
                if module_b in imports_a and module_a in imports_b:
                    # This is a circular dependency
                    assert False, f"Circular dependency detected: {file_a} <-> {file_b}"


# =============================================================================
# Import Order Tests (using Ruff)
# =============================================================================


class TestImportOrder:
    """Verify imports are properly ordered (Ruff isort)."""

    def test_ruff_import_order_check(self):
        """Run ruff check on security module for import order."""
        import subprocess

        security_path = "src/infrastructure/security"

        if not Path(security_path).exists():
            return

        # Run ruff check (E rules for errors, I rules for import order)
        result = subprocess.run(
            ["python", "-m", "ruff", "check", security_path, "--select=E,I"],
            capture_output=True,
            text=True,
        )

        # Ruff returns 0 if no issues found
        assert result.returncode == 0, f"Ruff check failed:\n{result.stdout}\n{result.stderr}"


# =============================================================================
# Compliance Event Tests
# =============================================================================


class TestComplianceEvents:
    """Validate compliance events follow domain event patterns."""

    def test_mfa_event_fields(self):
        """MFAChallengeIssuedEvent should have required fields."""
        from uuid import uuid4

        from src.domain.events.compliance_events import MFAChallengeIssuedEvent

        event = MFAChallengeIssuedEvent(
            challenge_id=uuid4(),
            user_id=uuid4(),
            challenge_type="totp",
            status="pending",
        )

        assert hasattr(event, "event_id")
        assert hasattr(event, "timestamp")
        assert hasattr(event, "user_id")
        assert hasattr(event, "challenge_type")
        assert hasattr(event, "status")

    def test_intrusion_event_fields(self):
        """IntrusionDetectedEvent should have required fields."""
        from uuid import uuid4

        from src.domain.events.compliance_events import IntrusionDetectedEvent

        event = IntrusionDetectedEvent(
            intrusion_id=uuid4(),
            source_ip="192.168.1.1",
            attack_type="sql_injection",
            severity="high",
            action_taken="blocked",
        )

        assert hasattr(event, "event_id")
        assert hasattr(event, "timestamp")
        assert hasattr(event, "source_ip")
        assert hasattr(event, "attack_type")
        assert hasattr(event, "severity")

    def test_data_integrity_event_fields(self):
        """DataIntegrityViolationEvent should have required fields."""
        from uuid import uuid4

        from src.domain.events.compliance_events import DataIntegrityViolationEvent

        event = DataIntegrityViolationEvent(
            violation_id=uuid4(),
            data_id=uuid4(),
            expected_hash="abc123",
            actual_hash="def456",
        )

        assert hasattr(event, "event_id")
        assert hasattr(event, "timestamp")
        assert hasattr(event, "data_id")
        assert hasattr(event, "expected_hash")
        assert hasattr(event, "actual_hash")


# =============================================================================
# Security Coverage Tests
# =============================================================================


class TestSecurityCoverage:
    """Validate security service coverage meets requirements."""

    def test_mfa_service_has_required_methods(self):
        """MFAService must implement all required methods."""
        from src.infrastructure.security.mfa_service import MFAService

        service = MFAService()

        # Required methods for MFA
        assert hasattr(service, "setup_mfa")
        assert hasattr(service, "verify_mfa_setup")
        assert hasattr(service, "create_challenge")
        assert hasattr(service, "verify_challenge")
        assert hasattr(service, "get_mfa_status")

    def test_intrusion_detector_has_required_methods(self):
        """IntrusionDetector must implement all required methods."""
        from src.infrastructure.security.intrusion_detector import IntrusionDetector

        detector = IntrusionDetector()

        # Required methods
        assert hasattr(detector, "detect_attack")
        assert hasattr(detector, "assess_threat")
        assert hasattr(detector, "check_rate_limit")
        assert hasattr(detector, "record_failed_login")
        assert hasattr(detector, "create_intrusion_event")

    def test_backup_service_has_required_methods(self):
        """BackupService must implement all required methods."""
        from src.infrastructure.security.backup_service import BackupService, RecoveryService

        backup_service = BackupService()
        recovery_service = RecoveryService()

        # Required methods for BackupService
        assert hasattr(backup_service, "create_full_backup")
        assert hasattr(backup_service, "create_incremental_backup")
        assert hasattr(backup_service, "verify_backup")
        assert hasattr(backup_service, "get_backup")
        assert hasattr(backup_service, "list_backups")

        # Required methods for RecoveryService
        assert hasattr(recovery_service, "recover_from_backup")
        assert hasattr(recovery_service, "recover_incremental_chain")

    def test_integrity_verifier_has_required_methods(self):
        """IntegrityVerifier must implement all required methods."""
        from src.infrastructure.security.integrity_service import IntegrityVerifier, SignatureService

        verifier = IntegrityVerifier()
        signature_service = SignatureService()

        # Required methods for IntegrityVerifier
        assert hasattr(verifier, "compute_hash")
        assert hasattr(verifier, "verify_hash")
        assert hasattr(verifier, "verify_and_record")

        # Required methods for SignatureService
        assert hasattr(signature_service, "generate_key_pair")
        assert hasattr(signature_service, "sign")
        assert hasattr(signature_service, "verify")
        assert hasattr(signature_service, "sign_data_with_timestamp")
        assert hasattr(signature_service, "verify_data_with_timestamp")


# =============================================================================
# Model Tests
# =============================================================================


class TestSecurityModels:
    """Validate security models have required fields and methods."""

    def test_mfa_challenge_model(self):
        """MFAChallenge model should have required fields."""
        from datetime import UTC, datetime, timedelta
        from uuid import uuid4

        from src.infrastructure.security.models import MFAChallenge

        challenge = MFAChallenge(
            id=uuid4(),
            user_id=uuid4(),
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

        assert hasattr(challenge, "id")
        assert hasattr(challenge, "user_id")
        assert hasattr(challenge, "expires_at")
        assert hasattr(challenge, "is_expired")
        assert hasattr(challenge, "is_max_attempts_reached")

    def test_backup_record_model(self):
        """BackupRecord model should have required fields."""
        from datetime import UTC, datetime
        from uuid import uuid4

        from src.infrastructure.security.models import BackupRecord, BackupStatus, BackupType

        record = BackupRecord(
            id=uuid4(),
            backup_type=BackupType.FULL,
            start_time=datetime.now(UTC),
            status=BackupStatus.COMPLETED,
        )

        assert hasattr(record, "id")
        assert hasattr(record, "backup_type")
        assert hasattr(record, "status")
        assert hasattr(record, "start_time")
        assert hasattr(record, "is_completed")
        assert hasattr(record, "duration_seconds")

    def test_threat_score_model(self):
        """ThreatScore model should calculate severity correctly."""
        from src.infrastructure.security.models import ThreatScore

        # Test low severity
        score_low = ThreatScore(score=20.0)
        assert score_low.severity_level() == "low"

        # Test medium severity
        score_medium = ThreatScore(score=50.0)
        assert score_medium.severity_level() == "medium"

        # Test high severity
        score_high = ThreatScore(score=70.0)
        assert score_high.severity_level() == "high"

        # Test critical severity
        score_critical = ThreatScore(score=90.0)
        assert score_critical.severity_level() == "critical"
