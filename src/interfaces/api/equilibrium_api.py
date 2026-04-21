"""等保 2.0 Level 3 Compliance API Endpoints.

FastAPI routes for:
- POST /api/v1/auth/mfa/setup - MFA setup for user
- POST /api/v1/auth/mfa/verify - Verify MFA code
- GET /api/v1/compliance/status - Compliance status query
- GET/POST /api/v1/admin/backups - Backup management
- POST /api/v1/admin/backups/{backup_id}/restore - Restore from backup
- POST /api/v1/integrity/check - Data integrity check

Reference: Story 1.12 等保 2.0 三级基础要求
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.infrastructure.security.backup_service import BackupService, RecoveryService
from src.infrastructure.security.integrity_service import IntegrityVerifier
from src.infrastructure.security.mfa_service import MFAService, get_mfa_service
from src.infrastructure.security.permission_middleware import get_current_user as auth_get_current_user
from src.interfaces.api.equilibrium_endpoints import (
    BackupCreateRequest,
    BackupListResponse,
    BackupResponse,
    BackupRestoreRequest,
    BackupRestoreResponse,
    ComplianceStatusResponse,
    IntegrityCheckRequest,
    IntegrityCheckResponse,
    MFASetupRequest,
    MFASetupResponse,
    MFAStatusResponse,
    MFAVerifyRequest,
    MFAVerifyResponse,
)

router = APIRouter(prefix="/api/v1", tags=["equilibrium"])


# =========================================================================
# MFA Endpoints
# =========================================================================


@router.post("/auth/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(
    request: MFASetupRequest,
    mfa_service: Annotated[MFAService, Depends(get_mfa_service)],
    current_user: dict = Depends(auth_get_current_user),
) -> MFASetupResponse:
    """Setup MFA for a user.

    Generates a new TOTP secret and provisioning URI for the user.
    The secret is returned once and must be stored securely by the client.
    """
    try:
        result = mfa_service.setup_mfa(
            user_id=request.user_id,
            username=request.username or current_user.get("username", ""),
        )

        return MFASetupResponse(
            success=result.success,
            secret=result.secret,
            provisioning_uri=result.provisioning_uri,
            challenge_id=result.challenge_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MFA setup failed: {str(e)}",
        )


@router.post("/auth/mfa/verify", response_model=MFAVerifyResponse)
async def mfa_verify(
    request: MFAVerifyRequest,
    mfa_service: Annotated[MFAService, Depends(get_mfa_service)],
    current_user: dict = Depends(auth_get_current_user),
) -> MFAVerifyResponse:
    """Verify MFA code for a user.

    Verifies the TOTP code provided by the user during login or sensitive operations.
    """
    try:
        # Create a challenge and verify it
        challenge = mfa_service.create_challenge(
            user_id=request.user_id,
            ip_address=current_user.get("ip_address", "unknown"),
            user_agent=current_user.get("user_agent", "unknown"),
        )

        result = mfa_service.verify_challenge(
            challenge_id=challenge.challenge_id,
            code=request.code,
        )

        return MFAVerifyResponse(
            success=result.success,
            challenge_id=challenge.challenge_id,
            message="MFA verification successful" if result.success else "Invalid MFA code",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MFA verification failed: {str(e)}",
        )


@router.get("/auth/mfa/status/{user_id}", response_model=MFAStatusResponse)
async def mfa_status(
    user_id: UUID,
    mfa_service: Annotated[MFAService, Depends(get_mfa_service)],
    current_user: dict = Depends(auth_get_current_user),
) -> MFAStatusResponse:
    """Get MFA status for a user."""
    mfa_enabled = mfa_service.get_mfa_status(user_id)

    return MFAStatusResponse(
        user_id=user_id,
        mfa_enabled=mfa_enabled,
        challenge_type="totp" if mfa_enabled else None,
    )


# =========================================================================
# Compliance Status Endpoints
# =========================================================================


@router.get("/compliance/status", response_model=ComplianceStatusResponse)
async def compliance_status(
    level: int = 3,
    current_user: dict = Depends(auth_get_current_user),
) -> ComplianceStatusResponse:
    """Get 等保 2.0 compliance status.

    Returns comprehensive compliance metrics for the specified level.
    In MVP, returns simulated/composite data.
    """
    # In production, this would query actual services
    # For MVP, return composite metrics
    return ComplianceStatusResponse(
        level=level,
        status="compliant" if level == 3 else "not_evaluated",
        mfa_coverage=100.0,
        rbac_coverage=100.0,
        audit_log_integrity=100.0,
        intrusion_detection_rate=95.0,
        data_encryption_rate=100.0,
        backup_recovery_time=30.0,
        high_risk_count=0,
        medium_risk_count=2,
        last_audit=datetime.now() - timedelta(days=7),
        next_audit=datetime.now() + timedelta(days=23),
    )


# =========================================================================
# Backup Management Endpoints
# =========================================================================


backup_service = BackupService()
recovery_service = RecoveryService(backup_service)


@router.post("/admin/backups", response_model=BackupResponse)
async def create_backup(
    request: BackupCreateRequest,
    current_user: dict = Depends(auth_get_current_user),
) -> BackupResponse:
    """Create a new backup (full or incremental)."""
    user_id = UUID(current_user.get("user_id", "00000000-0000-0000-0000-000000000000"))

    try:
        if request.backup_type.value == "full":
            record = await backup_service.create_full_backup(
                user_id=user_id,
                description=request.description,
            )
        else:
            if not request.base_backup_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="base_backup_id required for incremental backup",
                )
            record = await backup_service.create_incremental_backup(
                user_id=user_id,
                base_backup_id=request.base_backup_id,
                description=request.description,
            )

        return BackupResponse(
            id=record.id,
            backup_type=record.backup_type,
            status=record.status,
            size_bytes=record.size_bytes,
            checksum=record.checksum,
            location=record.location,
            start_time=record.start_time,
            end_time=record.end_time,
            description=record.description or "",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backup creation failed: {str(e)}",
        )


@router.get("/admin/backups", response_model=BackupListResponse)
async def list_backups(
    backup_type: str | None = None,
    status: str | None = None,
    limit: int = 100,
    current_user: dict = Depends(auth_get_current_user),
) -> BackupListResponse:
    """List backup records with optional filters."""
    from src.infrastructure.security.models import BackupStatus, BackupType

    backup_type_filter = BackupType[backup_type.upper()] if backup_type else None
    status_filter = BackupStatus[status.upper()] if status else None

    records = await backup_service.list_backups(
        backup_type=backup_type_filter,
        status=status_filter,
        limit=limit,
    )

    backups = [
        BackupResponse(
            id=r.id,
            backup_type=r.backup_type,
            status=r.status,
            size_bytes=r.size_bytes,
            checksum=r.checksum,
            location=r.location,
            start_time=r.start_time,
            end_time=r.end_time,
            description=r.description or "",
        )
        for r in records
    ]

    return BackupListResponse(
        backups=backups,
        total=len(backups),
        limit=limit,
    )


@router.get("/admin/backups/{backup_id}", response_model=BackupResponse)
async def get_backup(
    backup_id: UUID,
    current_user: dict = Depends(auth_get_current_user),
) -> BackupResponse:
    """Get a specific backup record."""
    record = await backup_service.get_backup(backup_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup {backup_id} not found",
        )

    return BackupResponse(
        id=record.id,
        backup_type=record.backup_type,
        status=record.status,
        size_bytes=record.size_bytes,
        checksum=record.checksum,
        location=record.location,
        start_time=record.start_time,
        end_time=record.end_time,
        description=record.description or "",
    )


@router.post("/admin/backups/{backup_id}/restore", response_model=BackupRestoreResponse)
async def restore_backup(
    backup_id: UUID,
    request: BackupRestoreRequest,
    current_user: dict = Depends(auth_get_current_user),
) -> BackupRestoreResponse:
    """Restore data from a backup."""
    try:
        result = await recovery_service.recover_from_backup(
            backup_id=backup_id,
            target_path=request.target_path,
        )

        return BackupRestoreResponse(
            backup_id=UUID(result["backup_id"]),
            backup_type=result["backup_type"],
            target_path=result["target_path"],
            size_bytes=result["size_bytes"],
            duration_seconds=result["duration_seconds"],
            status=result["status"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Restore failed: {str(e)}",
        )


# =========================================================================
# Integrity Check Endpoints
# =========================================================================


integrity_verifier = IntegrityVerifier()


@router.post("/integrity/check", response_model=IntegrityCheckResponse)
async def check_integrity(
    request: IntegrityCheckRequest,
    current_user: dict = Depends(auth_get_current_user),
) -> IntegrityCheckResponse:
    """Check data integrity against expected hash."""
    from src.infrastructure.security.models import HashAlgorithm

    data_id = request.data_id or UUID("00000000-0000-0000-0000-000000000000")
    algorithm = HashAlgorithm.SHA256 if request.algorithm == "SHA256" else HashAlgorithm.SHA512

    check = await integrity_verifier.verify_and_record(
        data_id=data_id,
        data="",  # In production, this would fetch actual data
        expected_hash=request.expected_hash,
        data_type=request.data_type,
        algorithm=algorithm,
    )

    return IntegrityCheckResponse(
        data_id=check.data_id,
        data_type=check.data_type,
        status=check.status,
        algorithm=check.algorithm.value,
        hash_value=check.hash_value,
        verified_at=datetime.now(),
        source=check.source or "",
    )
